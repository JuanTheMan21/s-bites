"""T14's definition of done, now that the graph has two fan-outs: a killed run resumes without
repeating work that already completed.

A real, file-backed ``AsyncSqliteSaver`` rather than the in-memory saver, deliberately -- only a
saver backed by something outside the process can stand in for a process actually being killed.

Both fan-outs get their own case. The second one (``author_scene``) reuses machinery the first one
already proved, but "the mechanism is the same" is an argument, not a test, and this project has
been wrong about exactly that kind of argument before (D57, D62, D67, D73).
"""

from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel

from core.graph import build_graph
from core.models import VideoJob
from core.slot_schemas import TitleCardSlots
from interfaces import ProviderMisconfigured
from interfaces.llm_provider import T
from tests.fakes import FakeLLMProvider, FakeStorage, FakeTTSProvider
from tests.graph_pipeline_fixtures import a_context, a_job, seeded_llm, slot_payloads


class FailsOnceForSchema(FakeLLMProvider):
    """A ``FakeLLMProvider`` that fails the first request for one particular schema.

    ``fail_next`` arms the *next* call whatever it is, which in a full run is always
    ``plan_segments``' outline call -- far upstream of what this file needs to interrupt. Keying
    the failure to the schema is what lets a test kill the run inside the second fan-out
    specifically, since ``author_scene`` is the only step that ever asks for a slot payload.
    """

    def __init__(self, responses: list[BaseModel], fail_schema: type[BaseModel]) -> None:
        super().__init__(responses)
        self._fail_schema = fail_schema
        self._fired = False

    async def generate(self, prompt: str, schema: type[T], *, system: str | None = None) -> T:
        if schema is self._fail_schema and not self._fired:
            self._fired = True
            # Never retried by either policy, so it reliably escapes to the caller -- the same
            # reason the TTS case below reaches for ProviderMisconfigured.
            raise ProviderMisconfigured("simulating a kill during scene authoring")
        return await super().generate(prompt, schema, system=system)


def _scene_calls(llm: FakeLLMProvider) -> int:
    return sum(1 for call in llm.calls if call.schema is TitleCardSlots)


async def test_a_kill_during_narration_does_not_repeat_completed_segments(tmp_path: Path) -> None:
    job = a_job()
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
        context = a_context(
            tmp_path, tts=fake_tts, storage=fake_storage, llm=seeded_llm(job.segment_count)
        )

        with pytest.raises(ProviderMisconfigured):
            await graph.ainvoke(
                {"job": job, "segments": {}}, config, context=context, durability="sync"
            )

    # FakeTTSProvider raises before logging the call, so the failing segment contributes nothing
    # here; every other segment's concurrent task still ran to completion in the same superstep.
    assert len(fake_tts.calls) == job.segment_count - 1

    # A fresh saver connection and a freshly compiled graph -- the closest a same-process test can
    # get to "a new process reattached to the same checkpoint database."
    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        graph = build_graph(saver)
        # plan_segments already completed and checkpointed before the kill (D68), so resume never
        # re-invokes it and no outline or narration response is needed here. assign_tiers and
        # author_scene, by contrast, never ran at all -- the kill happened upstream of both -- so
        # the resumed run still makes one scene-authoring call per segment.
        context = a_context(
            tmp_path,
            tts=fake_tts,
            storage=fake_storage,
            llm=FakeLLMProvider(slot_payloads(job.segment_count)),
        )

        result = await graph.ainvoke(None, config, context=context, durability="sync")

    result_job: VideoJob = result["job"]
    assert result_job.status.value == "succeeded"
    assert len(result_job.segments) == job.segment_count
    assert all(segment.duration_ms is not None for segment in result_job.segments)
    assert all(segment.tier is not None for segment in result_job.segments)
    assert all(segment.slots is not None for segment in result_job.segments)

    # The whole point: total successful narrations equals the segment count, not more. Every
    # completed segment's synthesize call happened exactly once, even though one segment's task
    # failed and the whole run had to be re-invoked.
    assert len(fake_tts.calls) == job.segment_count


async def test_a_kill_during_scene_authoring_does_not_repeat_narration(tmp_path: Path) -> None:
    """The second fan-out's version of the same guarantee, and the more expensive one to get
    wrong: by the time ``author_scene`` runs, every segment has already been narrated by a *billed*
    TTS call and measured. A resume that re-ran the graph from the top would pay for all of it
    again -- and, worse, re-measure, which is the one number Invariant 1 says must not move.
    """
    job = a_job()
    fake_tts = FakeTTSProvider()
    fake_storage = FakeStorage()
    db_path = str(tmp_path / "checkpoints.sqlite")
    config = {"configurable": {"thread_id": job.job_id}}

    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        graph = build_graph(saver)
        llm = FailsOnceForSchema(seeded_llm(job.segment_count).responses, TitleCardSlots)
        context = a_context(tmp_path, tts=fake_tts, storage=fake_storage, llm=llm)

        with pytest.raises(ProviderMisconfigured):
            await graph.ainvoke(
                {"job": job, "segments": {}}, config, context=context, durability="sync"
            )

    # Everything upstream of the failure completed: every segment narrated exactly once.
    assert len(fake_tts.calls) == job.segment_count
    scene_calls_before_resume = _scene_calls(llm)
    assert scene_calls_before_resume == job.segment_count - 1

    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        graph = build_graph(saver)
        resumed_llm = FakeLLMProvider(slot_payloads(job.segment_count))
        context = a_context(tmp_path, tts=fake_tts, storage=fake_storage, llm=resumed_llm)

        result = await graph.ainvoke(None, config, context=context, durability="sync")

    result_job: VideoJob = result["job"]
    assert result_job.status.value == "succeeded"
    assert all(segment.slots is not None for segment in result_job.segments)

    # Not one further TTS call: the resume picked up inside the second fan-out, not at the top.
    assert len(fake_tts.calls) == job.segment_count
    # And only the failed segment's scene was re-authored -- the other tasks in that superstep
    # keep the work they had already completed, exactly as the first fan-out's do.
    assert _scene_calls(resumed_llm) == 1
