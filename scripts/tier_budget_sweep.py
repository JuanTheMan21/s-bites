"""T18J: measure real segment durations ONCE for a topic, then show the tier spread
``FRAME_BUDGET`` values produce against that SAME measured set -- a fair, apples-to-apples
comparison ``tier_dry_run.py`` alone cannot give, since re-running it per budget value would
re-generate a fresh outline/narration each time (LLM non-determinism) and compare different
segment sets rather than the effect of the budget itself.

    PYTHONPATH=. .venv/Scripts/python.exe scripts/tier_budget_sweep.py "<topic>" 1400 3000 6000 9500

Real outline + narration + TTS cost once; resolve_tiers() itself is pure and free, so every
additional budget value in the sweep costs nothing further.
"""

import asyncio
import shutil
import sys

from dotenv import load_dotenv

from config import build_adapters, close_adapters
from core.frame_budget import scale_frame_budget
from core.graph.nodes.outline import generate_outline
from core.graph.nodes.scripting import write_narration
from core.tier_resolver import resolve_tiers
from core.video_job import VideoJob
from scripts.tier_dry_run import RUN_ROOT, _measure, _required_int


async def main() -> None:
    topic = sys.argv[1]
    budgets = [int(b) for b in sys.argv[2:]]
    if not budgets:
        raise SystemExit("usage: tier_budget_sweep.py <topic> <budget1> [budget2 ...]")

    load_dotenv()
    fps = _required_int("FPS")

    job = VideoJob(job_id="tier-budget-sweep", topic=topic)
    adapters = build_adapters()
    try:
        print(f"outlining {job.topic!r} into ~{job.segment_count} segments...")
        segments = await generate_outline(adapters.llm, adapters.skills, job)
        print(f"narrating {len(segments)} segments...")
        segments = await write_narration(adapters.llm, adapters.skills, segments)
        print("synthesising and measuring (real TTS, once)...")
        segments = await _measure(adapters, segments, job.job_id)
    finally:
        await close_adapters(adapters)

    seg_list = list(segments.values())
    total_narration_s = sum((s.duration_ms or 0) for s in seg_list) / 1000
    print(f"\n{len(seg_list)} segments, {total_narration_s:.0f}s of real narration\n")
    print(f"{'budget':>8} {'scaled':>8} {'T0':>4} {'T1':>4} {'T2':>4} {'anim_s':>8}  demoted")
    print("-" * 60)

    for base in budgets:
        scaled = scale_frame_budget(base, job.target_duration_ms)
        plan = resolve_tiers(seg_list, frame_budget=scaled, fps=fps)
        spread = plan.spread
        animated_frames = sum(a.frame_cost for a in plan.assignments if a.assigned.value == 2)
        anim_s = animated_frames / fps
        counts = {int(t): c for t, c in spread.items()}
        print(
            f"{base:>8} {scaled:>8} {counts.get(0, 0):>4} {counts.get(1, 0):>4} "
            f"{counts.get(2, 0):>4} {anim_s:>7.0f}s  {len(plan.demoted)} demoted"
        )

    if RUN_ROOT.exists():
        shutil.rmtree(RUN_ROOT)


if __name__ == "__main__":
    asyncio.run(main())
