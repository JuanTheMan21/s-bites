"""T20: stage transitions observed as they happen, sourced from graph.astream_events -- not a
bespoke event bus. Exercises api/events.py::summarize_node_event against the real langgraph
library (only the six interfaces underneath are fake), so this is real coverage of the one part
of T20 a mocked event stream could not catch: whether LangGraph's actual event shape is what the
summarizer assumes.
"""

from fastapi.testclient import TestClient

from api.app import create_app
from interfaces import ProviderMisconfigured
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


@needs_ffmpeg
def test_segment_data_appears_incrementally_not_only_after_the_job_finishes() -> None:
    """Regression: api/runner.py used to call job_store.save() exactly twice per run -- once at
    the very start (segments still empty), once after the whole graph finished -- and even after
    a first attempt at fixing that added more save() calls, every one of them still carried an
    empty segments[] until the very last: `state["job"].segments` (the pydantic list) is *only*
    ever populated by finalize.py, at the end. The fan-out's real progress lives in a *separate*
    state channel, `state["segments"]` (a dict merged by core/graph/state.py::merge_segments), so
    a correct fix has to assemble the same way finalize.py itself does. Confirmed the actual save
    sequence directly (offline, not part of the suite): segments appear at their full length,
    unfilled, right after plan_segments; duration_ms fills in next (synthesize_segment); tier
    lands after that (assign_tiers) -- a genuinely progressive fill, not one big jump.

    Intercepts JobStore.save() directly rather than racing a live SSE stream against a REST GET
    call -- against fakes, a whole 4-segment job finishes fast enough that the two race
    unpredictably, which would make an assertion pass or fail on timing luck rather than on
    whether the fix actually works. Recording every save() call's data is deterministic
    regardless of timing.
    """
    adapters = fake_adapters()
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    saved_segment_counts: list[int] = []
    tiered_counts: list[int] = []
    store = app.state.job_store
    original_save = store.save

    async def recording_save(job):
        saved_segment_counts.append(len(job.segments))
        tiered_counts.append(sum(1 for s in job.segments if s.tier is not None))
        await original_save(job)

    store.save = recording_save

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]
        finished = _wait_for_terminal(client, job_id)

    assert finished["status"] == "succeeded"
    # The old behaviour was exactly two saves (RUNNING at start, the finished snapshot), both with
    # zero segments until the last -- more saves than that, with the full-length segment list
    # already present and tiered before the very last save, is the fix.
    assert len(saved_segment_counts) > 2
    assert any(count == 4 for count in saved_segment_counts[:-1])
    assert any(count == 4 for count in tiered_counts[:-1])


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
    assert '"terminal": true' in events[0]


@needs_ffmpeg
def test_a_dead_lettered_failure_reports_terminal_true_and_records_the_error(monkeypatch) -> None:
    """T24: a client cannot otherwise tell a genuinely final failure from one that is about to be
    auto-requeued (both publish an identical {"job_status": "failed"}) -- the stream staying open
    is the only other signal, which is not observable without a timeout guess. `terminal` makes
    it explicit, and VideoJob.error gives T28's failure surface something to show besides the
    word "failed"."""
    monkeypatch.setattr("api.runner.MAX_ATTEMPTS", 1)
    adapters = fake_adapters()
    adapters.tts.fail_next("synthesize", ProviderMisconfigured("simulated failure"))
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]

        events = []
        with client.stream("GET", f"/jobs/{job_id}/events") as stream:
            assert stream.status_code == 200
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    events.append(line[len("data:") :].strip())

        finished = client.get(f"/jobs/{job_id}").json()

    assert finished["status"] == "failed"
    assert finished["error"] is not None
    assert "simulated failure" in finished["error"]
    failure_events = [e for e in events if '"job_status": "failed"' in e]
    assert len(failure_events) == 1
    assert '"terminal": true' in failure_events[0]


@needs_ffmpeg
def test_a_retryable_failure_reports_terminal_false_and_the_stream_stays_open(monkeypatch) -> None:
    monkeypatch.setattr("api.runner.MAX_ATTEMPTS", 2)
    adapters = fake_adapters()
    adapters.tts.fail_next("synthesize", ProviderMisconfigured("simulated failure"))
    app = create_app(adapters, frame_budget=FRAME_BUDGET, fps=FPS)

    with TestClient(app) as client:
        job_id = client.post(
            "/jobs", json={"topic": "x", "target_duration_ms": API_TEST_TARGET_DURATION_MS}
        ).json()["job_id"]

        events = []
        with client.stream("GET", f"/jobs/{job_id}/events") as stream:
            assert stream.status_code == 200
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    events.append(line[len("data:") :].strip())
                # Stop once both the retryable failure and the eventual success have arrived --
                # the stream stays open across the retry, so nothing else closes it for us.
                statuses = [e for e in events if '"job_status"' in e]
                if len(statuses) >= 2:
                    break

        finished = _wait_for_terminal(client, job_id)

    assert finished["status"] == "succeeded"
    statuses = [e for e in events if '"job_status"' in e]
    assert '"job_status": "failed"' in statuses[0]
    assert '"terminal": false' in statuses[0]
    assert '"job_status": "succeeded"' in statuses[1]
    assert '"terminal": true' in statuses[1]
