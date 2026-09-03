"""``core/graph/nodes/tiering.py::assign_tiers`` -- the join node that turns measured durations
into render tiers.

The resolver itself is exhaustively tested next door in ``tests/test_tier_resolver.py``, and the
budget scaling in ``tests/test_frame_budget.py``. What is tested here is only what the *node* adds:
that it reaches the resolver with the scaled budget and the context's frame rate, that it writes
every tier back onto the segments, and that an unmeasured segment still stops the run.
"""

from pathlib import Path

import pytest
from langgraph.graph import END, START, StateGraph

from core.graph import GraphContext, GraphState
from core.graph.nodes.tiering import assign_tiers
from core.models import DEFAULT_TARGET_DURATION_MS, Segment, Tier
from core.video_job import VideoJob
from tests.fakes import (
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)
from tests.segment_examples import a_segment, seven_minute_segments

FRAME_BUDGET = 600  # the .env base, calibrated for a DEFAULT_TARGET_DURATION_MS video
FPS = 24


def a_context(tmp_path: Path, *, frame_budget: int = FRAME_BUDGET, fps: int = FPS) -> GraphContext:
    """This node touches neither the LLM, TTS, storage nor the renderer -- only the two numbers."""
    return GraphContext(
        llm=FakeLLMProvider(),
        tts=FakeTTSProvider(),
        storage=FakeStorage(),
        skills=FakeSkillRegistry(),
        render=FakeRenderBackend(),
        working_dir=tmp_path / "work",
        frame_budget=frame_budget,
        fps=fps,
    )


async def run_assign_tiers(
    segments: list[Segment], context: GraphContext, *, target_duration_ms: int
) -> dict[int, Segment]:
    """One-node graph, matching pipeline.py's real registration: no retry policy, because this
    node reaches nothing outside the process and its only error is one a retry cannot fix."""
    builder = StateGraph(GraphState, context_schema=GraphContext)
    builder.add_node("assign_tiers", assign_tiers)
    builder.add_edge(START, "assign_tiers")
    builder.add_edge("assign_tiers", END)
    graph = builder.compile()

    job = VideoJob(job_id="job-1", topic="SQL injection", target_duration_ms=target_duration_ms)
    state = {"job": job, "segments": {segment.index: segment for segment in segments}}
    result = await graph.ainvoke(state, context=context)
    return result["segments"]


async def test_every_segment_comes_back_with_a_tier(tmp_path: Path) -> None:
    segments = seven_minute_segments()

    tiered = await run_assign_tiers(
        segments, a_context(tmp_path), target_duration_ms=DEFAULT_TARGET_DURATION_MS
    )

    assert len(tiered) == len(segments)
    assert all(segment.tier is not None for segment in tiered.values())
    # Nothing else on the segment is touched -- this node adds a tier, it does not re-plan.
    assert all(tiered[s.index].narration == s.narration for s in segments)
    assert all(tiered[s.index].duration_ms == s.duration_ms for s in segments)


async def test_the_budget_is_scaled_by_the_jobs_requested_length(tmp_path: Path) -> None:
    """``scale_frame_budget`` is why this node takes the *base* budget rather than a final one:
    the same segments must not be squeezed into a seven-minute video's render time just because
    the job asked for fourteen minutes of them.

    Asserted as an identity rather than as "more Tier 2", because more budget does not
    necessarily mean *more* animated segments -- at 1200 frames the resolver spends its extra
    budget promoting one long, important segment and demoting a short one, so the spread's
    *counts* are unchanged while the assignment is not. Doubling the length must therefore land
    exactly where doubling the base budget lands, and somewhere the base budget does not.
    """
    segments = seven_minute_segments()

    def tiers(tiered: dict[int, Segment]) -> dict[int, Tier | None]:
        return {index: segment.tier for index, segment in tiered.items()}

    at_base = await run_assign_tiers(
        segments, a_context(tmp_path), target_duration_ms=DEFAULT_TARGET_DURATION_MS
    )
    at_double_length = await run_assign_tiers(
        segments, a_context(tmp_path), target_duration_ms=2 * DEFAULT_TARGET_DURATION_MS
    )
    at_double_base = await run_assign_tiers(
        segments,
        a_context(tmp_path, frame_budget=2 * FRAME_BUDGET),
        target_duration_ms=DEFAULT_TARGET_DURATION_MS,
    )

    assert tiers(at_double_length) == tiers(at_double_base)
    assert tiers(at_double_length) != tiers(at_base)


async def test_the_context_frame_rate_is_what_tier_2_is_costed_against(tmp_path: Path) -> None:
    """Tier 2 costs duration x fps, so the same budget buys fewer animations at a higher frame
    rate. A node that hardcoded 24 rather than reading the context would pass every other test
    here and silently mis-cost every real run configured otherwise."""
    segments = seven_minute_segments()

    at_24 = await run_assign_tiers(
        segments, a_context(tmp_path, fps=24), target_duration_ms=DEFAULT_TARGET_DURATION_MS
    )
    at_60 = await run_assign_tiers(
        segments, a_context(tmp_path, fps=60), target_duration_ms=DEFAULT_TARGET_DURATION_MS
    )

    animated_at_24 = sum(1 for s in at_24.values() if s.tier is Tier.ANIMATED)
    animated_at_60 = sum(1 for s in at_60.values() if s.tier is Tier.ANIMATED)
    assert animated_at_60 < animated_at_24


async def test_an_unmeasured_segment_stops_the_run(tmp_path: Path) -> None:
    """Invariant 1, at the point it would otherwise be violated. The message comes from
    ``resolve_tiers`` itself and is deliberately not re-wrapped -- it already explains that an
    unmeasured segment looks free and spends the budget on nothing."""
    segments = [a_segment(0), a_segment(1, duration_ms=None), a_segment(2)]

    with pytest.raises(ValueError, match="no measured duration_ms"):
        await run_assign_tiers(
            segments, a_context(tmp_path), target_duration_ms=DEFAULT_TARGET_DURATION_MS
        )
