"""Durable job records (T22), addressed through ``Storage`` the same way every other artifact
is -- not a new database dependency. ``Storage`` has no ``list()`` (nothing under ``core/`` has
ever needed one, and adding one is real adapter-parity work across three implementations with
nothing else asking for it yet), so a single small index file stands in for one.
"""

import json

from core.models import VideoJob
from interfaces import ObjectNotFound, Storage

JOB_KEY = "jobs/{job_id}/job.json"
INDEX_KEY = "jobs/index.json"


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
        key = JOB_KEY.format(job_id=job.job_id)
        await self._storage.put_bytes(
            key, job.model_dump_json().encode(), content_type="application/json"
        )

    async def load(self, job_id: str) -> VideoJob:
        """Raises ``ObjectNotFound`` for an unknown id -- the same exception ``Storage`` itself
        raises, so a caller already handling that family handles this for free."""
        key = JOB_KEY.format(job_id=job_id)
        data = await self._storage.get_bytes(key)
        return VideoJob.model_validate_json(data)

    async def add_to_index(self, job_id: str) -> None:
        ids = await self._index_ids()
        if job_id not in ids:
            ids.append(job_id)
            await self._storage.put_bytes(
                INDEX_KEY, json.dumps(ids).encode(), content_type="application/json"
            )

    async def list_all(self) -> list[VideoJob]:
        jobs = []
        for job_id in await self._index_ids():
            try:
                jobs.append(await self.load(job_id))
            except ObjectNotFound:
                # The index and a job's own record are two writes, not one -- a process killed
                # between them leaves an id with nothing behind it. Skipped rather than raised:
                # one missing record should not 500 a listing of everything else.
                continue
        return jobs

    async def _index_ids(self) -> list[str]:
        try:
            data = await self._storage.get_bytes(INDEX_KEY)
        except ObjectNotFound:
            return []
        return json.loads(data)
