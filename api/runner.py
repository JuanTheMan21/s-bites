"""The worker loop that turns a queued job into a finished video (T19): claim, drive the graph,
close out the queue receipt.

This is the runner D67 has been waiting on. ``GraphContext`` deliberately excludes ``JobQueue``
(D66) -- nothing inside a graph run can see ``QueuedJob.attempt`` -- so a cross-requeue attempt
ceiling has only ever been buildable from *outside* the graph, wrapping a whole invocation. This
module is that wrapper, and ``MAX_ATTEMPTS`` below is where the ceiling finally lands.

Serial by design: one background task, one job at a time, on the same event loop the API serves
requests on. T34 promotes this to a real separate worker process; until then, serial execution is
what keeps ``JobStore``'s per-job writes race-free without a lock for every write, only the
concurrent one (``api/jobs.py``'s submit path).
"""

import asyncio
import contextlib
import logging
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from api.events import JobEventBus, summarize_node_event
from api.job_store import JobStore
from config import Adapters
from core.graph import GraphContext, build_graph
from core.graph.state import GraphState
from core.video_job import JobStatus, VideoJob
from interfaces import QueuedJob

logger = logging.getLogger(__name__)

# A job that still fails after this many attempts is dead-lettered rather than requeued forever --
# an exhausted StructuredOutputError budget or a genuinely broken topic should not loop the queue.
MAX_ATTEMPTS = 3

WORKING_ROOT = Path("artifacts") / "_api_run"


def _assemble_preview(values: GraphState) -> VideoJob:
    """The same ``state["segments"]``-dict-to-list assembly ``core/graph/nodes/finalize.py
    ::finalize`` does at the very end, applied mid-run: ``state["job"].segments`` is only ever
    populated by ``finalize`` itself, so a snapshot taken before then always carries an empty
    list there even though ``state["segments"]`` (the fan-out accumulator
    ``core/graph/state.py::merge_segments`` merges concurrent writes into) already has real data.
    ``plan_segments`` seeds every index up front, unfilled, so this is already the full-length
    list by the very first "end" event -- later per-segment nodes fill individual entries in as
    they converge on each index, rather than new cards appearing one at a time.
    """
    job = values["job"]
    segments = values.get("segments") or {}
    if not segments:
        return job
    ordered = [segments[i] for i in sorted(segments)]
    return job.model_copy(update={"segments": ordered})


class JobRunner:
    """Owns the single background task that dequeues and runs jobs."""

    def __init__(
        self,
        adapters: Adapters,
        store: JobStore,
        bus: JobEventBus,
        *,
        frame_budget: int,
        fps: int,
    ) -> None:
        self._adapters = adapters
        self._store = store
        self._bus = bus
        self._frame_budget = frame_budget
        self._fps = fps
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task

    async def _loop(self) -> None:
        while True:
            queued = await self._adapters.queue.dequeue(timeout_s=1.0)
            if queued is None:
                continue
            try:
                await self._run_one(queued)
            except Exception:
                # A failure inside a single job's own try/except (api/jobs.py's submit and
                # resume both guarantee a store record exists before enqueueing) already ends
                # up here as a completed except-branch, not an exception -- so reaching this is
                # something *outside* that contract breaking. Logged and swallowed anyway: one
                # bad job taking down every future job on this loop, silently, is worse than one
                # bad job's own failure going unrecorded in JobStore.
                logger.exception("unhandled failure processing job %s", queued.job_id)

    async def _run_one(self, queued: QueuedJob) -> None:
        job = await self._store.load(queued.job_id)
        job = job.model_copy(update={"status": JobStatus.RUNNING})
        await self._store.save(job)

        working_dir = WORKING_ROOT / job.job_id
        db_path = working_dir / "checkpoints.sqlite"
        working_dir.mkdir(parents=True, exist_ok=True)

        context = GraphContext(
            llm=self._adapters.llm,
            tts=self._adapters.tts,
            storage=self._adapters.storage,
            skills=self._adapters.skills,
            render=self._adapters.render,
            working_dir=working_dir,
            frame_budget=self._frame_budget,
            fps=self._fps,
        )
        try:
            async with AsyncSqliteSaver.from_conn_string(str(db_path)) as saver:
                graph = build_graph(saver)
                gconfig = {"configurable": {"thread_id": job.job_id}}
                # `AsyncSqliteSaver.from_conn_string` creates `db_path` the instant it connects,
                # before any checkpoint is ever written -- checking the file's existence (an
                # earlier version of this method did) says nothing about whether this thread_id
                # has actually run before. Asking the saver directly is the only correct check:
                # `None` here means a genuinely first attempt, gets the full initial state;
                # anything else -- an automatic requeue after a transient failure, or T22's
                # explicit resume endpoint -- means `None` input (continue from the last
                # checkpoint), the same call tests/test_graph_resume.py proves resumes correctly.
                existing_checkpoint = await saver.aget_tuple(gconfig)
                input_state = {"job": job, "segments": {}} if existing_checkpoint is None else None
                async for event in graph.astream_events(
                    input_state, gconfig, context=context, version="v2", durability="sync"
                ):
                    stage = summarize_node_event(event)
                    if stage is not None:
                        await self._bus.publish(job.job_id, stage)
                        # `job_store.save` otherwise only ever runs twice for a whole job -- once
                        # here at the very start, once after the loop ends -- so a REST poll (or
                        # the frontend's SSE-triggered refetch) saw an empty `segments[]` for the
                        # entire run and only ever jumped straight to the finished state.
                        if stage.get("stage") == "end":
                            in_progress = await graph.aget_state(gconfig)
                            await self._store.save(_assemble_preview(in_progress.values))
                snapshot = await graph.aget_state(gconfig)
            finished: VideoJob = snapshot.values["job"]
            await self._store.save(finished)
            await self._adapters.queue.complete(queued.receipt)
            await self._bus.publish(
                job.job_id, {"job_status": finished.status.value, "terminal": True}
            )
        except Exception as exc:
            logger.error("job %s failed on attempt %d: %s", job.job_id, queued.attempt, exc)
            requeue = queued.attempt < MAX_ATTEMPTS
            # A requeued attempt is persisted as QUEUED, not FAILED -- project-reviewer caught the
            # real consequence of getting this wrong: every consumer that reads persisted status
            # rather than a live SSE stream (api/jobs.py's already-terminal check, a fresh page
            # load, and -- most seriously -- resume_job's own `status != FAILED` guard) could not
            # tell a job mid-automatic-retry from one genuinely dead, and a user clicking Resume
            # during that window would enqueue a second, redundant run of the same job_id/thread
            # (neither LocalJobQueue nor FakeJobQueue dedupe by job_id). Mirroring the status
            # resume_job itself already sets for an explicit resume makes both paths consistent,
            # and means resume_job's existing guard now correctly 409s during a retry window too,
            # with no change needed there.
            saved_status = JobStatus.FAILED if not requeue else JobStatus.QUEUED
            saved_error = str(exc)[:500] if not requeue else None
            failed = job.model_copy(update={"status": saved_status, "error": saved_error})
            await self._store.save(failed)
            await self._adapters.queue.fail(queued.receipt, str(exc), requeue=requeue)
            # `terminal` is the one bit a client already *connected* to the SSE stream cannot
            # otherwise observe: this event and a genuinely final failure publish an identical
            # {"job_status": "failed"} except for whether the stream stays open for the retry that
            # follows. Published regardless of what was just persisted above -- a live subscriber
            # still sees the real-time hiccup even though REST/a fresh subscriber now correctly
            # sees QUEUED instead.
            await self._bus.publish(
                job.job_id, {"job_status": JobStatus.FAILED.value, "terminal": not requeue}
            )
            if requeue:
                # Not terminal -- the same job_id comes back around this loop shortly, resuming
                # from whatever checkpoint it reached. A subscriber watching this attempt should
                # see the failure, but the stream itself stays open for the retry that follows.
                return
            await self._bus.close(job.job_id)
        else:
            await self._bus.close(job.job_id)
