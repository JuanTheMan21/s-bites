"""T36: GET /jobs/{id}/scorm, against tests/fakes/* only."""

import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from api.app import create_app
from tests.api_fixtures import API_TEST_TARGET_DURATION_MS, FPS, FRAME_BUDGET, fake_adapters
from tests.graph_pipeline_fixtures import needs_ffmpeg
from tests.test_api_jobs import _wait_for_terminal


def test_scorm_before_a_job_finishes_404s() -> None:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        job_id = client.post("/jobs", json={"topic": "x"}).json()["job_id"]
        resp = client.get(f"/jobs/{job_id}/scorm")
    assert resp.status_code == 404


def test_scorm_of_an_unknown_job_404s() -> None:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        resp = client.get("/jobs/does-not-exist/scorm")
    assert resp.status_code == 404


@needs_ffmpeg
def test_scorm_package_is_downloadable_and_importable_once_a_job_succeeds() -> None:
    adapters = fake_adapters()
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]
        finished = _wait_for_terminal(client, job_id)
        assert finished["status"] == "succeeded"

        resp = client.get(f"/jobs/{job_id}/scorm")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert f"{job_id}.zip" in resp.headers["content-disposition"]

    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
        assert "imsmanifest.xml" in zf.namelist()
        assert "video.mp4" in zf.namelist()
        assert len(zf.read("video.mp4")) > 0
