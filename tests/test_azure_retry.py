"""T9's "survives an induced rate-limit response", induced offline.

Provoking a real 429 means hammering a live deployment until it complains: slow, billable,
flaky, and it proves one branch. A stub client raises exactly the sequence the test is about, so
"retries three times then gives up as ``RateLimited``" becomes an assertion instead of an
anecdote -- and it runs on every edit rather than only when someone remembers to pass ``-m live``.

What is checked here is the adapter's own policy, which is the part that is ours: how many
attempts, what is retried at all, whether the vendor type escapes, and whether ``Retry-After`` is
honoured. Whether Azure really sends a 429 is Azure's business.
"""

from dataclasses import dataclass, field

import httpx
import openai
import pytest
from tenacity import RetryCallState

from adapters.azure.llm_provider import (
    MAX_BACKOFF_S,
    AzureOpenAILLMProvider,
    _is_retryable,
    _retry_after_s,
)
from core.models import Importance, VisualIntent
from core.outline_schema import Outline, SegmentPlan
from interfaces import ProviderMisconfigured, RateLimited, StructuredOutputError


def an_outline() -> Outline:
    """A plausible response. Its contents do not matter; that it is the right *type* does."""
    return Outline(
        segments=[
            SegmentPlan(
                title="What SQL injection is",
                summary="Data supplied by a user gets executed as part of a query.",
                visual_intent=VisualIntent.DIAGRAM_FLOW,
                importance=Importance.CRITICAL,
            )
        ]
    )


def a_provider(max_attempts: int = 3) -> AzureOpenAILLMProvider:
    """Credentials that are never used: every test here replaces the call before it happens."""
    return AzureOpenAILLMProvider(
        endpoint="https://skill-bites.cognitiveservices.azure.com/",
        api_key="not-a-real-key",
        deployment="gpt-5.4-mini",
        api_version="2024-10-21",
        max_attempts=max_attempts,
    )


def rate_limited(retry_after: str | None = None) -> openai.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    return openai.RateLimitError(
        message="Requests to the ChatCompletions Operation have exceeded token rate limit",
        response=httpx.Response(429, request=httpx.Request("POST", "https://x/"), headers=headers),
        body=None,
    )


@dataclass
class StubParse:
    """Stands in for ``_parse``: raises the queued failures, then returns the queued result."""

    failures: list[Exception]
    result: Outline | None = None
    calls: int = field(default=0)

    async def __call__(self, prompt: str, schema: type, system: str | None) -> Outline:
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        assert self.result is not None
        return self.result


@pytest.fixture
def no_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backoff is real and tested separately; here it would only make the suite slow."""
    monkeypatch.setattr(AzureOpenAILLMProvider, "_wait", lambda self, state: 0.0)


async def test_a_transient_rate_limit_is_survived(no_waiting: None) -> None:
    provider = a_provider(max_attempts=3)
    stub = StubParse(failures=[rate_limited(), rate_limited()], result=an_outline())
    provider._parse = stub  # type: ignore[method-assign]

    assert await provider.generate("topic", Outline) is stub.result
    assert stub.calls == 3


async def test_attempts_are_capped_and_the_vendor_type_never_escapes(no_waiting: None) -> None:
    """The bound matters as much as the retry: an uncapped 429 loop is an unbounded bill."""
    provider = a_provider(max_attempts=3)
    stub = StubParse(failures=[rate_limited() for _ in range(5)])
    provider._parse = stub  # type: ignore[method-assign]

    with pytest.raises(RateLimited):
        await provider.generate("topic", Outline)
    assert stub.calls == 3


async def test_a_misconfiguration_is_not_retried(no_waiting: None) -> None:
    """A 401 reproduces exactly, so retrying it spends attempts to re-learn the same fact."""
    provider = a_provider(max_attempts=3)
    stub = StubParse(
        failures=[
            openai.AuthenticationError(
                message="Access denied due to invalid subscription key",
                response=httpx.Response(401, request=httpx.Request("POST", "https://x/")),
                body=None,
            )
        ]
    )
    provider._parse = stub  # type: ignore[method-assign]

    with pytest.raises(ProviderMisconfigured):
        await provider.generate("topic", Outline)
    assert stub.calls == 1


async def test_our_own_structured_output_error_passes_through_unchanged(no_waiting: None) -> None:
    """The trap in ``generate``'s except clause.

    ``_parse`` raises ``StructuredOutputError`` itself for a refusal or a truncated body. Handing
    that to ``translate`` would run it through the unrecognised-failure fallback and relabel a
    schema problem as an outage -- inverting its retry answer from "bounded" to "may help".
    """
    provider = a_provider()
    provider._parse = StubParse(failures=[StructuredOutputError("the model refused")])  # type: ignore[method-assign]

    with pytest.raises(StructuredOutputError, match="refused"):
        await provider.generate("topic", Outline)


def a_state(exc: Exception) -> RetryCallState:
    state = RetryCallState(retry_object=None, fn=None, args=(), kwargs={})
    state.set_exception((type(exc), exc, exc.__traceback__))
    return state


def test_retry_after_is_honoured_when_the_backend_sends_one() -> None:
    """Backing off less than the header asks wastes an attempt on a refusal already promised."""
    assert _retry_after_s(a_state(rate_limited(retry_after="7"))) == 7.0


def test_a_retry_after_header_cannot_stall_a_job_indefinitely() -> None:
    assert _retry_after_s(a_state(rate_limited(retry_after="99999"))) == MAX_BACKOFF_S


def test_an_http_date_retry_after_falls_back_to_plain_backoff() -> None:
    """Retry-After may legitimately be a date. Not retrying over a header format would be worse."""
    assert _retry_after_s(a_state(rate_limited(retry_after="Wed, 21 Oct 2026 07:28:00 GMT"))) == 0.0


def test_a_missing_retry_after_is_not_an_error() -> None:
    assert _retry_after_s(a_state(rate_limited())) == 0.0


@pytest.mark.parametrize(
    "exc, retryable",
    [
        (rate_limited(), True),
        (openai.APITimeoutError(request=httpx.Request("POST", "https://x/")), True),
        (
            openai.BadRequestError(
                message="bad",
                response=httpx.Response(400, request=httpx.Request("POST", "https://x/")),
                body=None,
            ),
            False,
        ),
    ],
    ids=["429", "timeout", "400"],
)
def test_only_transient_failures_are_retried(exc: Exception, retryable: bool) -> None:
    assert _is_retryable(a_state(exc)) is retryable
