"""The three ``JobQueue`` implementations, held to one set of assertions.

``fake`` and ``local`` run offline: ``LocalJobQueue`` is pure ``asyncio``, no installs, no
network. ``servicebus`` (T34, real as of this task) is marked ``live`` and so is deselected by
default, matching ``test_storage_parity.py``'s ``blob`` pattern -- each test gets its own
throwaway queue (``tests.azure_live.throwaway_queue``), never the real ``video-jobs`` queue this
project runs against, for the same isolation reason ``throwaway_container`` exists: a queue shared
across test runs risks a dequeue picking up a stale message left by an earlier, differently-
asserting test.

**The existing assertions below are the specification, unchanged by adding this third param.** If
one fails against Service Bus, the adapter is wrong, not the test.
"""

from collections.abc import AsyncIterator

import pytest

from adapters.azure.job_queue import ServiceBusJobQueue
from adapters.local.job_queue import LocalJobQueue
from interfaces import JobQueue
from tests.azure_live import SERVICE_BUS_CONNECTION_STRING, require, throwaway_queue
from tests.fakes import FakeJobQueue

IMPLEMENTATIONS = ["fake", "local", pytest.param("servicebus", marks=pytest.mark.live)]


@pytest.fixture(params=IMPLEMENTATIONS)
async def queue(request: pytest.FixtureRequest) -> AsyncIterator[JobQueue]:
    if request.param == "fake":
        yield FakeJobQueue()
        return
    if request.param == "local":
        yield LocalJobQueue()
        return

    async with throwaway_queue() as name:
        sb_queue = ServiceBusJobQueue(require(SERVICE_BUS_CONNECTION_STRING), name)
        try:
            yield sb_queue
        finally:
            await sb_queue.aclose()


async def test_a_job_dequeues_with_its_payload_and_starting_attempt(queue: JobQueue) -> None:
    receipt = await queue.enqueue("job-1", {"topic": "SQL injection"})

    job = await queue.dequeue(timeout_s=1.0)
    assert job is not None
    assert job.job_id == "job-1"
    assert job.payload == {"topic": "SQL injection"}
    assert job.receipt == receipt
    assert job.attempt == 1


async def test_dequeue_on_an_empty_queue_times_out_to_none_not_an_exception(
    queue: JobQueue,
) -> None:
    """The empty case is not an error on either implementation, per the contract."""
    assert await queue.dequeue(timeout_s=0.05) is None


async def test_complete_is_idempotent(queue: JobQueue) -> None:
    receipt = await queue.enqueue("job-1", {})
    await queue.dequeue(timeout_s=1.0)

    await queue.complete(receipt)
    await queue.complete(receipt)  # second call: a no-op, never a KeyError


async def test_fail_with_requeue_returns_the_job_with_a_new_receipt_and_incremented_attempt(
    queue: JobQueue,
) -> None:
    first_receipt = await queue.enqueue("job-1", {})
    claimed = await queue.dequeue(timeout_s=1.0)
    assert claimed is not None

    await queue.fail(first_receipt, "transient failure", requeue=True)

    revived = await queue.dequeue(timeout_s=1.0)
    assert revived is not None
    assert revived.job_id == "job-1"
    assert revived.attempt == 2
    assert revived.receipt != first_receipt  # matches Service Bus: redelivery mints a new token


async def test_fail_without_requeue_dead_letters_the_job(queue: JobQueue) -> None:
    receipt = await queue.enqueue("job-1", {})
    await queue.dequeue(timeout_s=1.0)

    await queue.fail(receipt, "permanent failure", requeue=False)

    assert await queue.dequeue(timeout_s=0.05) is None


async def test_fail_on_an_unknown_receipt_is_a_no_op(queue: JobQueue) -> None:
    """No job was ever claimed under this receipt -- both implementations swallow it silently,
    the same idempotency ``complete`` gets."""
    await queue.fail("never-claimed", "irrelevant", requeue=True)


async def test_enqueue_refuses_a_payload_that_could_not_cross_a_wire(queue: JobQueue) -> None:
    """D39's argument, applied to this contract: an in-process queue would happily hand back a
    ``Path`` it was never meant to carry, and the bug would wait for Service Bus to appear."""
    with pytest.raises(ValueError, match="JSON-serialisable"):
        await queue.enqueue("job-1", {"dest": object()})
