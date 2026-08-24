"""D47's third carry-forward, closed with a number: does DiskStorage's synchronous I/O stall
concurrent jobs sharing one event loop, now that T14's per-segment fan-out actually generates
concurrency to measure it with?

Run by hand -- ``python -m scripts.measure_segment_concurrency`` from the repo root -- against
the real local ``DiskStorage`` (never imported from core/graph/ itself; scripts/ sits outside the
boundary, same precedent as scripts/verify_azure.py, D51). TTS and the LLM stay fake: this measures
disk contention, not network latency, and real calls would drown the signal in synthesis time.

``DiskSkillRegistry`` is not separately exercised here -- the graph's ``SkillRegistry`` calls go to
a fake, for the same reason -- but its reads share ``DiskStorage``'s exact shape (synchronous I/O
inside an ``async def``, per D47), so this measurement's answer applies to both rather than needing
a second, contrived run.
"""

import asyncio
import shutil
import time
from pathlib import Path

from adapters.local.storage import DiskStorage
from core.graph import GraphContext, build_graph
from core.models import Importance, VideoJob, VisualIntent
from core.outline_schema import Outline, SegmentPlan
from core.scripting_schema import Narration
from core.slot_schemas import TitleCardSlots
from interfaces import SkillPack
from tests.fakes import FakeLLMProvider, FakeRenderBackend, FakeSkillRegistry, FakeTTSProvider

SEGMENT_COUNT_TARGET_MS = 15 * 28 * 1000  # ~15 segments, a realistic 7-minute job
RUN_ROOT = Path("artifacts") / "_measure_segment_concurrency"

# Only reach the tier resolver, which this run does not measure -- the .env defaults, so the graph
# behaves as it would in a real run rather than on numbers invented here.
FRAME_BUDGET = 600
FPS = 24


def _seeded_skills() -> FakeSkillRegistry:
    """Every pack the graph's four LLM-calling steps load. Content is irrelevant to a timing run."""
    return FakeSkillRegistry(
        [
            SkillPack(name=name, version="1.0", content=f"{name} pack")
            for name in ("outline", "scripting", "house-style", "scene-authoring")
        ]
    )


def _seeded_llm(segment_count: int) -> FakeLLMProvider:
    """One outline, one narration per segment, one slot payload per segment -- the exact call
    sequence a real run makes. Every segment is a title card, so the slot payloads are
    interchangeable and the concurrent ``author_scene`` tasks may pop them in any order."""
    outline = Outline(
        segments=[
            SegmentPlan(
                title=f"Segment {i}",
                summary="One idea, explained.",
                visual_intent=VisualIntent.TITLE_CARD,
                importance=Importance.NORMAL,
            )
            for i in range(segment_count)
        ]
    )
    narrations = [Narration(text=f"Narration {i}.") for i in range(segment_count)]
    slots = [TitleCardSlots(headline=f"Headline {i}", subtitle=None) for i in range(segment_count)]
    return FakeLLMProvider([outline, *narrations, *slots])


async def main() -> None:
    if RUN_ROOT.exists():
        shutil.rmtree(RUN_ROOT)
    storage_root = RUN_ROOT / "storage"

    job = VideoJob(
        job_id="measure-1", topic="measurement run", target_duration_ms=SEGMENT_COUNT_TARGET_MS
    )
    context = GraphContext(
        llm=_seeded_llm(job.segment_count),
        tts=FakeTTSProvider(),
        storage=DiskStorage(storage_root),
        skills=_seeded_skills(),
        render=FakeRenderBackend(),
        working_dir=RUN_ROOT / "work",
        frame_budget=FRAME_BUDGET,
        fps=FPS,
    )

    graph = build_graph()  # no checkpointer: this run measures throughput, not resume
    config = {"configurable": {"thread_id": job.job_id}}

    started = time.perf_counter()
    result = await graph.ainvoke({"job": job, "segments": {}}, config, context=context)
    elapsed = time.perf_counter() - started

    print(f"segments: {job.segment_count}")
    print(f"elapsed:  {elapsed:.3f}s")
    print(f"per segment: {elapsed / job.segment_count * 1000:.1f}ms")
    assert result["job"].status.value == "succeeded"

    shutil.rmtree(RUN_ROOT)


if __name__ == "__main__":
    asyncio.run(main())
