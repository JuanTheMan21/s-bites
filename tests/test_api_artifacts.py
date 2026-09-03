"""T21: artifacts served through Storage. DoD is "playback works identically under both
RUNTIME_ENV values" -- exercised here against FakeStorage's memory:// scheme, which (like
DiskStorage's file://, unlike BlobStorage's SAS URL) takes the byte-streaming branch, so this is
real coverage of the "local" code path, not just a smoke test against whichever fake is handy.
"""

from fastapi.testclient import TestClient

from api.app import create_app
from tests.api_fixtures import API_TEST_TARGET_DURATION_MS, FPS, FRAME_BUDGET, fake_adapters
from tests.graph_pipeline_fixtures import needs_ffmpeg
from tests.test_api_jobs import _wait_for_terminal


def test_video_before_a_job_finishes_404s() -> None:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        job_id = client.post("/jobs", json={"topic": "x"}).json()["job_id"]
        resp = client.get(f"/jobs/{job_id}/video")
    assert resp.status_code == 404


def test_video_of_an_unknown_job_404s() -> None:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        resp = client.get("/jobs/does-not-exist/video")
    assert resp.status_code == 404


@needs_ffmpeg
def test_video_streams_bytes_once_a_job_succeeds() -> None:
    adapters = fake_adapters()
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]
        finished = _wait_for_terminal(client, job_id)
        assert finished["status"] == "succeeded"

        video = client.get(f"/jobs/{job_id}/video")
        subtitles = client.get(f"/jobs/{job_id}/subtitles")

    assert video.status_code == 200
    assert video.headers["content-type"] == "video/mp4"
    assert len(video.content) > 0

    assert subtitles.status_code == 200
    assert subtitles.headers["content-type"].startswith("text/plain")


@needs_ffmpeg
def test_a_range_request_returns_206_with_only_the_requested_bytes() -> None:
    """T24: local-disk/FakeStorage's memory:// scheme took the byte-streaming branch with no
    Range support at all, which is what made <video> seeking silently not work against the
    project's primary day-to-day RUNTIME_ENV. api/byte_range.py closes that gap."""
    adapters = fake_adapters()
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]
        finished = _wait_for_terminal(client, job_id)
        assert finished["status"] == "succeeded"

        full = client.get(f"/jobs/{job_id}/video")
        ranged = client.get(f"/jobs/{job_id}/video", headers={"Range": "bytes=0-9"})

    assert ranged.status_code == 206
    assert ranged.content == full.content[:10]
    assert ranged.headers["content-range"] == f"bytes 0-9/{len(full.content)}"
    assert ranged.headers["accept-ranges"] == "bytes"
