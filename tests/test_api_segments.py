"""T27: per-segment audio, clip, and scene, addressed by job_id + index -- api/segments.py."""

from fastapi.testclient import TestClient

from api.app import create_app
from tests.api_fixtures import API_TEST_TARGET_DURATION_MS, FPS, FRAME_BUDGET, fake_adapters
from tests.graph_pipeline_fixtures import needs_ffmpeg
from tests.test_api_jobs import _wait_for_terminal


@needs_ffmpeg
def test_segment_audio_clip_and_scene_are_all_individually_fetchable() -> None:
    adapters = fake_adapters()
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]
        finished = _wait_for_terminal(client, job_id)
        assert finished["status"] == "succeeded"

        audio = client.get(f"/jobs/{job_id}/segments/0/audio")
        clip = client.get(f"/jobs/{job_id}/segments/0/clip")
        scene = client.get(f"/jobs/{job_id}/segments/0/scene")

    assert audio.status_code == 200
    assert len(audio.content) > 0

    assert clip.status_code == 200
    assert clip.headers["content-type"] == "video/mp4"
    assert len(clip.content) > 0

    assert scene.status_code == 200
    assert scene.headers["content-type"].startswith("application/json")
    # Deliberately not asserting on the scene's shape -- that would couple this test to whatever
    # T18 currently produces. Only that a completed segment's authoring source of truth arrives.
    assert scene.json() is not None


def test_segment_artifacts_of_an_unknown_job_404() -> None:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        assert client.get("/jobs/does-not-exist/segments/0/audio").status_code == 404
        assert client.get("/jobs/does-not-exist/segments/0/clip").status_code == 404
        assert client.get("/jobs/does-not-exist/segments/0/scene").status_code == 404


@needs_ffmpeg
def test_segment_artifacts_of_an_out_of_range_index_404() -> None:
    adapters = fake_adapters()
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]
        _wait_for_terminal(client, job_id)

        resp = client.get(f"/jobs/{job_id}/segments/999/clip")

    assert resp.status_code == 404


def test_segment_artifacts_before_a_job_progresses_404() -> None:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        job_id = client.post("/jobs", json={"topic": "x"}).json()["job_id"]
        # Submitted, not yet run far enough for plan_segments to have produced any segments --
        # index 0 does not exist on this job yet, same 404 as an out-of-range index.
        resp = client.get(f"/jobs/{job_id}/segments/0/clip")
    assert resp.status_code == 404
