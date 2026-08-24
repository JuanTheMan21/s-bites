"""``core.graph.nodes.structured_retry``: an isolated retry budget for ``StructuredOutputError``,
kept separate from ``core/graph/retry_policy.py``'s node-level policy per D67's shared-counter
limitation."""

import pytest
from pydantic import BaseModel

from core.graph.nodes.structured_retry import generate_with_bounded_retries
from interfaces import ProviderUnavailable, StructuredOutputError
from tests.fakes import FakeLLMProvider


class _Schema(BaseModel):
    value: str


async def test_succeeds_on_the_first_attempt_with_no_retry() -> None:
    llm = FakeLLMProvider([_Schema(value="ok")])

    result = await generate_with_bounded_retries(llm, "prompt", _Schema)

    assert result.value == "ok"
    assert len(llm.calls) == 1


async def test_retries_a_structured_output_error_within_budget() -> None:
    llm = FakeLLMProvider([_Schema(value="ok")])
    llm.fail_next("generate", StructuredOutputError("bad json"))

    result = await generate_with_bounded_retries(llm, "prompt", _Schema, max_attempts=2)

    assert result.value == "ok"
    # The failed attempt raises before FakeLLMProvider logs it (D68's gotcha) -- only the
    # eventual success is recorded.
    assert len(llm.calls) == 1


async def test_exhausting_the_budget_re_raises_the_structured_output_error() -> None:
    llm = FakeLLMProvider([_Schema(value="never reached")])
    llm.fail_next("generate", StructuredOutputError("bad json"), times=2)

    with pytest.raises(StructuredOutputError):
        await generate_with_bounded_retries(llm, "prompt", _Schema, max_attempts=2)


async def test_a_non_structured_output_error_propagates_without_being_retried() -> None:
    llm = FakeLLMProvider([_Schema(value="never reached")])
    llm.fail_next("generate", ProviderUnavailable("down"))

    with pytest.raises(ProviderUnavailable):
        await generate_with_bounded_retries(llm, "prompt", _Schema, max_attempts=2)


async def test_max_attempts_below_one_is_rejected() -> None:
    llm = FakeLLMProvider([_Schema(value="never reached")])

    with pytest.raises(ValueError, match="max_attempts"):
        await generate_with_bounded_retries(llm, "prompt", _Schema, max_attempts=0)
