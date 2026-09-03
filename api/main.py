"""ASGI entrypoint: ``uvicorn api.main:app``.

Builds real adapters from the environment and hands them to ``api.app.create_app`` -- the only
place ``api/`` reads ``FRAME_BUDGET``/``FPS``/``RUNTIME_ENV`` from the process, mirroring
``cli.py``'s own "read configuration at the edge" pattern rather than duplicating it as a shared
helper (there are exactly two edges in this repo, and a third does not exist yet).
"""

import os

from dotenv import load_dotenv

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
