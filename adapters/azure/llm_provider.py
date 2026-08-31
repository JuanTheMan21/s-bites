"""``LLMProvider`` backed by Azure OpenAI, with strict ``json_schema`` structured output.

Everything vendor-specific stops here: the SDK client, the retry policy, the concurrency bound
and the exception translation. ``core/`` calls ``generate`` and receives a validated model
instance or one of the errors in ``interfaces/errors.py`` -- never a string that might be JSON,
and never an ``openai`` type.

**Strict mode is the point of taking a pydantic class rather than a JSON Schema dict.** The SDK
emits the class as a ``json_schema`` response format with ``strict: true``, which constrains
*generation* so the model cannot emit a token that violates the schema. The response is valid by
construction rather than valid on inspection. That is also why ``core/strict_schema.py`` exists
and why its conformance test is worth its weight -- a schema outside the supported subset is a
400 at call time, not an import error.

**The SDK's own retries are switched off** (``max_retries=0``) so this class owns the policy
outright. Leaving them on nests two independent retry loops, and the effective attempt count
becomes their product -- which is how a "4 attempt" bound quietly becomes twelve, and how a rate
limit takes minutes to surface instead of seconds.

Verified against the live deployment during T8: ``gpt-5.4-mini`` on ``DataZoneStandard`` serves
strict ``json_schema`` on api-version ``2024-10-21``.
"""

import asyncio
import logging

import openai
from openai import AsyncAzureOpenAI
from tenacity import AsyncRetrying, RetryCallState, stop_after_attempt, wait_exponential_jitter

from adapters.azure.openai_errors import translate
from interfaces import AdapterError, LLMProvider, StructuredOutputError
from interfaces.llm_provider import T

logger = logging.getLogger(__name__)

# What is worth trying again, and nothing else. A 400, a 401 and a 404 all reproduce exactly.
RETRYABLE = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)

MAX_BACKOFF_S = 30.0


class AzureOpenAILLMProvider(LLMProvider):
    """Structured generation through one Azure OpenAI deployment.

    Constructor arguments are explicit rather than read from the environment: ``config.py`` is
    the only module permitted to know which adapter is active, and an adapter that reads
    ``os.environ`` itself makes T13 a formality that proves nothing.

    ``max_concurrency`` bounds the per-segment fan-out. T16 narrates and authors ~15 segments,
    and an unbounded ``asyncio.gather`` over them turns a deployment's TPM allowance into a wall
    of 429s -- so the bound belongs here, in the adapter that knows what the deployment can take,
    rather than in the graph that does not.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str,
        *,
        max_concurrency: int = 4,
        max_attempts: int = 4,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError(f"max_concurrency must be at least 1, got {max_concurrency}")
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")

        self.deployment = deployment
        self.max_attempts = max_attempts
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            max_retries=0,  # this class owns the retry policy; see the module docstring
        )
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def generate(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        retryer = AsyncRetrying(
            stop=stop_after_attempt(self.max_attempts),
            wait=self._wait,
            retry=_is_retryable,
            reraise=True,  # surface the vendor exception so translate() can classify it
            before_sleep=_log_before_sleep,
        )
        async with self._semaphore:
            try:
                return await retryer(self._parse, prompt, schema, system)
            except AdapterError:
                # Already ours -- _parse raises StructuredOutputError directly for a refusal or
                # a truncated body. Re-translating would run it through the unrecognised-failure
                # fallback and relabel a schema problem as an outage.
                raise
            except Exception as exc:
                raise translate(exc) from exc

    async def _parse(self, prompt: str, schema: type[T], system: str | None) -> T:
        """One attempt. Raises the vendor exception, or ``StructuredOutputError`` for a bad body."""
        messages: list[dict[str, str]] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # No temperature: gpt-5.x reasoning deployments reject a non-default value, and the 400
        # it returns reads like a schema rejection. Sampling defaults are the deployment's.
        completion = await self._client.chat.completions.parse(
            model=self.deployment,
            messages=messages,  # type: ignore[arg-type]
            response_format=schema,
        )

        choice = completion.choices[0]
        if choice.message.refusal is not None:
            raise StructuredOutputError(
                f"the model refused a {schema.__name__} request: {choice.message.refusal}"
            )
        if choice.finish_reason == "length":
            raise StructuredOutputError(
                f"the {schema.__name__} response was cut off at the token limit before it was "
                "complete; the object is truncated rather than invalid"
            )
        if choice.message.parsed is None:
            raise StructuredOutputError(
                f"the model returned no parsable {schema.__name__} body "
                f"(finish_reason={choice.finish_reason!r})"
            )
        return choice.message.parsed

    def _wait(self, state: RetryCallState) -> float:
        """Exponential backoff, floored by ``Retry-After`` when the backend sent one.

        Backing off less than the header asks for wastes an attempt on a request the service has
        already said it will refuse. Taking the maximum honours the header without letting a
        wildly large one stall a job indefinitely -- the attempt cap still bounds the total.
        """
        backoff = wait_exponential_jitter(initial=1.0, max=MAX_BACKOFF_S)(state)
        return max(backoff, _retry_after_s(state))

    async def aclose(self) -> None:
        """Release the underlying HTTP connection pool.

        Not on the ``LLMProvider`` contract: an in-memory fake has nothing to close, and adding
        it to the interface would oblige every implementation to grow a no-op. The owner of the
        instance -- ``config.py`` at T13, the FastAPI lifespan at T19 -- calls this.
        """
        await self._client.close()


def _is_retryable(state: RetryCallState) -> bool:
    exc = state.outcome.exception() if state.outcome else None
    return isinstance(exc, RETRYABLE)


def _log_before_sleep(state: RetryCallState) -> None:
    """T18E, D121/D122: a ~216s silent gap between two LLM calls in one T18D render was almost
    certainly retry/backoff stacking, and nothing logged enough to say so for certain. This is
    the log line that would have -- attempt number, what failed, and how long the computed
    backoff (``_wait``, floored by any ``Retry-After`` header) is about to sleep for."""
    exc = state.outcome.exception() if state.outcome else None
    sleep_s = state.next_action.sleep if state.next_action else 0.0
    logger.warning(
        "llm call retry: attempt %d failed with %s, sleeping %.2fs before the next attempt",
        state.attempt_number,
        type(exc).__name__ if exc else "unknown error",
        sleep_s,
    )


def _retry_after_s(state: RetryCallState) -> float:
    """Seconds the backend asked us to wait, or 0 if it did not ask."""
    exc = state.outcome.exception() if state.outcome else None
    response = getattr(exc, "response", None)
    header = getattr(response, "headers", {}).get("retry-after") if response else None
    try:
        return min(float(header), MAX_BACKOFF_S) if header else 0.0
    except (TypeError, ValueError):
        # Retry-After may legitimately be an HTTP date rather than a count of seconds. Falling
        # back to plain backoff is better than failing to retry over a header format.
        return 0.0
