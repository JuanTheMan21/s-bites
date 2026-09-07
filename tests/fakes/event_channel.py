"""``EventChannel``, as an in-process fan-out with test-observable state."""

import asyncio
import time
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
        # T18M/D197: same stamping LocalEventChannel/ServiceBusEventChannel do -- see the real
        # implementation's own comment. A new dict, never a mutation of the caller's own; never
        # overwritten if the caller already stamped one.
        stamped = event if "at" in event else {**event, "at": int(time.time() * 1000)}
        self.published.append((job_id, stamped))
        for queue in self._subscribers.get(job_id, []):
            await queue.put(stamped)

    async def end_stream(self, job_id: str) -> None:
        self._maybe_fail("end_stream")
        self.ended.append(job_id)
        for queue in self._subscribers.get(job_id, []):
            await queue.put(None)

    async def history(self, job_id: str) -> list[dict[str, Any]]:
        return [event for pub_job_id, event in self.published if pub_job_id == job_id]
