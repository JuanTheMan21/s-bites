"""T20: stage transitions observed as they happen, sourced from graph.astream_events -- not a
bespoke event bus. Exercises api/events.py::summarize_node_event against the real langgraph
library (only the six interfaces underneath are fake), so this is real coverage of the one part
of T20 a mocked event stream could not catch: whether LangGraph's actual event shape is what the
summarizer assumes.
"""

from fastapi.testclient import TestClient

from api.app import create_app
from tests.api_fixtures import API_TEST_TARGET_DURATION_MS, FPS, FRAME_BUDGET, fake_adapters
from tests.graph_pipeline_fixtures import needs_ffmpeg
from tests.test_api_jobs import _wait_for_terminal


@needs_ffmpeg
def test_stage_events_are_observed_for_a_running_job() -> None:
    adapters = fake_adapters()
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]

        stage_events = []
        with client.stream("GET", f"/jobs/{job_id}/events") as stream:
            assert stream.status_code == 200
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    stage_events.append(line[len("data:") :].strip())
                if len(stage_events) >= 3:
                    break

        finished = _wait_for_terminal(client, job_id)

    assert finished["status"] == "succeeded"
    assert len(stage_events) >= 3
    # At least one recognisable node name made it through the summarizer as real JSON, not just
    # bytes that happened to arrive.
    assert any('"node"' in event for event in stage_events)


def test_events_of_an_unknown_job_404s() -> None:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    with TestClient(app) as client:
        resp = client.get("/jobs/does-not-exist/events")
    assert resp.status_code == 404


@needs_ffmpeg
def test_events_of_an_already_finished_job_report_once_and_do_not_hang() -> None:
    """Regression: a subscriber that connects after the run already ended -- a page refresh, a
    reconnect -- used to get a fresh, empty queue nothing would ever publish to, and the request
    hung open forever. A terminal job must report its status once and close instead."""
    adapters = fake_adapters()
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]
        finished = _wait_for_terminal(client, job_id)
        assert finished["status"] == "succeeded"

        events = []
        with client.stream("GET", f"/jobs/{job_id}/events") as stream:
            assert stream.status_code == 200
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    events.append(line[len("data:") :].strip())

    assert len(events) == 1
    assert '"job_status": "succeeded"' in events[0]
