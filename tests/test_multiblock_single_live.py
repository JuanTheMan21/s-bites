"""Real-toolchain verification for T18I Part A: the render-side backstop for a multi-block
SINGLE stack (``hfFitStageToBand``, ``_annotations.html``) closes D124's own fifth,
deliberately-deferred finding -- a full GRAPH_DIAGRAM stacked above a TEXT_PANEL in one
SINGLE-layout scene, confirmed live in T18H to produce 42 ``canvas_overflow`` findings.

Composed directly rather than through ``core/graph/nodes/visual_plan.py``: ``normalize_layout``
(T18I, Part A) already prevents a FRESH plan from producing this shape, but a scene from an OLDER
checkpoint (written before that fix) can still arrive at render time in exactly this shape, which
is what the render-side backstop exists for. Testing it means deliberately bypassing the planner
and building that shape directly.

The diagram fixture below is ``test_graph_diagram_layout_live.py``'s own ``_DIAMOND`` -- already
proven clean standalone. Confirmed by direct experiment (temporarily disabling
``hfFitStageToBand``'s call in ``_layout_single.html``, not committed) that stacking it with a
``TEXT_PANEL`` genuinely reproduces ~45 ``canvas_overflow`` findings without the fix and zero with
it -- a real regression pin, not a fixture that happened to already fit. A denser, branching,
fully-captioned topology was tried first and rejected: it reproduces a genuinely different,
pre-existing GRAPH_DIAGRAM label-vs-marker collision (independent of stacking -- confirmed live
against that same topology alone, with no second block at all) that is not this task's scope.
"""

import json
import shutil
import subprocess

import pytest

from core.block_types import BlockType
from core.models import Tier
from core.scene_schemas import ComposedBlock, ComposedScene
from rendering.render_segment import render_segment
from tests.block_examples import EXAMPLES
from tests.segment_examples import a_segment

pytestmark = pytest.mark.local_live

_NPX = shutil.which("npx")
FPS = 24

# Same topology as test_graph_diagram_layout_live.py::_DIAMOND -- proven clean standalone, so any
# finding this fixture produces when stacked is attributable to the stacking itself, not to a
# pre-existing node-layout defect.
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


async def test_a_multi_block_single_stack_no_longer_overflows(backend, tmp_path) -> None:
    """D124's own fifth, deliberately-deferred finding, closed: a full (non-compact, 620px
    canvas) GRAPH_DIAGRAM stacked above a TEXT_PANEL in one SINGLE scene used to produce ~45
    canvas_overflow findings (confirmed live -- see this module's own docstring).
    hfFitStageToBand now shrinks #stage as a whole to fit the usable band when this shape
    reaches render time, regardless of source."""
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.GRAPH_DIAGRAM,
                role="role",
                anchor_phrase=None,
                payload=_DIAMOND,
            ),
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL,
                role="role",
                anchor_phrase=None,
                payload=EXAMPLES[BlockType.TEXT_PANEL],
            ),
        ],
        continues_previous=False,
    )
    segment = a_segment(0, duration_ms=24_000).model_copy(
        update={"tier": Tier.ANIMATED, "scene": scene.model_dump()}
    )
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
    findings_text = json.dumps(check["layout"]["findings"])
    assert "canvas_overflow" not in findings_text
