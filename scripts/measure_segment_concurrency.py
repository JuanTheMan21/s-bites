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

T18B: every segment plans as a single TITLE block (``scene_plan``/``slot_payloads``, the same
interchangeable-payload trick ``tests/graph_pipeline_fixtures.py`` uses) -- the call sequence a
real run makes now includes ``plan_visuals``' one whole-video call between narration and the
per-segment scene-authoring fan-out.
"""

import asyncio
import shutil
import time
from pathlib import Path

from adapters.local.storage import DiskStorage
from core.block_schemas import TitleSlots
from core.block_types import BlockType, MotifName, SceneLayout
from core.graph import GraphContext, build_graph
from core.models import Importance, VideoJob, VisualIntent
from core.outline_schema import Outline, SegmentPlan
from core.scene_plan_schema import PlannedBlock, SegmentScenePlan, VideoScenePlan
from core.scripting_schema import Narration
from interfaces import SkillPack
from tests.fakes import FakeLLMProvider, FakeRenderBackend, FakeSkillRegistry, FakeTTSProvider

SEGMENT_COUNT_TARGET_MS = 15 * 28 * 1000  # ~15 segments, a realistic 7-minute job
RUN_ROOT = Path("artifacts") / "_measure_segment_concurrency"

# Zero, not the .env default -- same reasoning as tests/graph_pipeline_fixtures.py's identical
# choice. FakeTTSProvider() below is given no explicit durations, so it estimates each segment's
# length from its (very short) synthetic narration text -- cheap enough that, post-D99's IDEAL_TIER
# correction (NORMAL importance now targets Tier.ANIMATED), a nonzero budget promotes some segments
# there. FakeRenderBackend.render() writes placeholder bytes, not a real MP4, so render_scene's real
# ffmpeg mux fails on whichever segment lands on Tier 2 -- found live, not assumed, when this
# script's own T18B-era import fix let it run far enough to hit it for the first time. Budget=0
# keeps every segment on Tier 0 deterministically, which this script's actual subject (disk I/O
# contention under concurrency) does not need tier variety to measure anyway.
FRAME_BUDGET = 0
FPS = 24


def _seeded_skills() -> FakeSkillRegistry:
    """Every pack the graph's five LLM-calling steps load. Content is irrelevant to a timing run."""
    return FakeSkillRegistry(
        [
            SkillPack(name=name, version="1.0", content=f"{name} pack")
            for name in ("outline", "scripting", "visual-plan", "house-style", "scene-authoring")
        ]
    )


def _seeded_llm(segment_count: int) -> FakeLLMProvider:
    """One outline, one narration per segment, one whole-video scene plan, one block-fill payload
    per segment -- the exact call sequence a real run makes. Every segment plans as a single TITLE
    block, so the fill payloads are interchangeable and the concurrent ``author_scene`` tasks may
    pop them in any order."""
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
    plan = VideoScenePlan(
        motif=MotifName.TERMINAL,
        segments=[
            SegmentScenePlan(
                segment_index=i,
                layout=SceneLayout.SINGLE,
                blocks=[PlannedBlock(block_type=BlockType.TITLE, role="Title", anchor_phrase=None)],
                continues_previous=False,
                annotations=[],
            )
            for i in range(segment_count)
        ],
    )
    slots = [TitleSlots(headline=f"Headline {i}", subtitle=None) for i in range(segment_count)]
    return FakeLLMProvider([outline, *narrations, plan, *slots])


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
