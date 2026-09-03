"""Wires one FastAPI app around an already-resolved adapter bundle (T19).

Adapters are a constructor argument, not built inside this module -- ``config.build_adapters()``
reads ``RUNTIME_ENV`` from the process environment, which is exactly the kind of edge-read
``api/main.py`` (the real entrypoint) owns and this factory should not, since T23's tests need to
pass ``tests/fakes/*`` in directly rather than exercising a second, environment-dependent
construction path only production ever runs.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.artifacts import router as artifacts_router
from api.events import JobEventBus
from api.job_store import JobStore
from api.jobs import router as jobs_router
from api.runner import JobRunner
from config import Adapters, close_adapters


def create_app(adapters: Adapters, *, frame_budget: int, fps: int) -> FastAPI:
    store = JobStore(adapters.storage)
    bus = JobEventBus()
    runner = JobRunner(adapters, store, bus, frame_budget=frame_budget, fps=fps)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runner.start()
        try:
            yield
        finally:
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
    return app
