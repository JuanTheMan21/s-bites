"""``JobQueue`` stub backed by Service Bus. Real implementation lands at T34 (D25).

A stub with drifted signatures is worse than none -- it makes the boundary look verified when it
is not (the ``adapter-contract`` skill). This one matches ``interfaces.JobQueue`` exactly and
raises ``NotImplementedError`` naming what is missing, so `tests/test_adapter_stubs.py` can prove
the boundary is real even before there is anything real behind it.
"""

from typing import Any

from interfaces import JobQueue, QueuedJob


class ServiceBusJobQueue(JobQueue):
    """Constructor shape is provisional -- T34 finalises it against the real Service Bus SDK,
    lease/renew semantics, and dead-lettering. Kept explicit-args per D51 even as a stub, so the
    real implementation is a fill-in rather than a signature change."""

    def __init__(self, connection_string: str, queue_name: str) -> None:
        self.connection_string = connection_string
        self.queue_name = queue_name

    async def enqueue(self, job_id: str, payload: dict[str, Any]) -> str:
        raise NotImplementedError(
            "ServiceBusJobQueue.enqueue: real Service Bus enqueue lands at T34 (D25)"
        )

    async def dequeue(self, *, timeout_s: float | None = None) -> QueuedJob | None:
        raise NotImplementedError(
            "ServiceBusJobQueue.dequeue: real Service Bus lease semantics land at T34 (D25)"
        )

    async def complete(self, receipt: str) -> None:
        raise NotImplementedError(
            "ServiceBusJobQueue.complete: real Service Bus completion lands at T34 (D25)"
        )

    async def fail(self, receipt: str, error: str, *, requeue: bool = False) -> None:
        raise NotImplementedError(
            "ServiceBusJobQueue.fail: real Service Bus dead-lettering lands at T34 (D25)"
        )
