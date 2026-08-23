"""The contract for the work queue that sits between a request and a video."""

import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


def check_serialisable(payload: dict[str, Any]) -> None:
    """Raise ``ValueError`` if ``payload`` could not survive the trip to a real queue.

    ``enqueue`` promises the payload is JSON-serialisable because Service Bus crosses a wire.
    An in-process queue hands the very same object back, so a ``Path``, a ``datetime`` or a
    model instance works perfectly there and fails only once a real queue is behind the
    interface -- the local-only bug the class docstring warns about, in its most literal form.
    Lives here rather than inside one implementation so every ``enqueue`` -- fake or real --
    enforces the same precondition (D43/D50's move, applied to this contract).
    """
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"job payload must be JSON-serialisable -- it crosses a wire on Service Bus: {exc}"
        ) from exc


class QueuedJob(BaseModel):
    """One unit of work claimed from the queue.

    This is a whole video request, not a step of one. Fan-out *within* a job -- narrating
    fifteen segments in parallel -- belongs to the graph, not to the queue.
    """

    job_id: str
    payload: dict[str, Any]
    receipt: str
    attempt: int = 1


class JobQueue(ABC):
    """Hands whole video jobs to whichever worker is free.

    Producing a video takes minutes, so the API cannot serve one inside an HTTP request. It
    enqueues and returns an id; a worker claims the job and runs the graph.

    ``receipt`` is an opaque token minted by the implementation -- an asyncio handle locally,
    a lock token on Service Bus. Callers pass it back to ``complete`` or ``fail`` and must
    never parse it, which is what allows the two implementations to differ underneath.

    Every method here may raise ``ProviderUnavailable`` or ``RateLimited`` once the queue is
    a real service (T34). The in-process implementation never does, which is precisely why
    it is worth writing down: code written against the local pool alone will not have seen
    either, and that is a parity gap waiting for the cloud path.
    """

    @abstractmethod
    async def enqueue(self, job_id: str, payload: dict[str, Any]) -> str:
        """Queue ``job_id`` with ``payload``. Returns the receipt for the queued message.

        ``payload`` must be JSON-serialisable; the Blob and Service Bus paths both cross a
        wire, so a value that only survives in-process is a local-only bug waiting for the
        cloud stack.
        """

    @abstractmethod
    async def dequeue(self, *, timeout_s: float | None = None) -> QueuedJob | None:
        """Claim the next job, waiting up to ``timeout_s`` seconds.

        Returns ``None`` on timeout -- both implementations, no exception on the empty case.
        ``timeout_s`` ``None`` waits indefinitely.

        A claimed job stays invisible to other workers until ``complete`` or ``fail`` is
        called, or until the implementation's own lease expires.
        """

    @abstractmethod
    async def complete(self, receipt: str) -> None:
        """Mark the claimed job done and remove it. Idempotent."""

    @abstractmethod
    async def fail(self, receipt: str, error: str, *, requeue: bool = False) -> None:
        """Release a claimed job as failed, recording ``error``.

        ``requeue`` returns it to the queue with ``attempt`` incremented; otherwise it is
        dead-lettered and will not be handed out again.
        """
