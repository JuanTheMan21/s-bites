"""``/tiers``, executable: a real topic taken as far as tier assignment, and no further.

    PYTHONPATH=. .venv/Scripts/python.exe scripts/tier_dry_run.py "teach me about SQL injection"

Outline, narration and **real** TTS -- then the tier resolver, then stop. No scene authoring, no
rendering, which is what makes this the cheap iteration loop ``/tiers`` describes: rendering a
seven-minute video to discover the tier distribution is wrong costs minutes of render time, and
this costs a handful of completions and the same number of syntheses.

The TTS calls are the point, and are why this is not a fixture. D32's open question -- is
``FRAME_BUDGET`` tuned such that Tier 2 buys importance or merely shortness -- is a question about
how long real narration of real segments actually turns out to be, and ``tests/segment_examples.py``
answers it only with durations somebody typed in by hand.

Lives in ``scripts/`` rather than ``core/``: it names concrete adapters through ``config.py``, the
same precedent ``scripts/verify_azure.py`` and ``scripts/measure_segment_concurrency.py`` set (D51).
"""

import argparse
import asyncio
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from config import Adapters, build_adapters, close_adapters
from core.frame_budget import scale_frame_budget
from core.graph.nodes.outline import generate_outline
from core.graph.nodes.scripting import write_narration
from core.models import DEFAULT_TARGET_DURATION_MS, Segment, Tier, VideoJob
from core.tier_resolver import TierPlan, resolve_tiers

RUN_ROOT = Path("artifacts") / "_tier_dry_run"


def _print_table(segments: list[Segment], plan: TierPlan) -> None:
    """Index, title, intent, importance, measured duration, tier, cumulative frames."""
    print(
        f"\n{'#':>2}  {'title':<34} {'intent':<18} {'imp':>3} "
        f"{'measured':>9} {'tier':>5} {'frames':>7} {'cum':>7}"
    )
    print("-" * 96)
    cumulative = 0
    by_index = {segment.index: segment for segment in segments}
    for assignment in plan.assignments:
        segment = by_index[assignment.index]
        cumulative += assignment.frame_cost
        demotion = f"  (wanted T{assignment.ideal})" if assignment.demoted else ""
        duration_s = (segment.duration_ms or 0) / 1000
        print(
            f"{segment.index:>2}  {segment.title[:34]:<34} {segment.visual_intent.value:<18} "
            f"{int(segment.importance):>3} {duration_s:>8.1f}s "
            f"{'T' + str(int(assignment.assigned)):>5} {assignment.frame_cost:>7} "
            f"{cumulative:>7}{demotion}"
        )


def _print_summary(plan: TierPlan, base_budget: int, fps: int) -> None:
    spread = plan.spread
    # Costed at the run's own fps, not a literal 24: this line is read by whoever is deciding
    # what FRAME_BUDGET should be, and a budget is really a render-time budget (D16).
    animated_frames = sum(a.frame_cost for a in plan.assignments if a.assigned is Tier.ANIMATED)
    total_s = animated_frames / fps
    print(f"\nframes: {plan.frames_used} used of {plan.frame_budget} (base {base_budget})")
    print(
        "spread: "
        + "  ".join(f"T{int(tier)}={count}" for tier, count in sorted(spread.items()))
        + f"   ({total_s:.0f}s of animation)"
    )

    if plan.demoted:
        print("\ndemoted by the budget:")
        for assignment in plan.demoted:
            print(
                f"  segment {assignment.index}: T{int(assignment.ideal)} -> "
                f"T{int(assignment.assigned)}"
            )
    else:
        print("\ndemoted by the budget: none -- every segment got the tier it asked for")

    empty = [tier for tier, count in spread.items() if count == 0]
    if empty:
        print(
            "\nWARNING: "
            + ", ".join(f"Tier {int(tier)}" for tier in empty)
            + " is empty. The tier system is doing less than it looks like it is (D32)."
        )


def _required_int(name: str) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {value!r}") from exc


async def _measure(
    adapters: Adapters, segments: dict[int, Segment], job_id: str
) -> dict[int, Segment]:
    """Narrate every segment for real and take ``duration_ms`` from the file that came back.

    Sequential, matching ``write_narration``: this is a tuning run, not a throughput measurement,
    and ``scripts/measure_segment_concurrency.py`` already owns the latter question.
    """
    measured: dict[int, Segment] = {}
    for index, segment in sorted(segments.items()):
        dest = RUN_ROOT / job_id / f"{index}.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        _, duration_ms = await adapters.tts.synthesize(segment.narration, dest)
        print(f"  segment {index}: {duration_ms / 1000:>5.1f}s  {segment.title[:48]}")
        measured[index] = segment.model_copy(update={"duration_ms": duration_ms})
    return measured


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("topic", help="the prompt as a user would type it")
    parser.add_argument(
        "--target-duration-ms",
        type=int,
        default=DEFAULT_TARGET_DURATION_MS,
        help="requested video length; the segment count and the frame budget both derive from it",
    )
    parser.add_argument(
        "--keep-audio", action="store_true", help=f"leave the WAVs under {RUN_ROOT}"
    )
    args = parser.parse_args()

    load_dotenv()
    # Required rather than defaulted. A default here would be a third place carrying a number
    # .env and .env.example already carry, and D32 is what happens when copies drift apart.
    base_budget = _required_int("FRAME_BUDGET")
    fps = _required_int("FPS")

    job = VideoJob(
        job_id="tier-dry-run", topic=args.topic, target_duration_ms=args.target_duration_ms
    )
    adapters = build_adapters()
    try:
        print(f"outlining {job.topic!r} into ~{job.segment_count} segments...")
        segments = await generate_outline(adapters.llm, adapters.skills, job)
        print(f"narrating {len(segments)} segments...")
        segments = await write_narration(adapters.llm, adapters.skills, segments)
        print("synthesising and measuring...")
        segments = await _measure(adapters, segments, job.job_id)
    finally:
        await close_adapters(adapters)

    budget = scale_frame_budget(base_budget, job.target_duration_ms)
    plan = resolve_tiers(list(segments.values()), frame_budget=budget, fps=fps)

    _print_table(list(segments.values()), plan)
    _print_summary(plan, base_budget, fps)

    if not args.keep_audio and RUN_ROOT.exists():
        shutil.rmtree(RUN_ROOT)


if __name__ == "__main__":
    asyncio.run(main())
