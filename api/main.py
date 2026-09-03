"""ASGI entrypoint: ``uvicorn api.main:app``.

Builds real adapters from the environment and hands them to ``api.app.create_app`` -- the only
place ``api/`` reads ``FRAME_BUDGET``/``FPS``/``RUNTIME_ENV`` from the process, mirroring
``cli.py``'s own "read configuration at the edge" pattern rather than duplicating it as a shared
helper (there are exactly two edges in this repo, and a third does not exist yet).
"""

import os

from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from api.app import create_app
from config import build_adapters

load_dotenv()


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
