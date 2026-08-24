"""A per-call, isolated retry budget for ``StructuredOutputError``.

Exists because of a real LangGraph limitation, not a style preference -- see
``core/graph/retry_policy.py``'s docstring for the full account (D67). That module's node-level
``RetryPolicy`` shares one attempt counter across a whole node invocation, so a node making
several ``LLMProvider.generate`` calls (T15's outline call, plus one scripting call per segment)
cannot get each call its own ``StructuredOutputError`` budget from the graph-level policy alone --
a transient failure on an earlier call would already have spent shared budget a later call's
bounded retry gets checked against. This wraps one ``generate`` call in its own counter instead.

Any exception other than ``StructuredOutputError`` propagates immediately on the first attempt --
transient errors are the node-level ``RetryPolicy``'s job (a whole-node retry), not this helper's.

**A node using this must register with ``build_transient_retry_policy()``, not
``build_retry_policies()``.** If the node-level policy still matches ``StructuredOutputError`` too,
a call that exhausts *this* helper's budget re-raises into a policy that retries the entire node --
redoing every already-completed call inside it (the outline, and every other segment's narration)
just to re-attempt the one call that failed, for an error D24 says a retry was never going to fix.
That defeats the isolation this module exists to provide as surely as not having it at all; caught
by review on `plan.py`'s first version, which had made exactly this mistake.
"""

from interfaces import LLMProvider, StructuredOutputError
from interfaces.llm_provider import T


async def generate_with_bounded_retries(
    llm: LLMProvider,
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    max_attempts: int = 2,
) -> T:
    """Call ``llm.generate``, retrying only ``StructuredOutputError`` up to ``max_attempts``
    times total for this one call. Raises the last ``StructuredOutputError`` if every attempt
    fails; any other exception is raised on the first attempt, unretried."""
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")

    last_exc: StructuredOutputError | None = None
    for _ in range(max_attempts):
        try:
            return await llm.generate(prompt, schema, system=system)
        except StructuredOutputError as exc:
            last_exc = exc
    assert last_exc is not None  # max_attempts >= 1 is the only way to reach here
    raise last_exc
