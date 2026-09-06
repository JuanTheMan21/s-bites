"""``JobQueue`` backed by Service Bus (T34, closing D25).

Constructor shape is unchanged from the T12 stub (D51: explicit args, never ``os.environ``).

**The receipt scheme is the one design decision in this file worth reading before the rest.**
``QueuedJob.receipt`` must round-trip through ``enqueue`` -> ``dequeue`` -> ``complete``/``fail``
identically to ``LocalJobQueue``'s opaque token, and a requeued job must get a *fresh* receipt
(``adapters/local/job_queue.py``'s own docstring names this as part of the contract). Service Bus
has no such token before a message is received, so this derives one:
``f"{message_id}:{delivery_count}"``. **Found live, against the real namespace, not assumed from
docs:** this SDK's ``delivery_count`` is 0 on a message's first delivery, not 1 -- the first
version of this file assumed 1-based and every live parity test failed identically, both on the
receipt round-trip and (as a direct consequence: ``fail(requeue=True)`` looked up a receipt that
was never stored) on redelivery. ``enqueue`` hands back ``f"{job_id}:0"`` to match. A message that
comes back after ``fail(requeue=True)`` (an ``abandon``) is redelivered with ``delivery_count``
incremented by the broker, which is what makes the "fresh receipt on redelivery" property fall out
for free -- no attempt counter is carried in the payload, unlike the local queue's ``model_copy``.
``QueuedJob.attempt`` is ``delivery_count + 1``, so it still starts at 1 to match every other
implementation's contract (``LocalJobQueue``/``FakeJobQueue`` both default ``attempt=1``) without
lying about what the broker actually counts from.

**Lock renewal is the correctness hazard this whole implementation exists to get right.** A
Service Bus lock lasts at most 5 minutes; this pipeline's own render can run 10-15. Without
renewal, a lease expires mid-render and the message is redelivered -- a second worker starts the
same job while the first is still rendering it. Every received message gets its own
``AutoLockRenewer``, registered for up to ``lock_renewal_s`` (default 3600, comfortably above the
longest expected job) the moment ``dequeue`` returns it, closed the moment ``complete``/``fail``
settles it.

**One renewer per message, not one shared for the adapter's lifetime -- found by review.** The
first version used a single ``AutoLockRenewer`` for this instance's whole life, registering every
dequeued message onto it. The SDK's own renewer never drops a completed registration from its
internal tracking list except on ``close()`` -- so a worker left running for days, processing
hundreds of jobs on one long-lived queue instance (exactly what ``worker.py`` does), accumulates
one more permanently-referenced finished task per job, forever: a slow, real memory leak invisible
in any test shorter than that. A fresh, short-lived renewer per message, closed as soon as that
message is settled, cannot leak past a single job's lifetime.
"""

import json
from typing import Any

from azure.servicebus import ServiceBusMessage, ServiceBusReceivedMessage
from azure.servicebus.aio import AutoLockRenewer, ServiceBusClient
from azure.servicebus.exceptions import ServiceBusError

from adapters.azure.servicebus_errors import LOCK_LOST_EXCEPTIONS, translate
from interfaces import JobQueue, QueuedJob, check_serialisable


class ServiceBusJobQueue(JobQueue):
    """One queue, one receiver held open for the adapter's lifetime, one lock renewer."""

    def __init__(
        self, connection_string: str, queue_name: str, *, lock_renewal_s: float = 3600
    ) -> None:
        self.connection_string = connection_string
        self.queue_name = queue_name
        self._lock_renewal_s = lock_renewal_s
        self._client = ServiceBusClient.from_connection_string(connection_string)
        self._sender = self._client.get_queue_sender(queue_name)
        self._receiver = self._client.get_queue_receiver(queue_name, prefetch_count=0)
        # Keyed by the derived receipt (not the SDK's own lock_token) so complete/fail can settle
        # the exact message a caller is holding without exposing SDK types across the boundary.
        self._in_flight: dict[str, ServiceBusReceivedMessage] = {}
        # One AutoLockRenewer per in-flight message, not one shared for the adapter's lifetime --
        # see the module docstring for why. Closed in complete/fail the moment its message settles.
        self._renewers: dict[str, AutoLockRenewer] = {}

    async def enqueue(self, job_id: str, payload: dict[str, Any]) -> str:
        check_serialisable(payload)
        try:
            await self._sender.send_messages(ServiceBusMessage(_encode(payload), message_id=job_id))
        except ServiceBusError as exc:
            raise translate(exc) from exc
        return f"{job_id}:0"

    async def dequeue(self, *, timeout_s: float | None = None) -> QueuedJob | None:
        try:
            messages = await self._receiver.receive_messages(
                max_message_count=1, max_wait_time=timeout_s
            )
        except ServiceBusError as exc:
            raise translate(exc) from exc
        if not messages:
            return None  # the empty case is not an error on either implementation
        message = messages[0]
        receipt = f"{message.message_id}:{message.delivery_count}"
        renewer = AutoLockRenewer()
        renewer.register(self._receiver, message, max_lock_renewal_duration=self._lock_renewal_s)
        self._in_flight[receipt] = message
        self._renewers[receipt] = renewer
        return QueuedJob(
            job_id=str(message.message_id),
            payload=_decode(message),
            receipt=receipt,
            attempt=message.delivery_count + 1,
        )

    async def complete(self, receipt: str) -> None:
        message = self._in_flight.pop(receipt, None)
        if message is None:
            return  # idempotent: a second call, or a receipt this instance never issued
        try:
            try:
                await self._receiver.complete_message(message)
            except LOCK_LOST_EXCEPTIONS:
                # Already settled (by us or by a redelivery elsewhere) -- see servicebus_errors's
                # module docstring. Not a failure: the job is done either way.
                pass
            except ServiceBusError as exc:
                raise translate(exc) from exc
        finally:
            await self._close_renewer(receipt)

    async def fail(self, receipt: str, error: str, *, requeue: bool = False) -> None:
        message = self._in_flight.pop(receipt, None)
        if message is None:
            return
        try:
            try:
                if requeue:
                    await self._receiver.abandon_message(message)
                else:
                    await self._receiver.dead_letter_message(
                        message, reason="job_failed", error_description=error[:4096]
                    )
            except LOCK_LOST_EXCEPTIONS:
                pass
            except ServiceBusError as exc:
                raise translate(exc) from exc
        finally:
            await self._close_renewer(receipt)

    async def _close_renewer(self, receipt: str) -> None:
        """Closing the message's own short-lived renewer is what keeps ``AutoLockRenewer``'s
        internal tracking list from growing for the life of the process -- see the module
        docstring. Runs in a ``finally`` so a settle failure still releases it."""
        renewer = self._renewers.pop(receipt, None)
        if renewer is not None:
            await renewer.close()

    async def aclose(self) -> None:
        """Off-contract, per D55 -- ``config.close_adapters`` picks this up generically."""
        for renewer in self._renewers.values():
            await renewer.close()
        self._renewers.clear()
        await self._receiver.close()
        await self._sender.close()
        await self._client.close()


def _encode(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


def _decode(message: ServiceBusReceivedMessage) -> dict[str, Any]:
    # ``.body`` is a generator of bytes chunks on a real received message. Checked the right way
    # around (found by review: ``hasattr(..., "__iter__")`` is true for plain ``bytes`` too, so
    # the original guard could never actually select that branch) -- ``isinstance`` against
    # bytes/str first, falling back to joining an iterable of chunks otherwise.
    body = message.body if isinstance(message.body, bytes | str) else b"".join(message.body)
    return json.loads(body)
