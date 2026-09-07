"""``EventChannel`` as an in-process fan-out (T34).

The same shape ``api/events.py::JobEventBus`` already was before the worker became its own
process -- moved here unchanged rather than redesigned, since co-located is still exactly the
right behaviour for local development and for the offline test suite. ``start()`` is a documented
no-op: nothing needs to arrive from anywhere when publisher and subscriber share a process.
"""

import asyncio
import time
from typing import Any

from interfaces import EventChannel, check_event_serialisable


class LocalEventChannel(EventChannel):
    """Per-``job_id`` fan-out. Each subscriber gets its own queue; ``None`` is the end-of-stream
    sentinel a subscriber's SSE generator stops on."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        # T18M/D197: every event this instance has ever published, kept for `history()` -- see
        # that method's own docstring on ``EventChannel`` for why. In-memory, bounded per job
        # (a job's own event count is small, a few dozen phase/segment transitions at most) but
        # NOT bounded across jobs -- found by review: nothing ever evicts a finished job's own
        # entry, so a long-lived process (this API's single replica, per `config_events.py`'s own
        # documented constraint) accumulates one entry per job it has EVER run, forever. Invisible
        # for a POC's own lifetime; a real, if slow, leak for the "must become an enterprise
        # product without a rewrite" goal CLAUDE.md states -- not fixed here (no natural
        # eviction point exists yet: a job must stay replayable for a client that reconnects long
        # after it finished, so end_stream() cannot simply clear it), flagged so it is not
        # mistaken for a solved problem.
        self._history: dict[str, list[dict[str, Any]]] = {}

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
        # T18M/D197: stamp a real server-side time, once, here -- the one place every event
        # (direct local publish, or a ServiceBusEventChannel's pump re-publishing one it received
        # over the wire, which already carries `at` from ITS OWN publish() call) passes through.
        # A new dict, not a mutation of the caller's own -- `publish` having a visible side effect
        # on an object the caller still holds a reference to would be a surprising API. Only
        # stamped when absent, never overwritten -- a message re-published here already carrying
        # `at` came from its true origin, which this instance cannot know better than.
        # Found by review: without this, the frontend stamped every event with the BROWSER's
        # receipt time, which is a fine proxy for a live event (arrives within milliseconds of
        # happening) but wrong for a REPLAYED one -- a client reconnecting minutes into a job
        # would see the whole history burst land in one instant, every already-reached phase
        # showing "just now" instead of when it actually happened.
        stamped = event if "at" in event else {**event, "at": int(time.time() * 1000)}
        self._history.setdefault(job_id, []).append(stamped)
        for queue in self._subscribers.get(job_id, []):
            await queue.put(stamped)

    async def end_stream(self, job_id: str) -> None:
        for queue in self._subscribers.get(job_id, []):
            await queue.put(None)

    async def history(self, job_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(job_id, []))
