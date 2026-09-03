"""Writes ``web/openapi.json`` from the real FastAPI app -- offline, with no live server, no
Azure credentials, and no ``FRAME_BUDGET``/``FPS`` env vars.

``api.app.create_app`` takes an already-resolved ``Adapters`` bundle rather than building one
itself (T19's whole point), so ``tests/api_fixtures.py::fake_adapters()`` -- the same bundle the
API test suite runs against -- is a complete, working input here too. ``create_app`` only
*registers* the lifespan; ``app.openapi()`` never runs it, so no adapter is ever contacted.

``web/openapi.json`` is committed, so a backend contract change shows up as a diff here before it
ever reaches ``npm run api:types`` -- ``git diff --exit-code web/openapi.json`` after a fresh run
of this script is the standing drift alarm (T24's own definition of done).
"""

import json
from pathlib import Path

from api.app import create_app
from tests.api_fixtures import FPS, FRAME_BUDGET, fake_adapters

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "web" / "openapi.json"


def dump_openapi(output_path: Path = OUTPUT_PATH) -> Path:
    app = create_app(fake_adapters(), frame_budget=FRAME_BUDGET, fps=FPS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    return output_path


if __name__ == "__main__":
    written = dump_openapi()
    print(f"wrote {written}")
