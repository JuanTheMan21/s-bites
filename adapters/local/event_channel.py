"""``EventChannel`` as an in-process fan-out (T34).

The same shape ``api/events.py::JobEventBus`` already was before the worker became its own
process -- moved here unchanged rather than redesigned, since co-located is still exactly the
right behaviour for local development and for the offline test suite. ``start()`` is a documented
no-op: nothing needs to arrive from anywhere when publisher and subscriber share a process.
"""

import asyncio
from typing import Any

from interfaces import EventChannel, check_event_serialisable


class LocalEventChannel(EventChannel):
    """Per-``job_id`` fan-out. Each subscriber gets its own queue; ``None`` is the end-of-stream
    sentinel a subscriber's SSE generator stops on."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    async def start(self) -> None:
        pass  # nothing to receive -- publisher and subscriber share this instance directly

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(job_id, []).append(queue)
        return queue

    async def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(job_id, [])
        if queue in subscribers:
            subscribers.remove(queue)
        if not subscribers:
            self._subscribers.pop(job_id, None)

    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        check_event_serialisable(event)
        for queue in self._subscribers.get(job_id, []):
            await queue.put(event)

    async def end_stream(self, job_id: str) -> None:
        for queue in self._subscribers.get(job_id, []):
            await queue.put(None)
