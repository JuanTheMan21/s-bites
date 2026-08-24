"""``core/graph/nodes/plan.py::plan_segments`` -- T15's definition of done: structured output
validates on every segment, and the skill packs demonstrably change what gets asked of the model.

The ``StructuredOutputError`` isolation behaviour lives in ``test_plan_segments_retry.py`` --
split out once this file crossed the 200-line ceiling.
"""

from pathlib import Path

from core.models import Importance, VisualIntent
from core.outline_schema import Outline, SegmentPlan
from core.scripting_schema import Narration
from tests.fakes import FakeLLMProvider
from tests.plan_segments_fixtures import (
    a_context,
    a_job,
    a_skill_registry,
    an_outline,
    run_plan_segments,
)


async def test_the_outline_and_house_style_packs_reach_the_outline_call(tmp_path: Path) -> None:
    job = a_job()
    skills = a_skill_registry(
        outline="DISTINCTIVE OUTLINE TEXT", house_style="DISTINCTIVE HOUSE STYLE"
    )
    llm = FakeLLMProvider(
        [an_outline(job.segment_count)] + [Narration(text="x") for _ in range(job.segment_count)]
    )

    await run_plan_segments(job, a_context(skills, llm, tmp_path))

    outline_call = llm.calls[0]
    assert "DISTINCTIVE OUTLINE TEXT" in outline_call.prompt
    assert outline_call.system == "DISTINCTIVE HOUSE STYLE"


async def test_the_scripting_and_house_style_packs_reach_every_narration_call(
    tmp_path: Path,
) -> None:
    job = a_job()
    skills = a_skill_registry(
        scripting="DISTINCTIVE SCRIPTING TEXT", house_style="DISTINCTIVE HOUSE STYLE"
    )
    llm = FakeLLMProvider(
        [an_outline(job.segment_count)] + [Narration(text="x") for _ in range(job.segment_count)]
    )

    await run_plan_segments(job, a_context(skills, llm, tmp_path))

    narration_calls = llm.calls[1:]
    assert len(narration_calls) == job.segment_count
    for call in narration_calls:
        assert "DISTINCTIVE SCRIPTING TEXT" in call.prompt
        assert call.system == "DISTINCTIVE HOUSE STYLE"


async def test_exactly_one_outline_call_and_one_narration_call_per_segment(tmp_path: Path) -> None:
    job = a_job()
    llm = FakeLLMProvider(
        [an_outline(job.segment_count)] + [Narration(text="x") for _ in range(job.segment_count)]
    )

    await run_plan_segments(job, a_context(a_skill_registry(), llm, tmp_path))

    assert len(llm.calls) == 1 + job.segment_count
    assert llm.calls[0].schema is Outline
    assert all(call.schema is Narration for call in llm.calls[1:])


async def test_every_segment_carries_its_outline_fields_and_its_own_narration(
    tmp_path: Path,
) -> None:
    job = a_job()
    outline = Outline(
        segments=[
            SegmentPlan(
                title="Prepared statements",
                summary="Separating query from data",
                visual_intent=VisualIntent.CODE_WALKTHROUGH,
                importance=Importance.CRITICAL,
            ),
            SegmentPlan(
                title="A vulnerable query",
                summary="String concatenation lets data become code",
                visual_intent=VisualIntent.COMPARISON,
                importance=Importance.MAJOR,
            ),
        ]
    )
    llm = FakeLLMProvider(
        [outline, Narration(text="First narration."), Narration(text="Second narration.")]
    )
    # job.segment_count isn't asserted here (MIN_SEGMENTS=3 floors it regardless of this
    # duration) -- the queued 2-segment Outline is what actually drives generate_outline's
    # return value, independent of what the prompt asked for.
    job = job.model_copy(update={"target_duration_ms": 56_000})

    segments = await run_plan_segments(job, a_context(a_skill_registry(), llm, tmp_path))

    assert segments[0].title == "Prepared statements"
    assert segments[0].visual_intent is VisualIntent.CODE_WALKTHROUGH
    assert segments[0].importance is Importance.CRITICAL
    assert segments[0].narration == "First narration."
    assert segments[1].title == "A vulnerable query"
    assert segments[1].narration == "Second narration."
    # Neither the outline nor the narration call knows about duration/tier -- Invariant 1.
    assert segments[0].duration_ms is None
    assert segments[0].tier is None
