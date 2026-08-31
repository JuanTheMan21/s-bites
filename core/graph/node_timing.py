"""Per-node timing, logged plain -- no new ``GraphState`` fields (T18E, D121/D122). A ~216s
silent gap between two LLM calls in one T18D render was almost certainly retry/backoff stacking,
and nothing anywhere logged enough to say so for certain. This wraps every node registered in
``core/graph/pipeline.py`` with a start/elapsed log line; ``adapters/azure/llm_provider.py`` logs
the retry side of the same picture.

``functools.wraps`` matters here specifically: LangGraph inspects a node callable's own signature
(via ``inspect.signature``, which follows ``__wrapped__`` by default) to decide whether to inject
``Runtime[GraphContext]`` as a second positional argument. Without ``wraps``, every timed node
would lose that injection and break at graph-build time -- ``tests/test_graph_pipeline.py`` is
what actually proves this wrapping stays safe, not reasoning about it alone.
"""

import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def timed(name: str, fn: F) -> F:
    """Wrap an async node callable to log its own start and elapsed time under ``name`` -- the
    name a graph node is registered under, not necessarily ``fn.__name__`` (kept explicit rather
    than assumed, since a node's registered name and its function's own name only usually match).
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = time.monotonic()
        logger.info("node %s started", name)
        try:
            return await fn(*args, **kwargs)
        finally:
            logger.info("node %s finished in %.2fs", name, time.monotonic() - started)

    return wrapper  # type: ignore[return-value]
