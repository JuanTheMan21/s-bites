"""Job submission, listing, lookup, and resume (T19, T22).

Every route here is owner-scoped as of T38A. Note what that does *not* look like: there is no
``if job.owner_id != principal.owner_id: raise 404`` anywhere. The owner is part of the storage
key (``api/job_store.py``), so another user's job raises ``ObjectNotFound`` from the same
``except`` these routes already had -- which is why the "wrong owner gets a 404, never a 403"
rule holds here without anything to remember.
"""

import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from api.auth import CurrentPrincipal, MutatingPrincipal
from api.schemas import JobSubmission
from core.video_job import JobStatus, VideoJob
from interfaces import ObjectNotFound

router = APIRouter()


@router.post("/jobs", status_code=201, response_model=VideoJob)
async def submit_job(
    body: JobSubmission, request: Request, principal: MutatingPrincipal
) -> VideoJob:
    job = VideoJob(
        job_id=uuid4().hex,
        owner_id=principal.owner_id,
        topic=body.topic,
        target_duration_ms=body.target_duration_ms,
    )
    # The one write this API makes that can race another request -- two submissions landing in
    # the same event-loop tick both read-modify-write JobStore's index file. Everything else
    # (the runner's own saves) is already serial by construction (api/runner.py's docstring).
    async with request.app.state.index_lock:
        await request.app.state.job_store.save(job)
        await request.app.state.job_store.add_to_index(principal.owner_id, job.job_id)
    # The payload has always existed on QueuedJob and has always been `{}`; T38A is what it is
    # for. The worker cannot load an owner-scoped job record from a job_id alone, and this is how
    # it learns the owner -- no JobQueue signature change, and it already crosses Service Bus
    # correctly (interfaces/job_queue.py::check_serialisable).
    await request.app.state.adapters.queue.enqueue(job.job_id, {"owner_id": principal.owner_id})
    return job


@router.get("/jobs", response_model=list[VideoJob])
async def list_jobs(request: Request, principal: CurrentPrincipal) -> list[VideoJob]:
    return await request.app.state.job_store.list_all(principal.owner_id)


@router.get("/jobs/{job_id}", response_model=VideoJob)
async def get_job(job_id: str, request: Request, principal: CurrentPrincipal) -> VideoJob:
    try:
        return await request.app.state.job_store.load(principal.owner_id, job_id)
    except ObjectNotFound:
        raise HTTPException(404, f"no job {job_id!r}") from None


@router.post("/jobs/{job_id}/resume", response_model=VideoJob)
async def resume_job(job_id: str, request: Request, principal: MutatingPrincipal) -> VideoJob:
    try:
        job = await request.app.state.job_store.load(principal.owner_id, job_id)
    except ObjectNotFound:
        raise HTTPException(404, f"no job {job_id!r}") from None
    if job.status != JobStatus.FAILED:
        raise HTTPException(409, f"job {job_id!r} is {job.status.value}, not failed")
    # Flipped to queued before returning, same as submit_job -- otherwise this response (and any
    # GET poll landing inside the runner's up-to-1s dequeue interval) would still show "failed"
    # for a resume that has, in fact, already been accepted.
    job = job.model_copy(update={"status": JobStatus.QUEUED, "error": None})
    await request.app.state.job_store.save(job)
    # The runner tells a first attempt from a resume by asking the checkpointer whether this
    # job_id has a checkpoint at all (api/runner.py), so re-enqueueing the same id is the whole
    # mechanism -- no separate "resume" code path through the graph.
    await request.app.state.adapters.queue.enqueue(job.job_id, {"owner_id": principal.owner_id})
    return job


@router.get("/jobs/{job_id}/events")
async def stream_job_events(
    job_id: str, request: Request, principal: CurrentPrincipal
) -> EventSourceResponse:
    try:
        job = await request.app.state.job_store.load(principal.owner_id, job_id)
    except ObjectNotFound:
        raise HTTPException(404, f"no job {job_id!r}") from None

    bus = request.app.state.event_bus
    # A subscriber that connects after the run already finished -- a page refresh, a reconnect
    # after a network blip -- would otherwise get a fresh, empty queue that nothing will ever
    # publish to (the runner has already returned) and hang open forever. Terminal jobs skip
    # subscribing entirely and just report the status once.
    already_terminal = job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED)
    queue = None if already_terminal else await bus.subscribe(job_id)

    async def stage_events():
        if already_terminal or queue is None:
            yield {
                "event": "stage",
                "data": json.dumps({"job_status": job.status.value, "terminal": True}),
            }
            return
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield {"event": "stage", "data": json.dumps(item)}
        finally:
            await bus.unsubscribe(job_id, queue)

    return EventSourceResponse(stage_events())
