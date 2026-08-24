"""``core/graph/nodes/plan.py::plan_segments``'s ``StructuredOutputError`` isolation -- the reason
``core/graph/nodes/structured_retry.py`` exists (D67), split out from ``test_plan_segments.py``
once that file crossed the 200-line ceiling.
"""

from pathlib import Path

import pytest

from core.scripting_schema import Narration
from interfaces import StructuredOutputError
from tests.fakes import FakeLLMProvider
from tests.plan_segments_fixtures import (
    a_context,
    a_job,
    a_skill_registry,
    an_outline,
    run_plan_segments,
)


async def test_a_structured_output_error_recovers_locally_without_re_running_the_whole_node(
    tmp_path: Path,
) -> None:
    """Each ``LLMProvider.generate`` call this node makes (the outline call, and one per
    segment's narration) gets its own isolated ``StructuredOutputError`` retry budget, so a
    single bad sample recovers on the spot instead of ever reaching ``plan_segments``'s
    node-level ``RetryPolicy`` -- which would otherwise redo the outline *and* every other
    segment's narration just to retry the one call that failed.
    """
    # job.segment_count isn't asserted here (MIN_SEGMENTS=3 floors it regardless of this
    # duration) -- the queued 1-segment Outline is what actually drives generate_outline's
    # return value, independent of what the prompt asked for.
    job = a_job().model_copy(update={"target_duration_ms": 28_000})
    llm = FakeLLMProvider([an_outline(1), Narration(text="Recovered narration.")])
    llm.fail_next("generate", StructuredOutputError("one bad sample"))

    segments = await run_plan_segments(job, a_context(a_skill_registry(), llm, tmp_path))

    assert segments[0].narration == "Recovered narration."
    # 2 logged calls (the failed attempt raises before being logged, per D68) -- proof the whole
    # node never re-ran: a whole-node retry would have logged a second outline call too.
    assert len(llm.calls) == 2


async def test_a_persistent_structured_output_error_propagates_without_redoing_the_whole_node(
    tmp_path: Path,
) -> None:
    """The exact bug review caught in this task's first version: ``plan_segments`` was registered
    with ``build_retry_policies()`` (both policies), so once a call's local retry budget was
    exhausted, the re-raised ``StructuredOutputError`` matched the node-level bounded policy too
    and retried the **entire node** -- silently redoing the outline call from scratch (D24: a
    schema the model consistently cannot satisfy is a prompt bug that a redo cannot fix, but the
    old wiring redid it anyway, once, and happened to succeed the second time since no more
    failures were armed -- masking the bug rather than surfacing it as a raised exception).

    With ``build_transient_retry_policy()`` (the fix, in ``tests/plan_segments_fixtures.py`` and
    ``core/graph/pipeline.py``), the node-level policy no longer matches ``StructuredOutputError``
    at all, so once the outline call's own local budget is exhausted, it propagates for good --
    this test fails with "DID NOT RAISE" against the old, buggy wiring.
    """
    # job.segment_count isn't asserted here (MIN_SEGMENTS=3 floors it regardless of this
    # duration) -- the queued 1-segment Outline is what actually drives generate_outline's
    # return value, independent of what the prompt asked for.
    job = a_job().model_copy(update={"target_duration_ms": 28_000})
    llm = FakeLLMProvider([an_outline(1), Narration(text="never reached if this test passes")])
    # The outline call is the first generate() invocation, so these two armed failures exhaust
    # structured_retry.py's default max_attempts=2 local budget on it specifically.
    llm.fail_next(
        "generate", StructuredOutputError("this call can never satisfy the schema"), times=2
    )

    with pytest.raises(StructuredOutputError):
        await run_plan_segments(job, a_context(a_skill_registry(), llm, tmp_path))

    # Zero logged calls: both attempts failed before ever being logged (D68). A whole-node redo
    # (the bug) would have consumed the queued outline and narration responses instead, and this
    # would be 2 -- and the pytest.raises above would have failed with "DID NOT RAISE" first.
    assert len(llm.calls) == 0
