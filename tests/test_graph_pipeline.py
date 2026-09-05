"""The compiled graph's happy path: a job goes in, and every segment comes out narrated, measured,
tiered, authored, rendered, muxed, and concatenated into one playable video.

The resume cases -- the DoD's real question, that a killed run does not repeat completed work --
live in ``test_graph_resume.py``, split out when this file crossed the 200-line ceiling. Shared
setup is in ``tests/graph_pipeline_fixtures.py``.

No network, but real ffmpeg since T18: ``render_scene``/``finalize`` are now part of the graph's
happy path, and ``tests/graph_pipeline_fixtures.py``'s zero frame budget keeps every segment on
Tier 0, which renders through real ffmpeg (``mux/frames_to_clip.py``) rather than
``FakeRenderBackend.render``'s placeholder bytes.
"""

from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from core.graph import build_graph
from core.scene_schemas import ComposedScene
from core.video_job import VideoJob
from tests.fakes import FakeStorage, FakeTTSProvider
from tests.graph_pipeline_fixtures import a_context, a_job, needs_ffmpeg, seeded_llm


@needs_ffmpeg
async def test_a_full_run_narrates_every_segment_and_succeeds(tmp_path: Path) -> None:
    job = a_job()
    # Comfortably longer than 2x mux.concat_segments.DEFAULT_TRANSITION_S (identical across
    # segments so the concurrent fan-out's non-deterministic pop order can't mismatch one to the
    # wrong segment) -- FakeTTSProvider's own text-length estimate would otherwise produce
    # sub-second durations these placeholder narrations are far too short for a real crossfade.
    fake_tts = FakeTTSProvider(durations=[3000] * job.segment_count)
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
    # One narration WAV and one clip per segment, plus the one final video and its SRT sidecar
    # (T18A).
    assert len(fake_storage.objects) == 2 * job.segment_count + 2

    # The whole T16 stretch, end to end: measured, then tiered, then authored against that measure.
    for segment in result_job.segments:
        assert segment.tier is not None
        assert segment.scene is not None
        # Stored as an untyped dict (D29), so the check that it is a well-formed scene has to be
        # made explicitly rather than by the type system.
        assert ComposedScene.model_validate(segment.scene)
        assert segment.clip_key is not None
        assert segment.clip_key in fake_storage.objects

    # T18's own new ground: a real, non-empty, playable final video, persisted through Storage.
    assert result_job.video_key is not None
    assert result_job.video_key in fake_storage.objects
    assert len(fake_storage.objects[result_job.video_key]) > 0
