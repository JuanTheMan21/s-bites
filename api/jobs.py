"""Job submission, listing, lookup, and resume (T19, T22)."""

import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from api.schemas import JobSubmission
from core.models import JobStatus, VideoJob
from interfaces import ObjectNotFound

router = APIRouter()


@router.post("/jobs", status_code=201, response_model=VideoJob)
async def submit_job(body: JobSubmission, request: Request) -> VideoJob:
    job = VideoJob(job_id=uuid4().hex, topic=body.topic, target_duration_ms=body.target_duration_ms)
    # The one write this API makes that can race another request -- two submissions landing in
    # the same event-loop tick both read-modify-write JobStore's index file. Everything else
    # (the runner's own saves) is already serial by construction (api/runner.py's docstring).
    async with request.app.state.index_lock:
        await request.app.state.job_store.save(job)
        await request.app.state.job_store.add_to_index(job.job_id)
    await request.app.state.adapters.queue.enqueue(job.job_id, {})
    return job


@router.get("/jobs", response_model=list[VideoJob])
async def list_jobs(request: Request) -> list[VideoJob]:
    return await request.app.state.job_store.list_all()


@router.get("/jobs/{job_id}", response_model=VideoJob)
async def get_job(job_id: str, request: Request) -> VideoJob:
    try:
        return await request.app.state.job_store.load(job_id)
    except ObjectNotFound:
        raise HTTPException(404, f"no job {job_id!r}") from None


@router.post("/jobs/{job_id}/resume", response_model=VideoJob)
async def resume_job(job_id: str, request: Request) -> VideoJob:
    try:
        job = await request.app.state.job_store.load(job_id)
    except ObjectNotFound:
        raise HTTPException(404, f"no job {job_id!r}") from None
    if job.status != JobStatus.FAILED:
        raise HTTPException(409, f"job {job_id!r} is {job.status.value}, not failed")
    # Flipped to queued before returning, same as submit_job -- otherwise this response (and any
    # GET poll landing inside the runner's up-to-1s dequeue interval) would still show "failed"
    # for a resume that has, in fact, already been accepted.
    job = job.model_copy(update={"status": JobStatus.QUEUED})
    await request.app.state.job_store.save(job)
    # The runner tells a first attempt from a resume by asking the checkpointer whether this
    # job_id has a checkpoint at all (api/runner.py), so re-enqueueing the same id is the whole
    # mechanism -- no separate "resume" code path through the graph.
    await request.app.state.adapters.queue.enqueue(job.job_id, {})
    return job


@router.get("/jobs/{job_id}/events")
async def stream_job_events(job_id: str, request: Request) -> EventSourceResponse:
    try:
        job = await request.app.state.job_store.load(job_id)
    except ObjectNotFound:
        raise HTTPException(404, f"no job {job_id!r}") from None

    bus = request.app.state.event_bus
    # A subscriber that connects after the run already finished -- a page refresh, a reconnect
    # after a network blip -- would otherwise get a fresh, empty queue that nothing will ever
    # publish to (the runner has already returned) and hang open forever. Terminal jobs skip
    # subscribing entirely and just report the status once.
    already_terminal = job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED)
    queue = None if already_terminal else bus.subscribe(job_id)

    async def stage_events():
        if already_terminal or queue is None:
            yield {"event": "stage", "data": json.dumps({"job_status": job.status.value})}
            return
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield {"event": "stage", "data": json.dumps(item)}
        finally:
            bus.unsubscribe(job_id, queue)

    return EventSourceResponse(stage_events())
