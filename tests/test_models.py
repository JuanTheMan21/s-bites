"""T4's domain models, asserted where they are easy to get quietly wrong.

Three things here are worth a test rather than a review comment: that segment count is derived
from the requested length instead of assumed, that a segment can represent "not yet measured"
so an ordering violation is visible rather than plausible, and that the dependency between
``interfaces/`` and ``core/`` still runs the one direction D22 requires.
"""

import ast
from datetime import datetime
from pathlib import Path

import pytest

from core import (
    DEFAULT_TARGET_DURATION_MS,
    MIN_SEGMENTS,
    SECONDS_PER_SEGMENT,
    Importance,
    JobStatus,
    Outline,
    Segment,
    SegmentPlan,
    Tier,
    VideoJob,
    VisualIntent,
)
from core.render_outcome import RenderOutcome


def a_plan(**overrides: object) -> SegmentPlan:
    fields = {
        "title": "Parameterised queries",
        "summary": "Binding values separately means the parser never sees them as code.",
        "visual_intent": VisualIntent.CODE_WALKTHROUGH,
        "importance": Importance.CRITICAL,
    }
    fields.update(overrides)
    return SegmentPlan(**fields)  # type: ignore[arg-type]


# The numbers named in tasks.md T4, turned into assertions. A 10-minute request producing 21
# segments is the whole point of the flag: nothing may hardcode 15.
@pytest.mark.parametrize(
    "target_ms, expected",
    [
        (7 * 60 * 1000, 15),
        (10 * 60 * 1000, 21),
        (3 * 60 * 1000, 6),
        (30 * 1000, MIN_SEGMENTS),
        (0, MIN_SEGMENTS),
    ],
)
def test_segment_count_is_derived_from_target_duration(target_ms: int, expected: int) -> None:
    job = VideoJob(job_id="j", topic="sql injection", target_duration_ms=target_ms)
    assert job.segment_count == expected


def test_segment_count_scales_rather_than_holding_at_a_constant() -> None:
    """The failure this guards against is a longer video made of longer segments."""
    short = VideoJob(job_id="a", topic="t", target_duration_ms=5 * 60 * 1000)
    long = VideoJob(job_id="b", topic="t", target_duration_ms=20 * 60 * 1000)
    assert long.segment_count > short.segment_count * 3


def test_default_target_is_a_parameter_default_not_an_assumption() -> None:
    job = VideoJob(job_id="j", topic="t")
    assert job.target_duration_ms == DEFAULT_TARGET_DURATION_MS
    assert job.segment_count == round(DEFAULT_TARGET_DURATION_MS / 1000 / SECONDS_PER_SEGMENT)


def test_a_fresh_segment_is_unnarrated_unmeasured_and_untiered() -> None:
    """Invariant 1 is only checkable if "no duration yet" is representable."""
    segment = a_plan().to_segment(0)
    assert segment.index == 0
    assert segment.title == "Parameterised queries"
    assert segment.narration is None
    assert segment.duration_ms is None
    assert segment.tier is None
    assert segment.scene is None


def test_segment_plan_carries_no_timing_field_for_the_llm_to_fill() -> None:
    """Invariant 1 made structural: the model is never shown a duration to guess at."""
    assert "duration_ms" not in SegmentPlan.model_fields
    assert "tier" not in SegmentPlan.model_fields


def test_tier_is_ordered_so_the_resolver_can_compare_and_sum() -> None:
    assert Tier.STATIC < Tier.REVEAL < Tier.ANIMATED
    assert [int(t) for t in Tier] == [0, 1, 2]


def test_job_and_segments_survive_a_serialisation_round_trip() -> None:
    """They cross the LangGraph checkpoint in T14 and the HTTP boundary in T19."""
    job = VideoJob(
        job_id="job-1",
        topic="teach me about SQL injection",
        status=JobStatus.RUNNING,
        segments=[
            a_plan().to_segment(0),
            Segment(
                index=1,
                title="Impact",
                summary="What an attacker gets.",
                visual_intent=VisualIntent.STAT_CALLOUT,
                importance=Importance.MAJOR,
                narration="Roughly a fifth of breaches start here.",
                duration_ms=4200,
                tier=Tier.ANIMATED,
                scene={
                    "motif": "terminal",
                    "layout": "single",
                    "blocks": [
                        {
                            "block_type": "stat_callout",
                            "role": "role",
                            "anchor_phrase": None,
                            "payload": {
                                "value": "1 in 5",
                                "unit": None,
                                "context": "of breaches",
                                "value_number": None,
                                "prefix": None,
                                "suffix": None,
                            },
                        }
                    ],
                    "continues_previous": False,
                },
            ),
        ],
    )
    restored = VideoJob.model_validate_json(job.model_dump_json())
    assert restored == job
    assert restored.segments[1].tier is Tier.ANIMATED
    assert isinstance(restored.created_at, datetime)


def test_outline_wraps_the_list_because_strict_mode_needs_an_object_root() -> None:
    outline = Outline(segments=[a_plan(), a_plan(title="Impact")])
    assert Outline.model_json_schema()["type"] == "object"
    assert len(outline.segments) == 2


def test_pipeline_state_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        Segment.model_validate({**a_plan().model_dump(), "index": 0, "durationMs": 1000})


def test_a_fresh_segment_and_job_have_no_render_degradation_recorded() -> None:
    """T18I: absence, not a "clean" variant, is what says a segment/job needed nothing beyond
    its first render attempt -- see RenderOutcome's own docstring."""
    segment = a_plan().to_segment(0)
    job = VideoJob(job_id="j", topic="t")
    assert segment.render_outcome is None
    assert job.degraded_segments == []


def test_a_render_outcome_survives_the_same_serialisation_round_trip() -> None:
    """T18I: degraded_segments crosses the same LangGraph checkpoint / HTTP boundary as the rest
    of VideoJob (D14/T19) -- it must round-trip exactly like every other field here."""
    outcome = RenderOutcome(
        segment_index=1,
        attempts=2,
        finding_codes=["canvas_overflow"],
        reauthored=True,
        fallback_used=False,
        original_tier=2,
    )
    segment = (
        a_plan().to_segment(1).model_copy(update={"duration_ms": 4200, "render_outcome": outcome})
    )
    job = VideoJob(job_id="j", topic="t", segments=[segment], degraded_segments=[outcome])

    restored = VideoJob.model_validate_json(job.model_dump_json())

    assert restored == job
    assert restored.segments[0].render_outcome == outcome
    assert restored.degraded_segments == [outcome]


def test_interfaces_does_not_import_core() -> None:
    """D22, mechanically. T4 depends on T3; the reverse edge would be a cycle.

    A cycle introduced later is invisible in a diff and shows up as an import error in whichever
    module happened to be imported first, which is nowhere near the edit that caused it.
    """
    offenders = []
    for path in sorted(Path("interfaces").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "core":
                offenders.append(f"{path}: from {node.module} import ...")
            elif isinstance(node, ast.Import):
                offenders += [
                    f"{path}: import {n.name}" for n in node.names if n.name.split(".")[0] == "core"
                ]
    assert not offenders, f"interfaces/ imports core (D22): {offenders}"
