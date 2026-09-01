"""Real-toolchain verification for T18G's F2: the layered/rank-based ``GRAPH_DIAGRAM`` layout
algorithm (``computeLayeredLayout``, ``rendering/templates/_block_graph_diagram.html``).

``tests/test_graph_diagram_edges.py`` only asserts the composed HTML *calls* the algorithm with
the right ``rankAxisIsX`` argument -- it cannot run the JS itself. This is the live counterpart:
real Playwright + the real HyperFrames CLI's ``check`` (layout/contrast/motion audits none of the
offline suite can perform), against topologies chosen specifically to exercise the algorithm's own
interesting cases -- a diamond (two paths converging, exercises barycenter ordering) and a cycle
(exercises the DFS cycle-breaking pass), each in both SINGLE and the SPLIT_HORIZONTAL compact
canvas (E2.4's aspect-ratio-awareness principle, now feeding the real algorithm).
"""

import json
import shutil
import subprocess

import pytest

from core.block_types import BlockType
from core.models import Segment, Tier
from core.scene_schemas import ComposedBlock, ComposedScene
from rendering.render_segment import render_segment
from tests.segment_examples import a_segment

pytestmark = pytest.mark.local_live

_NPX = shutil.which("npx")
DURATION_MS = 6_000
FPS = 24

_DIAMOND: dict = {
    "headline": "Two paths converge",
    "layout": "graph",
    "nodes": [
        {"id": "start", "label": "Start", "caption": None, "anchor_phrase": "we begin"},
        {"id": "left", "label": "Left path", "caption": None, "anchor_phrase": "one branch"},
        {
            "id": "right",
            "label": "Right path",
            "caption": None,
            "anchor_phrase": "the other branch",
        },
        {"id": "end", "label": "Merge", "caption": None, "anchor_phrase": "they merge back"},
    ],
    "edges": [
        {"from_id": "start", "to_id": "left", "label": None},
        {"from_id": "start", "to_id": "right", "label": None},
        {"from_id": "left", "to_id": "end", "label": None},
        {"from_id": "right", "to_id": "end", "label": None},
    ],
    "positions": [],
    "traversal": [],
}

_CYCLE: dict = {
    "headline": "A small state machine",
    "layout": "graph",
    "nodes": [
        {"id": "idle", "label": "Idle", "caption": None, "anchor_phrase": "starts idle"},
        {"id": "running", "label": "Running", "caption": None, "anchor_phrase": "begins running"},
        {"id": "error", "label": "Error", "caption": None, "anchor_phrase": "hits an error"},
    ],
    "edges": [
        {"from_id": "idle", "to_id": "running", "label": None},
        {"from_id": "running", "to_id": "error", "label": None},
        # Back to idle -- a real cycle, exercising the DFS back-edge pass.
        {"from_id": "error", "to_id": "idle", "label": None},
        {"from_id": "running", "to_id": "idle", "label": None},
    ],
    "positions": [],
    "traversal": [],
}


def _a_graph_segment(payload: dict, *, compact: bool) -> Segment:
    layout = "split_horizontal" if compact else "single"
    blocks = [
        ComposedBlock(
            block_type=BlockType.GRAPH_DIAGRAM, role="role", anchor_phrase=None, payload=payload
        )
    ]
    if compact:
        from tests.block_examples import EXAMPLES

        blocks.append(
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL,
                role="role",
                anchor_phrase=None,
                payload=EXAMPLES[BlockType.TEXT_PANEL],
            )
        )
    scene = ComposedScene(motif="terminal", layout=layout, blocks=blocks, continues_previous=False)
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


@pytest.mark.parametrize("payload", [_DIAMOND, _CYCLE], ids=["diamond", "cycle"])
@pytest.mark.parametrize("compact", [False, True], ids=["single", "split_horizontal"])
async def test_layered_layout_renders_cleanly(
    backend, tmp_path, payload: dict, compact: bool
) -> None:
    segment = _a_graph_segment(payload, compact=compact)
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
