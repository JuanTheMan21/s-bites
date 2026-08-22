"""What ``FakeJobQueue`` and ``FakeRenderBackend`` do.

Paired because they are the two contracts that stay stubbed on Azure through iteration 3 and
become real services in iteration 5.5 (T34, T35). Both are therefore tested here against
behaviour a *cloud* implementation must also produce -- attempts surviving a requeue,
dead-letters never redelivered -- rather than against whatever an in-process object happens to do.
"""

from pathlib import Path

import pytest

from interfaces import RateLimited, RenderFailed
from tests.fakes import FakeJobQueue, FakeRenderBackend

# --- JobQueue -----------------------------------------------------------------------------


async def test_a_job_survives_the_round_trip(fake_queue: FakeJobQueue) -> None:
    receipt = await fake_queue.enqueue("job-1", {"topic": "SQL injection"})

    job = await fake_queue.dequeue(timeout_s=1)

    assert job is not None
    assert (job.job_id, job.payload, job.receipt, job.attempt) == (
        "job-1",
        {"topic": "SQL injection"},
        receipt,
        1,
    )


async def test_an_empty_queue_times_out_to_none_rather_than_raising(
    fake_queue: FakeJobQueue,
) -> None:
    """Both implementations, no exception on the empty case -- a worker polls this in a loop."""
    assert await fake_queue.dequeue(timeout_s=0.01) is None


async def test_a_payload_that_could_not_cross_a_wire_is_refused(
    fake_queue: FakeJobQueue, tmp_path: Path
) -> None:
    """In-process a Path would work perfectly and fail at T34. One json.dumps closes the gap."""
    with pytest.raises(ValueError, match="JSON-serialisable"):
        await fake_queue.enqueue("job-1", {"dest": tmp_path})


async def test_completing_is_idempotent_and_a_completed_job_is_gone(
    fake_queue: FakeJobQueue,
) -> None:
    receipt = await fake_queue.enqueue("job-1", {})
    await fake_queue.dequeue(timeout_s=1)

    await fake_queue.complete(receipt)
    await fake_queue.complete(receipt)  # must not raise

    assert [job.job_id for job in fake_queue.completed] == ["job-1"]
    assert await fake_queue.dequeue(timeout_s=0.01) is None


async def test_a_requeued_failure_comes_back_with_its_attempt_incremented(
    fake_queue: FakeJobQueue,
) -> None:
    """T14 bounds StructuredOutputError retries on ``attempt``, so it has to survive a requeue."""
    receipt = await fake_queue.enqueue("job-1", {})
    await fake_queue.dequeue(timeout_s=1)

    await fake_queue.fail(receipt, "the model would not produce valid JSON", requeue=True)
    retried = await fake_queue.dequeue(timeout_s=1)

    assert retried is not None
    assert retried.attempt == 2
    assert retried.receipt != receipt, "redelivery issues a fresh lock token"


async def test_a_dead_lettered_job_is_never_handed_out_again(fake_queue: FakeJobQueue) -> None:
    receipt = await fake_queue.enqueue("job-1", {})
    await fake_queue.dequeue(timeout_s=1)

    await fake_queue.fail(receipt, "composition was invalid")

    assert [error for _, error in fake_queue.dead_letters] == ["composition was invalid"]
    assert await fake_queue.dequeue(timeout_s=0.01) is None


async def test_a_claimed_job_is_invisible_to_the_next_worker(fake_queue: FakeJobQueue) -> None:
    await fake_queue.enqueue("job-1", {})
    await fake_queue.dequeue(timeout_s=1)

    assert await fake_queue.dequeue(timeout_s=0.01) is None


async def test_the_queue_can_be_made_to_fail_the_way_a_real_one_would(
    fake_queue: FakeJobQueue,
) -> None:
    """The whole point of the injector: the in-process queue never raises these on its own."""
    fake_queue.fail_next("dequeue", RateLimited("service bus is throttling"))

    with pytest.raises(RateLimited):
        await fake_queue.dequeue(timeout_s=1)


# --- RenderBackend ------------------------------------------------------------------------


async def test_capture_returns_one_image_per_timestamp_in_the_order_requested(
    fake_render: FakeRenderBackend, tmp_path: Path
) -> None:
    """Tier 1 crossfades the results in order, so a reordered return is a scrambled reveal."""
    paths = await fake_render.capture(
        tmp_path / "scene.html", tmp_path / "frames", at_seconds=[2.0, 0.0, 2.0]
    )

    assert len(paths) == 3, "one image per request, even when a timestamp repeats"
    assert [p.name for p in paths] == sorted(p.name for p in paths)
    assert all(p.read_bytes().startswith(b"\x89PNG") for p in paths)
    assert fake_render.captures[0].at_seconds == (2.0, 0.0, 2.0)


async def test_render_records_the_measured_duration_it_was_given(
    fake_render: FakeRenderBackend, tmp_path: Path
) -> None:
    """The number that came from measured audio has to arrive at the backend unchanged."""
    dest = tmp_path / "clips" / "0.mp4"

    assert await fake_render.render(tmp_path / "s.html", dest, fps=24, duration_ms=9_000) == dest
    assert dest.exists()
    assert (fake_render.renders[0].fps, fake_render.renders[0].duration_ms) == (24, 9_000)


async def test_lint_returns_findings_and_never_raises(tmp_path: Path) -> None:
    """An invalid composition is this method's expected input; empty means valid."""
    assert await FakeRenderBackend().lint(tmp_path / "s.html") == []
    assert await FakeRenderBackend(["missing data-duration"]).lint(tmp_path / "s.html") == [
        "missing data-duration"
    ]


async def test_a_render_can_be_made_to_fail(fake_render: FakeRenderBackend, tmp_path: Path) -> None:
    fake_render.fail_next("render", RenderFailed("the browser crashed"))

    with pytest.raises(RenderFailed):
        await fake_render.render(tmp_path / "s.html", tmp_path / "0.mp4", fps=24, duration_ms=1)
