"""T18M/D197: ``EventChannel.history`` and its replay in ``api/jobs.py::stream_job_events``.

Split out of ``test_api_events.py`` (T20's own suite, about events being observed as they
happen) once this file would have crossed the 200-line ceiling -- this is a genuinely separate
concern: not whether live events are observed, but whether a connection that arrives late (or
reconnects) sees everything that happened before it connected.
"""

from fastapi.testclient import TestClient

from api.app import create_app
from tests.api_fixtures import API_TEST_TARGET_DURATION_MS, FPS, FRAME_BUDGET, fake_adapters
from tests.graph_pipeline_fixtures import needs_ffmpeg
from tests.test_api_jobs import _wait_for_terminal


@needs_ffmpeg
def test_events_of_an_already_finished_job_replay_history_then_report_once() -> None:
    """Regression: a subscriber that connects after the run already ended -- a page refresh, a
    reconnect -- used to get a fresh, empty queue nothing would ever publish to, and the request
    hung open forever. A terminal job must still close (not hang) rather than stream forever.

    T18M/D197: it no longer reports "just the status" -- EventChannel.history now replays every
    event the run ever published (real progress the run genuinely made, no reason to hide it from
    a client that only connected after the fact), with the terminal status ping always last."""
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

    assert len(events) >= 1
    assert '"job_status": "succeeded"' in events[-1]
    assert '"terminal": true' in events[-1]


@needs_ffmpeg
def test_a_reconnecting_subscriber_gets_the_events_it_missed() -> None:
    """T18M/D197: confirmed live -- a real user's browser tab that connects to a job already
    mid-flight (a page refresh, a job opened from the list after it's been running a while) used
    to get NOTHING from before that moment: every phase timecode and the whole waveform are built
    entirely from received events, so real progress looked frozen/blank even though the job was
    running fine. First connection disconnects early (closing the stream, not waiting for the
    job to finish); a second, fresh connection must still see everything the first one saw, not
    start from a blank slate."""
    adapters = fake_adapters()
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]

        first_connection_events = []
        with client.stream("GET", f"/jobs/{job_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    first_connection_events.append(line[len("data:") :].strip())
                if len(first_connection_events) >= 3:
                    break  # disconnect early -- the job is still running past this point

        second_connection_events = []
        with client.stream("GET", f"/jobs/{job_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    second_connection_events.append(line[len("data:") :].strip())
                if len(second_connection_events) >= len(first_connection_events):
                    break

        _wait_for_terminal(client, job_id)

    assert second_connection_events[: len(first_connection_events)] == first_connection_events
