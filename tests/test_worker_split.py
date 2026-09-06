"""T34: proves the SSE endpoint still updates live when the process running ``JobRunner`` is not
the process serving requests -- the exact property `api/main.py`'s ``RUN_INPROC_WORKER=false`` /
``worker.py`` pair exists for.

Two ``create_app`` instances share one ``Adapters`` bundle: ``api_app`` (``run_worker=False``,
what serves ``/jobs/{id}/events``) and ``worker_app`` (``run_worker=True``, standing in for
``worker.py`` -- its own lifespan starts the ``JobRunner`` that actually dequeues and drives the
graph). Nothing here is shared *state* between them beyond the same fake backends -- exactly what
two real processes pointed at the same Service Bus queue and Blob container would share. Before
T34, ``JobEventBus`` lived only in-process; had this split shipped without the T34 event channel,
this test is exactly the one that would have failed -- the SSE stream would open and then never
receive a single event, because nothing published in ``worker_app``'s process could ever reach a
subscriber registered against ``api_app``'s.
"""

from fastapi.testclient import TestClient

from api.app import create_app
from tests.api_fixtures import API_TEST_TARGET_DURATION_MS, FPS, FRAME_BUDGET, fake_adapters
from tests.graph_pipeline_fixtures import needs_ffmpeg
from tests.test_api_jobs import _wait_for_terminal


@needs_ffmpeg
def test_sse_receives_progress_from_a_runner_in_a_different_app_instance() -> None:
    adapters = fake_adapters()
    api_app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS, run_worker=False)
    worker_app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS, run_worker=True)

    with TestClient(worker_app), TestClient(api_app) as api_client:
        job_id = api_client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]

        stage_events = []
        with api_client.stream("GET", f"/jobs/{job_id}/events") as stream:
            assert stream.status_code == 200
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    stage_events.append(line[len("data:") :].strip())
                if len(stage_events) >= 3:
                    break

        finished = _wait_for_terminal(api_client, job_id)

    assert finished["status"] == "succeeded"
    assert len(stage_events) >= 3
    assert any('"node"' in event for event in stage_events)
