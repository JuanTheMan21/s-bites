"""The retry classifier D24 left open: which ``interfaces/errors.py`` exceptions are worth a
retry, and how many.

**Two policies, with a caveat that is documented rather than glossed over.**
``StateGraph.add_node``'s ``retry_policy`` accepts a ``Sequence[RetryPolicy]``, and LangGraph's
runner (``langgraph/pregel/_retry.py``) picks the *first* policy in the sequence whose ``retry_on``
matches the raised exception and checks *that policy's* ``max_attempts`` -- so "may help"
(``RateLimited``, ``ProviderUnavailable``, ``RenderFailed``) and "may help, but bounded"
(``StructuredOutputError``) can be given different caps in the common case, where a single node
invocation's failures are consistently one classified family.

**What is not true, and was wrongly claimed in an earlier version of this docstring (caught by
review, then re-checked against the installed ``langgraph`` source and empirically confirmed):**
the caps are not *independent* budgets. LangGraph keeps one ``attempts`` counter for the whole
node invocation, incremented on every failure regardless of which policy matched, and only ever
checks that **shared** counter against whichever policy matched the *current* exception. So if a
node's failures span both families within one invocation -- one transient error, then a run of
``StructuredOutputError`` -- the transient failure has already spent a unit of the shared counter
before the bounded error is ever seen, and the bounded policy's cap is checked against that
already-advanced total. In the worst case a ``StructuredOutputError`` that shows up after enough
prior failures of any other retryable type gets zero further retries of itself, regardless of its
own configured ``max_attempts``.

**Accepted, not solved, here:** no node in this skeleton can raise both families in one
invocation (``synthesize_segment`` only calls ``TTSProvider``/``Storage``, never an
``LLMProvider``), so the gap is inert today. It stops being inert the moment a future node can
raise both -- T15's outline/scripting node, calling an ``LLMProvider`` that can plausibly hit
``ProviderUnavailable`` on one attempt and ``StructuredOutputError`` on another within the same
run. **If that node needs a ``StructuredOutputError`` cap that holds regardless of what else
failed first, it must not rely on this module's two-policy split for that isolation** -- wrap the
``LLMProvider.generate`` call in its own explicit, locally-counted retry loop instead, and let
this module's policies handle only the outer, node-level classification.

**What this still does not do, and cannot from inside ``core/graph/``:** ``interfaces/errors.py``
says to cap ``StructuredOutputError`` "using ``QueuedJob.attempt``" -- a job-level counter that
survives a *requeue*, not just a node-level counter that survives a *checkpoint resume*.
Confirmed empirically: LangGraph's per-node attempt counter resets on every fresh ``ainvoke``
against the same thread, so a job requeued by a future runner after exhausting the cap below gets
the full cap again, indefinitely. ``core/graph/context.GraphContext`` deliberately excludes
``JobQueue`` (a runner's concern, not a node's), so nothing here can see ``QueuedJob.attempt`` to
enforce a cap across requeues even if it wanted to. That piece is still open, and belongs to
whichever future task builds the runner that calls ``JobQueue.fail(..., requeue=True)`` -- it
should refuse to requeue past some ``QueuedJob.attempt`` ceiling before this module's per-run cap
is ever reached a second time.

Reused by every future node that can raise these, rather than each re-deriving the classification.
**A node that isolates its own ``StructuredOutputError`` retries internally (T15's outline/
scripting node, via ``core/graph/nodes/structured_retry.py``) registers with
``build_transient_retry_policy()`` alone, not this function** -- see that function's docstring for
why attaching the bounded policy too would silently defeat the isolation. A node that never raises
``StructuredOutputError`` at all (``synthesize_segment``, which only calls ``TTSProvider``/
``Storage``) can keep using either -- the bounded half is simply never matched for it.
"""

from langgraph.types import RetryPolicy

from interfaces import ProviderUnavailable, RateLimited, RenderFailed, StructuredOutputError

TRANSIENT: tuple[type[Exception], ...] = (RateLimited, ProviderUnavailable, RenderFailed)
BOUNDED: tuple[type[Exception], ...] = (StructuredOutputError,)
RETRYABLE: tuple[type[Exception], ...] = TRANSIENT + BOUNDED


def is_retryable(exc: Exception) -> bool:
    """Whether a node raising ``exc`` should be retried at all, per the classification above."""
    return isinstance(exc, RETRYABLE)


def build_retry_policies(
    *, transient_max_attempts: int = 5, structured_output_max_attempts: int = 2
) -> tuple[RetryPolicy, RetryPolicy]:
    """One node's worth of "retry, but bounded" -- two policies, cleanly isolated only when a
    node's failures stay within one classified family across its retries (see module docstring
    for the shared-counter caveat when they don't).

    Order matters to LangGraph (first match wins), though the two predicates are disjoint here so
    it makes no behavioural difference -- listed transient-first because that is the common case.
    """
    return (
        RetryPolicy(
            max_attempts=transient_max_attempts, retry_on=lambda exc: isinstance(exc, TRANSIENT)
        ),
        RetryPolicy(
            max_attempts=structured_output_max_attempts,
            retry_on=lambda exc: isinstance(exc, BOUNDED),
        ),
    )


def build_transient_retry_policy(*, max_attempts: int = 5) -> RetryPolicy:
    """The transient half of ``build_retry_policies()``, alone -- for a node that isolates its own
    ``StructuredOutputError`` retries internally (``core/graph/nodes/structured_retry.py``) rather
    than relying on this module's bounded policy for that.

    Attaching the bounded policy *as well* to such a node would defeat that isolation: a call
    whose local retry budget is exhausted re-raises ``StructuredOutputError`` into a node-level
    policy that still matches it, retrying the **entire node** -- redoing every other
    already-completed call inside it -- to re-attempt the one call a local retry already gave up
    on for good reason (D24: a schema the model consistently cannot satisfy is a prompt bug, not
    sampling noise, so redoing everything else buys nothing). T15's outline/scripting node is the
    first to need this.
    """
    return RetryPolicy(max_attempts=max_attempts, retry_on=lambda exc: isinstance(exc, TRANSIENT))
