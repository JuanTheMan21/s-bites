"""T18A: measure real Tier-2 render throughput, and correct D16's frame budget.

    PYTHONPATH=. .venv/Scripts/python.exe scripts/measure_render_throughput.py

D16's ``FRAME_BUDGET`` derives from a 90-frame (3-second) sample dominated by browser cold start
and CLI resolution overhead -- 1.7-2.7 frames/sec. This repo's own successful renders contradict
that: ``adapters/local/render_backend.py`` applied a flat 60s timeout to full Tier-2 renders, and
~600-frame (25s) segments completed inside it. This script composes one realistic segment and
hands it to ``hyperframes benchmark`` -- the CLI's own tool for exactly this measurement -- rather
than re-implementing timing by hand.

Same precedent as ``scripts/tier_dry_run.py``/``scripts/verify_azure.py`` (D51) for living outside
``core/`` while naming concrete pieces of the render toolchain.
"""

import json
import subprocess
import sys
from pathlib import Path

from core.models import Importance, Segment, Tier, VisualIntent
from rendering.compose import compose_scene
from tests.slot_examples import EXAMPLES

DURATION_MS = 25_000
DEST_DIR = Path("artifacts") / "_throughput_probe"


def _repo_hyperframes() -> list[str]:
    name = "hyperframes.cmd" if sys.platform == "win32" else "hyperframes"
    local = Path("node_modules") / ".bin" / name
    if local.exists():
        return [str(local)]
    return ["npx", "hyperframes"]


def main() -> None:
    segment = Segment(
        index=0,
        title="Throughput probe",
        summary="A realistic bullet-list segment for measuring render throughput.",
        visual_intent=VisualIntent.BULLET_LIST,
        importance=Importance.NORMAL,
        narration="Narration for a throughput probe.",
        duration_ms=DURATION_MS,
        tier=Tier.ANIMATED,
        slots=EXAMPLES[VisualIntent.BULLET_LIST],
    )
    composition_dir = DEST_DIR / "composition"
    compose_scene(segment, composition_dir)

    command = [*_repo_hyperframes(), "benchmark", str(composition_dir), "--runs", "3", "--json"]
    print(f"$ {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Could not parse benchmark JSON -- see raw output above.", file=sys.stderr)
        return

    print("\n--- summary ---")
    rows = payload if isinstance(payload, list) else payload.get("results", [])
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
