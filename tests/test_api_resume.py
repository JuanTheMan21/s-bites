"""T22's own DoD: a failed job resumes via the API without recomputing finished segments.

``MAX_ATTEMPTS`` is monkeypatched to 1 so the induced failure dead-letters on the first attempt
instead of the runner's own automatic requeue racing this test to the same recovery -- the point
here is the *explicit* ``POST /jobs/{id}/resume`` path, not the automatic one.
"""

from fastapi.testclient import TestClient

from api.app import create_app
from interfaces import ProviderMisconfigured
from tests.api_fixtures import API_TEST_TARGET_DURATION_MS, FPS, FRAME_BUDGET, fake_adapters
from tests.graph_pipeline_fixtures import needs_ffmpeg
from tests.test_api_jobs import _wait_for_terminal


@needs_ffmpeg
def test_resume_recovers_a_dead_lettered_job_without_re_synthesizing(monkeypatch) -> None:
    monkeypatch.setattr("api.runner.MAX_ATTEMPTS", 1)
    adapters = fake_adapters()
    # Whichever segment's task reaches synthesize first fails once; the other three complete
    # normally in the same fan-out (tests/test_graph_resume.py's identical setup already proves
    # this is how a real checkpointer-backed run behaves under concurrent Send tasks).
    adapters.tts.fail_next("synthesize", ProviderMisconfigured("simulated failure"))
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        submitted = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()
        job_id = submitted["job_id"]

        first_attempt = _wait_for_terminal(client, job_id)
        assert first_attempt["status"] == "failed"

        resp = client.post(f"/jobs/{job_id}/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"  # not stale "failed" from before the resume

        finished = _wait_for_terminal(client, job_id)

    assert finished["status"] == "succeeded"
    assert finished["video_key"] is not None
    # The whole point: one synthesize call per segment, total, across both attempts combined --
    # not one extra for the segment that had already succeeded before the kill.
    assert len(adapters.tts.calls) == 4


@needs_ffmpeg
def test_a_failure_before_the_first_checkpoint_still_recovers_on_retry(monkeypatch) -> None:
    """Regression: an earlier version of api/runner.py inferred "first attempt" from whether
    checkpoints.sqlite already existed on disk -- but AsyncSqliteSaver.from_conn_string creates
    that file the instant it connects, before any checkpoint is ever written. A failure this
    early (plan_segments, the graph's first node, before any Send fan-out has produced a single
    checkpointed superstep) made every retry after the first look like a resume with nothing to
    resume from, crashing on EmptyInputError until the job dead-lettered -- permanently, since
    the explicit resume endpoint re-enqueues into the exact same broken check.
    """
    monkeypatch.setattr("api.runner.MAX_ATTEMPTS", 2)
    adapters = fake_adapters()
    adapters.llm.fail_next(
        "generate", ProviderMisconfigured("simulated failure, zero checkpoints written yet")
    )
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]
        finished = _wait_for_terminal(client, job_id)

    assert finished["status"] == "succeeded"
