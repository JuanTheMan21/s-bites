"""T34, found by review: a `JobStore` failure before `JobRunner._run_one`'s own try/except even
starts must still release the queue receipt, or a real broker (Service Bus) strands that message
locked forever. Cheap and direct against `JobRunner` itself -- no graph, no ffmpeg, no FastAPI --
since the whole point is the receipt bookkeeping, not anything the graph does.
"""

from api.job_store import JobStore
from api.runner import JobRunner
from config import Adapters
from interfaces import ObjectNotFound
from tests.fakes import (
    FakeEventChannel,
    FakeJobQueue,
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)


async def test_a_job_store_failure_before_the_try_block_still_releases_the_receipt(
    monkeypatch,
) -> None:
    """MAX_ATTEMPTS pinned to 1 so the induced failure dead-letters on the first attempt, the
    same convention tests/test_api_resume.py already uses -- makes the outcome deterministic
    rather than racing this test against the runner's own automatic requeue."""
    monkeypatch.setattr("api.runner.MAX_ATTEMPTS", 1)
    queue = FakeJobQueue()
    adapters = Adapters(
        llm=FakeLLMProvider(),
        tts=FakeTTSProvider(),
        storage=FakeStorage(),
        skills=FakeSkillRegistry(),
        queue=queue,
        render=FakeRenderBackend(),
        events=FakeEventChannel(),
    )
    store = JobStore(adapters.storage)  # no job record ever saved -- store.load() below 404s
    runner = JobRunner(adapters, store, adapters.events, frame_budget=0, fps=24)

    receipt = await queue.enqueue("job-1", {})
    queued = await queue.dequeue(timeout_s=1.0)
    assert queued is not None

    try:
        await runner._run_one(queued)
        raise AssertionError("expected ObjectNotFound to propagate")
    except ObjectNotFound:
        pass

    assert receipt not in queue.in_flight
    assert len(queue.dead_letters) == 1
    assert queue.dead_letters[0][0].receipt == receipt
