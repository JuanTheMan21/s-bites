"""Durable job records (T22), addressed through ``Storage`` the same way every other artifact
is -- not a new database dependency. ``Storage`` has no ``list()`` (nothing under ``core/`` has
ever needed one, and adding one is real adapter-parity work across three implementations with
nothing else asking for it yet), so a small index file stands in for one.

**Owner-scoped since T38A, and that is what enforces ownership.** D173 chose a Blob key prefix
over a real database for exactly this ("no new service, no migration, no second data store"). The
payoff is that ``load`` cannot be called without an owner, so another user's job is not "found and
then rejected" -- it is genuinely not there, and ``ObjectNotFound`` becomes a 404 through the
error path every route already has. The rule that a wrong owner must get a 404 rather than a 403,
so a job's existence is not leaked, is therefore structural: there is no check on any of the eleven
routes that a future route could forget to copy. Same spirit as ``scene_author`` taking
``duration_ms`` as a required parameter so calling it early is a type error.

The index is now per owner too, which additionally makes listing *cheaper* than it was before --
``list_all`` no longer loads every job in the system to show one user their own.
"""

import json

from core.video_job import VideoJob
from interfaces import ObjectNotFound, Storage

JOB_KEY = "jobs/{owner_id}/{job_id}/job.json"
INDEX_KEY = "jobs/{owner_id}/index.json"


class JobStore:
    """One job's full state, plus the flat list of ids that makes listing possible.

    Not safe under concurrent writers on its own -- ``add_to_index``'s read-modify-write can
    race two simultaneous submissions. The API layer (``api/jobs.py``) serialises submissions
    with a single ``asyncio.Lock`` rather than this class doing so, since only that one caller
    ever needs it: every other write here (``save`` alone, from the single-worker runner) is
    already serial by construction.
    """

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    async def save(self, job: VideoJob) -> None:
        """The owner comes off the job itself, so a job can never be written to a different
        owner's prefix than the one it belongs to."""
        key = JOB_KEY.format(owner_id=_owner_of(job), job_id=job.job_id)
        await self._storage.put_bytes(
            key, job.model_dump_json().encode(), content_type="application/json"
        )

    async def load(self, owner_id: str, job_id: str) -> VideoJob:
        """Raises ``ObjectNotFound`` for an unknown id **or an id owned by someone else** -- the
        same exception ``Storage`` itself raises, so a caller already handling that family
        handles both for free, and cannot accidentally distinguish the two cases in its response.
        """
        key = JOB_KEY.format(owner_id=owner_id, job_id=job_id)
        data = await self._storage.get_bytes(key)
        return VideoJob.model_validate_json(data)

    async def add_to_index(self, owner_id: str, job_id: str) -> None:
        ids = await self._index_ids(owner_id)
        if job_id not in ids:
            ids.append(job_id)
            await self._storage.put_bytes(
                INDEX_KEY.format(owner_id=owner_id),
                json.dumps(ids).encode(),
                content_type="application/json",
            )

    async def list_all(self, owner_id: str) -> list[VideoJob]:
        jobs = []
        for job_id in await self._index_ids(owner_id):
            try:
                jobs.append(await self.load(owner_id, job_id))
            except ObjectNotFound:
                # The index and a job's own record are two writes, not one -- a process killed
                # between them leaves an id with nothing behind it. Skipped rather than raised:
                # one missing record should not 500 a listing of everything else.
                continue
        return jobs

    async def _index_ids(self, owner_id: str) -> list[str]:
        try:
            data = await self._storage.get_bytes(INDEX_KEY.format(owner_id=owner_id))
        except ObjectNotFound:
            return []
        return json.loads(data)


def _owner_of(job: VideoJob) -> str:
    if not job.owner_id:
        # Reachable only by constructing a VideoJob by hand and saving it: every API submission
        # stamps an owner. Raised rather than defaulted, because a job silently written under a
        # placeholder owner would be invisible to the user who submitted it, with no error.
        raise ValueError(f"job {job.job_id!r} has no owner_id and cannot be stored")
    return job.owner_id
