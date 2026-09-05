"""Shared setup for ``test_plan_segments.py`` and ``test_plan_segments_retry.py``: a believable
job, seeded skill packs, and a minimal one-node graph running ``plan_segments`` in isolation.

Not a test module -- the same role ``tests/segment_examples.py`` plays for ``Segment`` fixtures.
"""

from pathlib import Path

from langgraph.graph import END, START, StateGraph

from core.graph import GraphContext, GraphState
from core.graph.nodes.plan import plan_segments
from core.graph.retry_policy import build_transient_retry_policy
from core.models import Importance, Segment, VisualIntent
from core.outline_schema import Outline, SegmentPlan
from core.video_job import VideoJob
from interfaces import SkillPack
from tests.fakes import (
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)

TARGET_DURATION_MS = 100_000  # round(100_000 / 1000 / 28) == 4 segments


def a_job() -> VideoJob:
    return VideoJob(job_id="job-1", topic="SQL injection", target_duration_ms=TARGET_DURATION_MS)


def a_skill_registry(
    *,
    outline: str = "OUTLINE PACK",
    scripting: str = "SCRIPTING PACK",
    house_style: str = "HOUSE STYLE PACK",
) -> FakeSkillRegistry:
    return FakeSkillRegistry(
        [
            SkillPack(name="outline", version="1.0", content=outline),
            SkillPack(name="scripting", version="1.0", content=scripting),
            SkillPack(name="house-style", version="1.0", content=house_style),
        ]
    )


def a_context(skills: FakeSkillRegistry, llm: FakeLLMProvider, tmp_path: Path) -> GraphContext:
    return GraphContext(
        llm=llm,
        tts=FakeTTSProvider(),
        storage=FakeStorage(),
        skills=skills,
        render=FakeRenderBackend(),
        working_dir=tmp_path / "work",
        frame_budget=600,
        fps=24,
    )


def an_outline(count: int) -> Outline:
    return Outline(
        segments=[
            SegmentPlan(
                title=f"Title {i}",
                summary=f"Summary {i}",
                visual_intent=VisualIntent.TITLE_CARD,
                importance=Importance.NORMAL,
            )
            for i in range(count)
        ]
    )


async def run_plan_segments(job: VideoJob, context: GraphContext) -> dict[int, Segment]:
    # Matches core/graph/pipeline.py's real registration: build_transient_retry_policy(), not
    # build_retry_policies() -- plan_segments isolates its own StructuredOutputError retries
    # internally (structured_retry.py), so the node-level policy here must not also match that
    # error, or an exhausted local retry would re-trigger a whole-node redo of the same failure.
    builder = StateGraph(GraphState, context_schema=GraphContext)
    builder.add_node("plan_segments", plan_segments, retry_policy=build_transient_retry_policy())
    builder.add_edge(START, "plan_segments")
    builder.add_edge("plan_segments", END)
    graph = builder.compile()

    result = await graph.ainvoke({"job": job, "segments": {}}, context=context)
    return result["segments"]
