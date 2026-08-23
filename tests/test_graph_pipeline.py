"""Integration tests for the compiled graph: the happy path, and the DoD itself -- a killed run
resumes without repeating completed segments.

A real, file-backed ``AsyncSqliteSaver`` is used rather than the in-memory saver deliberately:
only a saver backed by something outside the process can stand in for a process actually being
killed. Everything else stays offline -- fakes for every interface, no network.
"""

from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from core.graph import GraphContext, build_graph
from core.models import JobStatus, VideoJob
from interfaces import ProviderMisconfigured
from tests.fakes import (
    FakeLLMProvider,
    FakeRenderBackend,
    FakeSkillRegistry,
    FakeStorage,
    FakeTTSProvider,
)

# 100s targets 4 segments (round(100_000 / 1000 / 28) == 4) -- enough to make fan-out and a
# single failure among several concurrent tasks meaningful, small enough to stay fast.
TARGET_DURATION_MS = 100_000


def _context(tmp_path: Path, *, tts: FakeTTSProvider, storage: FakeStorage) -> GraphContext:
    return GraphContext(
        llm=FakeLLMProvider(),
        tts=tts,
        storage=storage,
        skills=FakeSkillRegistry(),
        render=FakeRenderBackend(),
        working_dir=tmp_path / "work",
    )


def _job() -> VideoJob:
    return VideoJob(job_id="job-1", topic="SQL injection", target_duration_ms=TARGET_DURATION_MS)


async def test_a_full_run_narrates_every_segment_and_succeeds(tmp_path: Path) -> None:
    job = _job()
    fake_tts = FakeTTSProvider()
    fake_storage = FakeStorage()

    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "checkpoints.sqlite")) as saver:
        graph = build_graph(saver)
        config = {"configurable": {"thread_id": job.job_id}}
        context = _context(tmp_path, tts=fake_tts, storage=fake_storage)

        result = await graph.ainvoke(
            {"job": job, "segments": {}}, config, context=context, durability="sync"
        )

    result_job: VideoJob = result["job"]
    assert result_job.status == JobStatus.SUCCEEDED
    assert len(result_job.segments) == job.segment_count
    assert all(segment.duration_ms is not None for segment in result_job.segments)
    assert len(fake_storage.objects) == job.segment_count


async def test_a_killed_run_resumes_without_repeating_completed_segments(tmp_path: Path) -> None:
    job = _job()
    fake_tts = FakeTTSProvider()
    fake_storage = FakeStorage()
    # Fails whichever segment's task happens to call synthesize first -- deliberately not
    # ProviderUnavailable/RateLimited, which the node's own RetryPolicy would absorb before it
    # ever reached ainvoke. ProviderMisconfigured is never retried, so it reliably escapes.
    fake_tts.fail_next("synthesize", ProviderMisconfigured("bad voice, simulating a kill"))
    db_path = str(tmp_path / "checkpoints.sqlite")
    config = {"configurable": {"thread_id": job.job_id}}

    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        graph = build_graph(saver)
        context = _context(tmp_path, tts=fake_tts, storage=fake_storage)

        with pytest.raises(ProviderMisconfigured):
            await graph.ainvoke(
                {"job": job, "segments": {}}, config, context=context, durability="sync"
            )

    # FakeTTSProvider raises before logging the call, so the failing segment contributes nothing
    # here; every other segment's concurrent task still ran to completion in the same superstep.
    calls_before_resume = len(fake_tts.calls)
    assert calls_before_resume == job.segment_count - 1

    # A fresh saver connection and a freshly compiled graph -- the closest a same-process test can
    # get to "a new process reattached to the same checkpoint database."
    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        graph = build_graph(saver)
        context = _context(tmp_path, tts=fake_tts, storage=fake_storage)

        result = await graph.ainvoke(None, config, context=context, durability="sync")

    result_job: VideoJob = result["job"]
    assert result_job.status == JobStatus.SUCCEEDED
    assert len(result_job.segments) == job.segment_count
    assert all(segment.duration_ms is not None for segment in result_job.segments)

    # The whole point: total successful narrations equals the segment count, not more. Every
    # completed segment's synthesize call happened exactly once, even though one segment's task
    # failed and the whole run had to be re-invoked.
    assert len(fake_tts.calls) == job.segment_count
