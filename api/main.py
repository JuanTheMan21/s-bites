"""ASGI entrypoint: ``uvicorn api.main:app``.

Builds real adapters from the environment and hands them to ``api.app.create_app`` -- the only
place ``api/`` reads ``FRAME_BUDGET``/``FPS``/``RUNTIME_ENV`` from the process, mirroring
``cli.py``'s own "read configuration at the edge" pattern rather than duplicating it as a shared
helper (there are exactly two edges in this repo, and a third does not exist yet).

**Never run this with ``uvicorn``'s own ``--reload`` on Windows.** Found live, T18J: `--reload`
runs the actual server as a spawned worker (`use_subprocess=True` in uvicorn's own
`uvicorn/loops/asyncio.py::asyncio_loop_factory`), and on Windows that branch deliberately picks
`asyncio.SelectorEventLoop` over the default `ProactorEventLoop` -- but `SelectorEventLoop` cannot
create subprocesses on Windows at all. `adapters/local/hyperframes_process.py`'s
`asyncio.create_subprocess_exec` (every `lint`/`render`/`check` call, i.e. most of this
project's actual work) then raises a bare `NotImplementedError` with no message, non-
deterministically -- whichever segment's render happens to be in flight when the process pool
gets to it, so it looks like a different segment failing every attempt rather than one
consistent bug. This is not a config knob to work around; do not add ``--reload`` back without a
real fix for it (e.g. `uvicorn.run(..., loop="asyncio")` alone does not change this -- the
subprocess-worker branch is what matters). Restart the process by hand after an edit instead.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from api.app import create_app
from config import build_adapters

load_dotenv()

# T18K: found live -- core/graph/node_timing.py's own per-node start/elapsed INFO logs (T18E,
# D121/D122's "make retry/timing visible" fix) and this task's new per-step finalize timing never
# actually appeared in a real run, because nothing anywhere configured logging above the
# interpreter's own WARNING default. The instrumentation shipped, twice, and was silently
# useless both times -- this is the fix, not a new feature. A no-op if something else already
# configured root handlers (basicConfig's own documented behavior), so it is safe to call once
# here regardless of run order.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def _required_int(name: str) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {value!r}") from exc


app = create_app(
    build_adapters(),
    frame_budget=_required_int("FRAME_BUDGET"),
    fps=_required_int("FPS"),
)

# The Vite dev server (default :5173) and its production origin are otherwise blocked outright --
# create_app() itself must stay env-free (T23's tests and scripts/dump_openapi.py both build the
# app without a live server or credentials), so the CORS origin list belongs here, the one place
# api/ is documented to read the process environment.
_web_origins = [
    origin.strip()
    for origin in os.environ.get("WEB_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_web_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges"],
)
