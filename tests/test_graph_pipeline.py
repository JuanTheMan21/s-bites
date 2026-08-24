"""The compiled graph's happy path: a job goes in, and every segment comes out narrated, measured,
tiered and authored.

The resume cases -- the DoD's real question, that a killed run does not repeat completed work --
live in ``test_graph_resume.py``, split out when this file crossed the 200-line ceiling. Shared
setup is in ``tests/graph_pipeline_fixtures.py``.

Everything here stays offline: fakes for every interface, no network.
"""

from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from core.graph import build_graph
from core.models import VideoJob
from core.slot_schemas import slot_schema_for
from tests.fakes import FakeStorage, FakeTTSProvider
from tests.graph_pipeline_fixtures import a_context, a_job, seeded_llm


async def test_a_full_run_narrates_every_segment_and_succeeds(tmp_path: Path) -> None:
    job = a_job()
    fake_tts = FakeTTSProvider()
    fake_storage = FakeStorage()

    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "checkpoints.sqlite")) as saver:
        graph = build_graph(saver)
        config = {"configurable": {"thread_id": job.job_id}}
        llm = seeded_llm(job.segment_count)
        context = a_context(tmp_path, tts=fake_tts, storage=fake_storage, llm=llm)

        result = await graph.ainvoke(
            {"job": job, "segments": {}}, config, context=context, durability="sync"
        )

    result_job: VideoJob = result["job"]
    assert result_job.status.value == "succeeded"
    assert len(result_job.segments) == job.segment_count
    assert all(segment.duration_ms is not None for segment in result_job.segments)
    assert len(fake_storage.objects) == job.segment_count

    # The whole T16 stretch, end to end: measured, then tiered, then authored against that measure.
    for segment in result_job.segments:
        assert segment.tier is not None
        assert segment.slots is not None
        # Stored as an untyped dict (D29), so the check that it is the *right* payload for this
        # segment's intent has to be made explicitly rather than by the type system.
        assert slot_schema_for(segment.visual_intent).model_validate(segment.slots)
