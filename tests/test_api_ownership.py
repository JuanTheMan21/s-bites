"""T38A: a signed-in user can only ever see, list, or download their own jobs. This is the task's
DoD.

Asserted over **every** job-scoped route rather than a representative sample. The whole claim
being made is that ownership is structural -- part of the storage key, not a check each route
performs -- so a test covering three routes would not actually be testing it.

The assertion is also deliberately stronger than "not 200": a non-owner must get the same status
*and the same body* as they would for a job id that never existed, compared modulo the id itself.
A 403, or a differently-worded 404, would confirm the job is real, which is exactly the leak the
task text calls out.

No pipeline runs here -- the job record and its artifacts are seeded straight into the fakes, so
this stays a test about authorisation and nothing else.
"""

from typing import Any

from fastapi.testclient import TestClient

from api.job_store import JobStore
from core.graph.nodes.synthesize import SEGMENT_AUDIO_KEY
from core.models import Importance, Segment, Tier, VisualIntent
from core.video_job import JobStatus, VideoJob
from tests.api_fixtures import authenticated_app, bearer

OWNER_A = "11111111-1111-1111-1111-111111111111.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OWNER_B = "22222222-2222-2222-2222-222222222222.bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

JOB_ID = "job-owned-by-a"
ABSENT_ID = "no-such-job"
VIDEO_KEY = f"{JOB_ID}/final.mp4"
SUBTITLES_KEY = f"{JOB_ID}/final.srt"
CLIP_KEY = f"{JOB_ID}/segments/0/clip.mp4"

# Every route that takes a job_id. Kept as one list so a route added later without ownership
# shows up here as a visible omission rather than passing unnoticed.
JOB_SCOPED_ROUTES = [
    ("GET", "/jobs/{job_id}"),
    ("GET", "/jobs/{job_id}/events"),
    ("GET", "/jobs/{job_id}/video"),
    ("GET", "/jobs/{job_id}/subtitles"),
    ("GET", "/jobs/{job_id}/scorm"),
    ("GET", "/jobs/{job_id}/segments/0/audio"),
    ("GET", "/jobs/{job_id}/segments/0/clip"),
    ("GET", "/jobs/{job_id}/segments/0/scene"),
    ("POST", "/jobs/{job_id}/resume"),
]


def _seeded_job(owner_id: str) -> VideoJob:
    return VideoJob(
        job_id=JOB_ID,
        owner_id=owner_id,
        topic="how a hash table works",
        status=JobStatus.SUCCEEDED,
        video_key=VIDEO_KEY,
        subtitles_key=SUBTITLES_KEY,
        segments=[
            Segment(
                index=0,
                title="Buckets",
                summary="what a bucket is",
                visual_intent=VisualIntent.TITLE_CARD,
                importance=Importance.MAJOR,
                narration="a bucket holds entries",
                duration_ms=3000,
                tier=Tier.STATIC,
                clip_key=CLIP_KEY,
                scene={"layout": "SINGLE", "blocks": []},
            )
        ],
    )


async def _seed(app, owner_id: str) -> None:
    storage = app.state.adapters.storage
    store = JobStore(storage)
    await store.save(_seeded_job(owner_id))
    await store.add_to_index(owner_id, JOB_ID)
    for key in (VIDEO_KEY, SUBTITLES_KEY, CLIP_KEY):
        await storage.put_bytes(key, b"artifact-bytes", content_type="application/octet-stream")
    await storage.put_bytes(
        SEGMENT_AUDIO_KEY.format(job_id=JOB_ID, index=0), b"RIFF", content_type="audio/wav"
    )


def _as_if_absent(body: Any) -> Any:
    """The real job's id, substituted into a response that was about a non-existent one -- both
    bodies quote back whichever id was asked for, and that is not a leak."""
    if isinstance(body, dict):
        return {key: _as_if_absent(value) for key, value in body.items()}
    if isinstance(body, list):
        return [_as_if_absent(item) for item in body]
    if isinstance(body, str):
        return body.replace(ABSENT_ID, JOB_ID)
    return body


async def test_every_job_scoped_route_hides_another_users_job() -> None:
    app = authenticated_app()
    with TestClient(app) as client:
        await _seed(app, OWNER_A)

        for method, template in JOB_SCOPED_ROUTES:
            path = template.format(job_id=JOB_ID)

            mine = client.request(method, path, headers=bearer(OWNER_A))
            assert mine.status_code != 404, f"{method} {path} should be visible to its owner"

            theirs = client.request(method, path, headers=bearer(OWNER_B))
            assert theirs.status_code == 404, f"{method} {path} leaked to a non-owner"

            absent = client.request(
                method, template.format(job_id=ABSENT_ID), headers=bearer(OWNER_B)
            )
            assert theirs.status_code == absent.status_code, f"{method} {path} status differs"
            assert theirs.json() == _as_if_absent(absent.json()), (
                f"{method} {path} tells a non-owner that the job exists"
            )


async def test_listing_shows_only_your_own_jobs() -> None:
    app = authenticated_app()
    with TestClient(app) as client:
        await _seed(app, OWNER_A)

        mine = client.get("/jobs", headers=bearer(OWNER_A))
        assert [job["job_id"] for job in mine.json()] == [JOB_ID]

        theirs = client.get("/jobs", headers=bearer(OWNER_B))
        assert theirs.json() == []


async def test_two_users_can_hold_jobs_with_the_same_id_without_colliding() -> None:
    """Ids are uuid4 in practice, so this will not happen by accident -- but if the owner were
    *not* part of the key, one user's record would silently overwrite the other's, and this is the
    cheapest way to pin that it is."""
    app = authenticated_app()
    with TestClient(app) as client:
        await _seed(app, OWNER_A)
        await _seed(app, OWNER_B)

        for owner in (OWNER_A, OWNER_B):
            body = client.get(f"/jobs/{JOB_ID}", headers=bearer(owner)).json()
            assert body["owner_id"] == owner


async def test_a_submitted_job_is_stamped_with_its_submitter() -> None:
    app = authenticated_app()
    with TestClient(app) as client:
        created = client.post(
            "/jobs",
            json={"topic": "anything", "target_duration_ms": 100_000},
            headers=bearer(OWNER_A),
        )
        assert created.status_code == 201
        assert created.json()["owner_id"] == OWNER_A

        # And the worker can still find it: a job_id alone no longer addresses a job record, so
        # the owner has to reach the runner through the queue payload.
        queued = await app.state.adapters.queue.dequeue(timeout_s=1.0)
        assert queued is not None
        assert queued.payload == {"owner_id": OWNER_A}
