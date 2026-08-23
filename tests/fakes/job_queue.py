"""``JobQueue``, as an in-process asyncio queue."""

import asyncio
from typing import Any
from uuid import uuid4

from interfaces import JobQueue, QueuedJob, check_serialisable
from tests.fakes.failure_injection import FailureInjector


class FakeJobQueue(FailureInjector, JobQueue):
    """Hands out jobs in order, tracks what is claimed, and dead-letters what fails.

    Receipts are random hex: opaque by construction, so no test can come to depend on their
    shape and no caller can start parsing them. A requeued job gets a *new* receipt, matching
    Service Bus, where redelivery issues a fresh lock token.

    This implementation never fails on its own -- see ``failure_injection`` for why that is the
    problem it needs, and how to arm one.
    """

    def __init__(self) -> None:
        self._waiting: asyncio.Queue[QueuedJob] = asyncio.Queue()
        self.in_flight: dict[str, QueuedJob] = {}
        self.completed: list[QueuedJob] = []
        self.dead_letters: list[tuple[QueuedJob, str]] = []

    async def enqueue(self, job_id: str, payload: dict[str, Any]) -> str:
        self._maybe_fail("enqueue")
        check_serialisable(payload)
        job = QueuedJob(job_id=job_id, payload=payload, receipt=uuid4().hex)
        await self._waiting.put(job)
        return job.receipt

    async def dequeue(self, *, timeout_s: float | None = None) -> QueuedJob | None:
        self._maybe_fail("dequeue")
        try:
            job = await asyncio.wait_for(self._waiting.get(), timeout_s)
        except TimeoutError:
            return None  # the empty case is not an error on either implementation
        self.in_flight[job.receipt] = job
        return job

    async def complete(self, receipt: str) -> None:
        self._maybe_fail("complete")
        job = self.in_flight.pop(receipt, None)
        if job is not None:  # idempotent: a second call is a no-op, never a KeyError
            self.completed.append(job)

    async def fail(self, receipt: str, error: str, *, requeue: bool = False) -> None:
        self._maybe_fail("fail")
        job = self.in_flight.pop(receipt, None)
        if job is None:
            return
        if requeue:
            revived = job.model_copy(update={"attempt": job.attempt + 1, "receipt": uuid4().hex})
            await self._waiting.put(revived)
        else:
            self.dead_letters.append((job, error))
