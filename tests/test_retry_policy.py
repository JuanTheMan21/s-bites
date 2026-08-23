"""Every ``interfaces/errors.py`` class, classified once so no future node re-derives it.

``build_retry_policies()`` returns two policies rather than one shared bound --
``StructuredOutputError`` gets a tighter cap than the unconditionally transient errors, per D24.
The bottom test pins a real, discovered-not-decided limit of that split: LangGraph's node-level
attempt counter is shared across a whole node invocation, not tracked per policy, so the caps are
only cleanly isolated when a node's failures stay within one classified family. See
``core/graph/retry_policy.py``'s docstring for the full explanation.
"""

from typing import TypedDict

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from core.graph.retry_policy import build_retry_policies, is_retryable
from interfaces import (
    CompositionInvalid,
    ObjectNotFound,
    ProviderMisconfigured,
    ProviderUnavailable,
    RateLimited,
    RenderFailed,
    SkillPackNotFound,
    StructuredOutputError,
)

RETRYABLE_CASES = [
    RateLimited("throttled"),
    ProviderUnavailable("unreachable"),
    RenderFailed("browser crashed"),
    StructuredOutputError("schema mismatch"),
]

NOT_RETRYABLE_CASES = [
    ProviderMisconfigured("bad credentials"),
    ObjectNotFound("missing key"),
    SkillPackNotFound("missing pack"),
    CompositionInvalid("bad markup"),
]


@pytest.mark.parametrize("exc", RETRYABLE_CASES, ids=lambda e: type(e).__name__)
def test_transient_and_bounded_errors_are_retryable(exc: Exception) -> None:
    assert is_retryable(exc) is True


@pytest.mark.parametrize("exc", NOT_RETRYABLE_CASES, ids=lambda e: type(e).__name__)
def test_errors_that_will_never_succeed_are_not_retryable(exc: Exception) -> None:
    """Retrying these only spends the attempt budget arriving at the message the first
    attempt already had."""
    assert is_retryable(exc) is False


def test_each_retryable_class_matches_exactly_one_policy() -> None:
    """Every retryable exception must be claimed by exactly one of the two policies -- two
    matches would make LangGraph's "first match wins" order load-bearing in a way nothing
    documents, and zero matches would mean is_retryable() and the policies have drifted apart."""
    policies = build_retry_policies()

    for exc in RETRYABLE_CASES:
        matches = [policy for policy in policies if policy.retry_on(exc)]
        assert len(matches) == 1, f"{type(exc).__name__} matched {len(matches)} policies"


def test_never_retried_errors_match_no_policy() -> None:
    policies = build_retry_policies()

    for exc in NOT_RETRYABLE_CASES:
        assert not any(policy.retry_on(exc) for policy in policies)


def test_structured_output_error_gets_a_tighter_cap_than_transient_errors() -> None:
    """The whole point of splitting the policy: sampling noise gets more tries than a schema the
    model consistently cannot satisfy."""
    transient_policy, bounded_policy = build_retry_policies(
        transient_max_attempts=5, structured_output_max_attempts=2
    )

    assert transient_policy.retry_on(RateLimited("throttled")) is True
    assert transient_policy.retry_on(StructuredOutputError("bad json")) is False
    assert transient_policy.max_attempts == 5

    assert bounded_policy.retry_on(StructuredOutputError("bad json")) is True
    assert bounded_policy.retry_on(RateLimited("throttled")) is False
    assert bounded_policy.max_attempts == 2


class _State(TypedDict):
    pass


async def test_a_prior_transient_failure_eats_into_the_bounded_policys_own_budget() -> None:
    """Pins the shared-counter limit the module docstring warns about: a node whose *first*
    failure is transient and whose *second* is a StructuredOutputError gets only one shot at the
    bounded error, not the two its own max_attempts promises in isolation -- because LangGraph
    checks one shared per-invocation counter against whichever policy matches the current
    failure, not a counter kept per policy.

    This is discovered LangGraph behaviour, not a choice made in this module -- pinned here so a
    future LangGraph upgrade or a reader's optimistic assumption doesn't quietly rely on
    isolation this mechanism does not provide.
    """
    calls = 0

    async def flaky(state: _State, runtime: Runtime) -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProviderUnavailable("first attempt: transient")
        raise StructuredOutputError("every attempt after: bounded")

    builder = StateGraph(_State)
    builder.add_node("flaky", flaky, retry_policy=build_retry_policies())
    builder.add_edge(START, "flaky")
    builder.add_edge("flaky", END)
    graph = builder.compile()

    with pytest.raises(StructuredOutputError):
        await graph.ainvoke({})

    # A StructuredOutputError seen for the first time, on its own, would get
    # structured_output_max_attempts (2) tries. Here it gets only one, because the prior
    # transient failure already spent one unit of the shared counter.
    assert calls == 2
