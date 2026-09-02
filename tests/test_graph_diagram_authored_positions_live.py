"""Real-toolchain verification for T18H's authored-position safety net
(``_block_graph_diagram.html``'s GRAPH-mode ``script()``, right after ``computeLayeredLayout``).

Split out of ``test_graph_diagram_layout_live.py`` once it hit the 200-line ceiling -- a distinct
responsibility from that file's own scope (verifying the *fallback* algorithm): this file verifies
what happens when a scene's ``payload.positions`` are present but unsafe, not absent.

Confirmed live, not hypothetical: a real render (``t18h-showcase-binary-search`` segment 2, "how
binary search works") authored ``y=0.92`` for one node in a 3-rank, fully-captioned diagram --
well past the caption-band-safety ceiling the fallback algorithm would never produce on its own.
The fixture below reproduces that exact scene shape (a 3-way branch converging back to one node,
every node captioned, one authored position deliberately unsafe).
"""

import json
import shutil
import subprocess

import pytest

from core.block_types import BlockType
from core.models import Tier
from core.scene_schemas import ComposedBlock, ComposedScene
from rendering.render_segment import render_segment
from tests.segment_examples import a_segment

pytestmark = pytest.mark.local_live

_NPX = shutil.which("npx")
DURATION_MS = 29_000
FPS = 24

# The exact topology and authored positions from the real render that found this bug -- every node
# captioned (so each has real vertical footprint), a 3-way branch (start -> match/left/right) that
# reconverges (left/right -> shrink), and one authored position (shrink's own y=0.92) well past the
# 0.62 ceiling the fallback algorithm itself respects.
_UNSAFE_AUTHORED: dict = {
    "headline": "Binary search narrows the range",
    "layout": "graph",
    "nodes": [
        {
            "id": "start",
            "label": "Middle check",
            "caption": "one comparison",
            "anchor_phrase": "check the middle",
        },
        {
            "id": "match",
            "label": "Match",
            "caption": "ends search",
            "anchor_phrase": "values match",
        },
        {
            "id": "left",
            "label": "Left half",
            "caption": "smaller target",
            "anchor_phrase": "go left",
        },
        {
            "id": "right",
            "label": "Right half",
            "caption": "larger target",
            "anchor_phrase": "go right",
        },
        {
            "id": "shrink",
            "label": "Half removed",
            "caption": "search shrinks fast",
            "anchor_phrase": "half is gone",
        },
    ],
    "edges": [
        {"from_id": "start", "to_id": "match", "label": None},
        {"from_id": "start", "to_id": "left", "label": None},
        {"from_id": "start", "to_id": "right", "label": None},
        {"from_id": "left", "to_id": "shrink", "label": None},
        {"from_id": "right", "to_id": "shrink", "label": None},
    ],
    "positions": [
        {"node_id": "start", "x": 0.5, "y": 0.22},
        {"node_id": "match", "x": 0.5, "y": 0.48},
        {"node_id": "left", "x": 0.22, "y": 0.72},
        {"node_id": "right", "x": 0.78, "y": 0.72},
        # The unsafe one -- well past Y_MAX_FRAC (0.62), confirmed in the real render to land a
        # node's label in the caption band.
        {"node_id": "shrink", "x": 0.5, "y": 0.92},
    ],
    "traversal": [],
}


def _a_graph_segment(payload: dict):
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.GRAPH_DIAGRAM, role="role", anchor_phrase=None, payload=payload
            )
        ],
        continues_previous=False,
    )
    return a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"tier": Tier.ANIMATED, "scene": scene.model_dump()}
    )


def _run_check(composition_dir) -> dict:
    assert _NPX is not None, "npx is not on PATH"
    result = subprocess.run(
        [_NPX, "--no-install", "hyperframes", "check", "--json", str(composition_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return json.loads(result.stdout)


@pytest.fixture
async def backend():
    from adapters.local.render_backend import PlaywrightHyperFramesRenderBackend

    real = PlaywrightHyperFramesRenderBackend(quality="draft", max_attempts=1, timeout_s=90.0)
    try:
        yield real
    finally:
        await real.aclose()


async def test_one_unsafe_authored_position_falls_back_for_the_whole_diagram(
    backend, tmp_path
) -> None:
    """The regression pin for the confirmed real-render bug: a single unsafe authored (x, y)
    among an otherwise-safe, fully-authored set must not reach the page at all -- the whole set
    is discarded in favor of the (already-verified-clean) fallback layout, not clamped in place
    (clamping was tried first and confirmed live to trade a caption-band collision for a
    different node-vs-node one instead)."""
    segment = _a_graph_segment(_UNSAFE_AUTHORED)
    composition_dir = tmp_path / "comp"
    dest = tmp_path / "clip.mp4"

    result = await render_segment(
        segment, backend, composition_dir=composition_dir, dest=dest, fps=FPS
    )

    assert result == dest
    assert dest.exists() and dest.stat().st_size > 0

    check = _run_check(composition_dir)
    assert check.get("ok") is True, check
    assert check["layout"]["errorCount"] == 0, check["layout"]["findings"]
    assert check["contrast"]["errorCount"] == 0, check["contrast"]["findings"]
