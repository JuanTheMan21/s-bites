"""The contract for carrying one job's progress from whoever is running it to whoever is
watching it (T34).

Exists because ``JobRunner`` and the SSE endpoint stopped being guaranteed to share a process the
moment the worker became its own entry point. Co-located, an in-process fan-out is enough -- that
is exactly what ``adapters/local/event_channel.py::LocalEventChannel`` still is. Split across a
worker container and an API container, nothing links them unless something crosses that boundary,
and the failure mode if nothing does is not an exception: the SSE endpoint simply never receives
another event, and the progress UI looks like a hung pipeline with no error anywhere to find.

Shaped after ``JobQueue`` rather than invented fresh: ``publish``/``end_stream`` are one side (the
worker, one-way), ``subscribe``/``unsubscribe`` are the other (the API, per-connection), and
``start`` begins whatever receiving a real implementation needs -- a documented no-op locally,
where nothing needs to arrive from anywhere.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any


def check_event_serialisable(event: dict[str, Any]) -> None:
    """Raise ``ValueError`` if ``event`` could not survive the trip to a real channel.

    The same precondition ``interfaces/job_queue.py::check_serialisable`` enforces, and for the
    identical reason (D39): an in-process fan-out hands the very same object back to a subscriber,
    so anything -- a ``Path``, a ``datetime``, a model instance -- works perfectly under
    ``EVENTS_ENV=local`` and only fails once a real channel is behind the interface. Enforced by
    every implementation's own ``publish``, including the local/fake ones, so the bug surfaces in
    dev and in the offline test suite rather than waiting for Service Bus to appear.
    """
    try:
        json.dumps(event)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"event must be JSON-serialisable -- it crosses a wire on Service Bus: {exc}"
        ) from exc


class EventChannel(ABC):
    """Fans one job's stage events out to any number of concurrent subscribers, across however
    many processes are actually running.

    ``subscribe`` returns a plain ``asyncio.Queue`` rather than a channel-specific handle so the
    SSE generator that reads it (``api/jobs.py``) does not change between implementations --
    ``asyncio`` is stdlib, not a vendor type, so returning it here does not reintroduce the vendor
    type this contract exists to keep out.
    """

    @abstractmethod
    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        """Send ``event`` to every current subscriber of ``job_id``. A ``job_id`` with no
        subscribers yet is not an error -- the same reasoning as ``JobQueue.dequeue``'s empty
        case: a subscriber connecting after this call started is a normal race, not a bug to
        raise on.

        ``event`` must be JSON-serialisable; the Service Bus path crosses a wire, so a value that
        only survives in-process is a local-only bug waiting for the cloud stack -- see
        ``check_event_serialisable``, which every implementation calls."""

    @abstractmethod
    async def end_stream(self, job_id: str) -> None:
        """Signal every current subscriber of ``job_id`` that no further events are coming.
        Idempotent: ending an already-ended stream, or one with no subscribers, is a no-op."""

    @abstractmethod
    async def subscribe(self, job_id: str) -> asyncio.Queue:
        """Register for ``job_id``'s events. Returns a fresh queue; a sentinel of ``None`` is
        put on it when ``end_stream`` is called, which is what the SSE generator's loop stops
        on. ``async`` to match every other method here (this project's own mechanical rule,
        ``tests/test_interfaces.py``/``tests/test_fakes.py``), even though neither implementation
        actually awaits anything inside it."""

    @abstractmethod
    async def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        """Stop delivering to ``queue``. Idempotent: unsubscribing twice, or a queue that was
        never subscribed, is a no-op -- the same shape as ``JobQueue.complete``'s idempotence."""

    @abstractmethod
    async def start(self) -> None:
        """Begin receiving events published from elsewhere, if this implementation needs to.
        Must be called once before any cross-process event can arrive; called from the same
        FastAPI lifespan that starts the in-process worker today. A no-op on an implementation
        with nothing to receive."""

    @abstractmethod
    async def history(self, job_id: str) -> list[dict[str, Any]]:
        """Every event ``publish``ed for ``job_id`` so far, in order. Empty for a ``job_id`` this
        channel has never seen a ``publish`` call for.

        T18M/D197: this is what closes the gap ``publish``'s own docstring names ("a subscriber
        connecting after this call started is a normal race, not a bug") -- true for ``publish``
        itself, but confirmed live to leave a real user's progress UI (every phase timecode, and
        the waveform, both entirely built from received events) permanently blank for a job that
        was already mid-flight when the page connected -- an ordinary refresh or a job opened
        from the list, not a rare edge case. ``api/jobs.py::stream_job_events`` replays this
        before tailing live events, for both a still-running and an already-terminal job.

        In-memory for the life of this process, not durably persisted -- sufficient for the
        current single-replica deployment (``config_events.py``'s own documented constraint);
        lost across a process restart, same caveat that constraint already carries. A future
        multi-replica API would need real persistence here, not just this."""
