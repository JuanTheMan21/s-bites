"""``EventChannel``, as an in-process fan-out with test-observable state."""

import asyncio
from typing import Any

from interfaces import EventChannel, check_event_serialisable
from tests.fakes.failure_injection import FailureInjector


class FakeEventChannel(FailureInjector, EventChannel):
    """Same fan-out shape as ``LocalEventChannel``, plus ``published``/``ended`` so a test can
    assert on what crossed the channel without racing a subscriber's queue."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self.published: list[tuple[str, dict[str, Any]]] = []
        self.ended: list[str] = []
        self.started = False

    async def start(self) -> None:
        self._maybe_fail("start")
        self.started = True

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
        self._maybe_fail("publish")
        check_event_serialisable(event)
        self.published.append((job_id, event))
        for queue in self._subscribers.get(job_id, []):
            await queue.put(event)

    async def end_stream(self, job_id: str) -> None:
        self._maybe_fail("end_stream")
        self.ended.append(job_id)
        for queue in self._subscribers.get(job_id, []):
            await queue.put(None)
