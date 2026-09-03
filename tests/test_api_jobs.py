"""T19/T22: submission, listing, lookup, and resume, against tests/fakes/* only -- one real
end-to-end run through the whole app is T19's own DoD ("posting a job starts a real run and
returns an id"), and the resume tests are T22's.
"""

import time

from fastapi.testclient import TestClient

from api.app import create_app
from tests.api_fixtures import API_TEST_TARGET_DURATION_MS, FPS, FRAME_BUDGET, fake_adapters
from tests.graph_pipeline_fixtures import needs_ffmpeg


def _wait_for_terminal(client: TestClient, job_id: str, *, timeout_s: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while True:
        body = client.get(f"/jobs/{job_id}").json()
        if body["status"] in ("succeeded", "failed"):
            return body
        if time.monotonic() > deadline:
            raise AssertionError(f"job {job_id} still {body['status']!r} after {timeout_s}s")
        time.sleep(0.02)


@needs_ffmpeg
def test_submit_job_returns_id_and_starts_a_real_run() -> None:
    adapters = fake_adapters()
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        resp = client.post(
            "/jobs",
            json={"topic": "SQL injection", "target_duration_ms": API_TEST_TARGET_DURATION_MS},
        )
        assert resp.status_code == 201
        job_id = resp.json()["job_id"]
        assert resp.json()["status"] == "queued"

        finished = _wait_for_terminal(client, job_id)

    assert finished["status"] == "succeeded"
    assert finished["video_key"] is not None
    assert len(finished["segments"]) == 4


def test_submission_rejects_unknown_fields() -> None:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        resp = client.post("/jobs", json={"topic": "x", "made_up_field": 1})
    assert resp.status_code == 422


def test_get_unknown_job_404s() -> None:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        resp = client.get("/jobs/does-not-exist")
    assert resp.status_code == 404


def test_resume_of_unknown_job_404s() -> None:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        resp = client.post("/jobs/does-not-exist/resume")
    assert resp.status_code == 404


def test_resume_of_a_non_failed_job_is_rejected() -> None:
    """A job that is queued, running, or already succeeded has nothing to resume from -- 409,
    not a silent re-run. Whichever of those three this job happens to be by the time resume is
    called (the background runner races this call against fakes), none of them is 'failed', so
    the assertion holds regardless of exactly how far it got."""
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        submitted = client.post("/jobs", json={"topic": "x"}).json()
        resp = client.post(f"/jobs/{submitted['job_id']}/resume")
    assert resp.status_code == 409
