"""Wires one FastAPI app around an already-resolved adapter bundle (T19).

Adapters are a constructor argument, not built inside this module -- ``config.build_adapters()``
reads ``RUNTIME_ENV`` from the process environment, which is exactly the kind of edge-read
``api/main.py`` (the real entrypoint) owns and this factory should not, since T23's tests need to
pass ``tests/fakes/*`` in directly rather than exercising a second, environment-dependent
construction path only production ever runs.

**``run_worker`` (T34):** defaults to ``True`` so every existing caller -- every test in
``tests/api_fixtures.py``, every ``tests/test_api_*.py`` -- keeps the in-process worker it always
had, unchanged. ``worker.py`` is the new entry point that runs the worker loop on its own, and
passes ``run_worker=False`` when it needs an app only to serve requests. ``adapters.events.start()``
runs in *both* modes: the event channel's receive side (a no-op locally, a background pump on
Service Bus) has to be live whether or not this process also runs the worker, since it is what a
connected SSE client reads from either way.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.artifacts import router as artifacts_router
from api.job_store import JobStore
from api.jobs import router as jobs_router
from api.runner import JobRunner
from api.scorm import router as scorm_router
from api.segments import router as segments_router
from config import Adapters, close_adapters


def create_app(
    adapters: Adapters, *, frame_budget: int, fps: int, run_worker: bool = True
) -> FastAPI:
    store = JobStore(adapters.storage)
    bus = adapters.events
    runner = JobRunner(adapters, store, bus, frame_budget=frame_budget, fps=fps)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await adapters.events.start()
        if run_worker:
            runner.start()
        try:
            yield
        finally:
            if run_worker:
                await runner.stop()
            await close_adapters(adapters)

    app = FastAPI(lifespan=lifespan)
    app.state.adapters = adapters
    app.state.job_store = store
    app.state.event_bus = bus
    app.state.runner = runner
    app.state.index_lock = asyncio.Lock()

    app.include_router(jobs_router)
    app.include_router(artifacts_router)
    app.include_router(segments_router)
    app.include_router(scorm_router)
    return app
