"""Fans one job's graph events out to any number of concurrent SSE subscribers (T20).

No bespoke event bus -- the source of truth is ``graph.astream_events`` itself (``api/runner.py``
iterates it directly). This module exists only because ``astream_events`` has exactly one
consumer, and an HTTP request that arrives after a run has already started still needs to see
what happens next.
"""

import asyncio
from typing import Any

# The graph's own node names (core/graph/pipeline.py's add_node calls) -- everything else
# astream_events emits (LLM/tool sub-steps inside a node) is real but not a "stage" a client
# needs to see, so it is filtered out rather than forwarded as noise.
STAGE_NODES = frozenset(
    {
        "plan_segments",
        "synthesize_segment",
        "assign_tiers",
        "plan_visuals",
        "author_scene",
        "collect_scenes",
        "render_scene",
        "finalize",
    }
)


def summarize_node_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """A raw ``astream_events`` event, reduced to one stage transition -- or ``None`` if this
    event is not one (an LLM call inside a node, a checkpoint write, etc.).

    Deliberately defensive about the input's shape: LangGraph's event payload is a real,
    version-sensitive structure this module does not control, and a stage feed that occasionally
    drops one event is a far smaller problem than a run that crashes because a UI-facing summary
    could not be built. ``core/graph/node_timing.py``'s log line is the guaranteed record either
    way.
    """
    kind = event.get("event")
    name = event.get("name")
    if kind not in ("on_chain_start", "on_chain_end") or name not in STAGE_NODES:
        return None
    summary: dict[str, Any] = {
        "node": name,
        "stage": "start" if kind == "on_chain_start" else "end",
    }
    segment = _segment_payload(event)
    if segment is not None:
        index = (
            segment.get("index") if isinstance(segment, dict) else getattr(segment, "index", None)
        )
        title = (
            segment.get("title") if isinstance(segment, dict) else getattr(segment, "title", None)
        )
        if index is not None:
            summary["segment_index"] = index
        if title is not None:
            summary["segment_title"] = title
    return summary


def _segment_payload(event: dict[str, Any]) -> Any:
    data = event.get("data") or {}
    payload = data.get("input") if event.get("event") == "on_chain_start" else data.get("output")
    if isinstance(payload, dict):
        return payload.get("segment")
    return getattr(payload, "segment", None)


class JobEventBus:
    """Per-``job_id`` fan-out. Each subscriber gets its own queue; ``None`` is the end-of-stream
    sentinel a subscriber's SSE generator stops on."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(job_id, []).append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(job_id, [])
        if queue in subscribers:
            subscribers.remove(queue)
        if not subscribers:
            self._subscribers.pop(job_id, None)

    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        for queue in self._subscribers.get(job_id, []):
            await queue.put(event)

    async def close(self, job_id: str) -> None:
        for queue in self._subscribers.get(job_id, []):
            await queue.put(None)
