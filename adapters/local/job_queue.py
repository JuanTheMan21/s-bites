"""``JobQueue``, as an in-process asyncio queue.

For an in-process queue there is no "more real" implementation to build short of a genuine
service -- Service Bus, at T34 (``adapters/azure/job_queue.py``, stubbed there until then). This
class is deliberately close to ``tests/fakes/job_queue.py``'s ``FakeJobQueue``: the two differ only
in that this one does not mix in test-only failure injection, and that this one is what
``config.py`` wires up for real use. Seeing the same shape twice here is not duplication to clean
up -- it is what "the fake already behaves like the local backend" looks like in code.
"""

import asyncio
import logging
from typing import Any
from uuid import uuid4

from interfaces import JobQueue, QueuedJob, check_serialisable

logger = logging.getLogger(__name__)


class LocalJobQueue(JobQueue):
    """Hands out jobs in order, in-process, on one asyncio event loop.

    ``receipt`` is random hex, opaque by construction, matching Service Bus's lock-token shape
    closely enough that no caller can come to depend on either format. A requeued job gets a
    *fresh* receipt, again matching Service Bus's redelivery semantics.

    Never raises ``ProviderUnavailable`` or ``RateLimited`` -- there is no network here to fail
    on. The ``JobQueue`` docstring names this as a real, documented parity gap: code exercised
    only against this adapter will not have seen either exception before the cloud path (T34)
    exists to raise them.
    """

    def __init__(self) -> None:
        self._waiting: asyncio.Queue[QueuedJob] = asyncio.Queue()
        self._in_flight: dict[str, QueuedJob] = {}

    async def enqueue(self, job_id: str, payload: dict[str, Any]) -> str:
        check_serialisable(payload)
        job = QueuedJob(job_id=job_id, payload=payload, receipt=uuid4().hex)
        await self._waiting.put(job)
        return job.receipt

    async def dequeue(self, *, timeout_s: float | None = None) -> QueuedJob | None:
        try:
            job = await asyncio.wait_for(self._waiting.get(), timeout_s)
        except TimeoutError:
            return None  # the empty case is not an error on either implementation
        self._in_flight[job.receipt] = job
        return job

    async def complete(self, receipt: str) -> None:
        self._in_flight.pop(receipt, None)  # idempotent: a second call is a no-op, never KeyError

    async def fail(self, receipt: str, error: str, *, requeue: bool = False) -> None:
        job = self._in_flight.pop(receipt, None)
        if job is None:
            return
        if requeue:
            revived = job.model_copy(update={"attempt": job.attempt + 1, "receipt": uuid4().hex})
            await self._waiting.put(revived)
        else:
            # Dead-lettered. There is no inspection surface on this contract, so a log line is
            # the only record -- a failure nobody can see is worse than a bare print here.
            logger.error(
                "job %s dead-lettered after attempt %d: %s", job.job_id, job.attempt, error
            )
