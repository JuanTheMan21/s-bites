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


@needs_ffmpeg
def test_resuming_during_an_automatic_retry_is_rejected_not_double_enqueued(monkeypatch) -> None:
    """Regression (project-reviewer, T24-T28 checkpoint): api/runner.py used to persist
    JobStatus.FAILED even for an attempt about to be auto-requeued -- indistinguishable, to any
    consumer reading persisted state rather than a live SSE stream, from a genuinely dead job.
    Most seriously, resume_job's own `status != FAILED` guard would accept a resume click during
    the retry window and enqueue a *second*, redundant run of the same job_id/thread (neither
    LocalJobQueue nor FakeJobQueue dedupe by job_id). Fixed by persisting QUEUED, not FAILED, for
    a requeued attempt -- mirroring what resume_job itself already sets on an explicit resume.
    """
    monkeypatch.setattr("api.runner.MAX_ATTEMPTS", 2)
    adapters = fake_adapters()
    adapters.tts.fail_next("synthesize", ProviderMisconfigured("simulated transient failure"))
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]

        # api/runner.py saves the requeued-attempt status before publishing the SSE event that
        # reports it -- by the time this event is observed here, GET already reflects the fix.
        with client.stream("GET", f"/jobs/{job_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:") and '"job_status": "failed"' in line:
                    break

        mid_retry = client.get(f"/jobs/{job_id}").json()
        resume_resp = client.post(f"/jobs/{job_id}/resume")

        finished = _wait_for_terminal(client, job_id)

    # Never observably "failed" to a fresh REST caller during the retry window -- the whole bug.
    assert mid_retry["status"] != "failed"
    # A resume attempt during that window is correctly rejected, not silently double-enqueued.
    assert resume_resp.status_code == 409
    assert finished["status"] == "succeeded"
    # One synthesize call per segment across both attempts combined -- inflated above 4 if the
    # rejected resume had actually enqueued a redundant second run.
    assert len(adapters.tts.calls) == 4
