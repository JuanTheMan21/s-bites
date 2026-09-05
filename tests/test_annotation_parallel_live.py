"""Real-toolchain verification for T18I: an edge-targeted annotation (the parallel-to-a-line
placement the user asked for directly) renders clean.

The wiring itself -- the target resolves to the real edge id, "parallel" leads the candidate
order -- is already pinned offline (``tests/test_annotation_line_targets.py``). This is the
real-toolchain proof that the result is a clean composition, not just correctly-shaped HTML.
The multi-block SINGLE capacity fix (D124's fifth, deferred finding) is its own file,
``tests/test_multiblock_single_live.py`` -- a distinct responsibility, split out to stay under
the 200-line ceiling.
"""

import json
import shutil
import subprocess

import pytest

from core.block_types import AnnotationTargetKind, BlockType
from core.models import Tier
from core.scene_schemas import ComposedAnnotation, ComposedBlock, ComposedScene
from rendering.render_segment import render_segment
from tests.segment_examples import a_segment

pytestmark = pytest.mark.local_live

_NPX = shutil.which("npx")
FPS = 24

_GRAPH_WITH_EDGE: dict = {
    "headline": "The attack path",
    "layout": "graph",
    "nodes": [
        {"id": "n1", "label": "Form input", "caption": None, "anchor_phrase": "an apostrophe"},
        {
            "id": "n2",
            "label": "String concatenation",
            "caption": None,
            "anchor_phrase": "concatenated straight into the query",
        },
    ],
    "edges": [{"from_id": "n1", "to_id": "n2", "label": None}],
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


async def test_an_edge_targeted_check_annotation_renders_clean(backend, tmp_path) -> None:
    """The user's own explicit requirement: an annotation on a line-shaped target must be able
    to render parallel to it, not above/below/on top of it."""
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.GRAPH_DIAGRAM,
                role="role",
                anchor_phrase=None,
                payload=_GRAPH_WITH_EDGE,
            )
        ],
        continues_previous=False,
        annotations=[
            ComposedAnnotation(
                annotation_type="check",
                target_block_index=0,
                target_kind=AnnotationTargetKind.LINK,
                target_item_index=0,
                anchor_phrase="concatenated straight into the query",
                caption="unsanitized",
            )
        ],
    )
    segment = a_segment(0, duration_ms=8_000).model_copy(
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
    assert check["contrast"]["errorCount"] == 0, check["contrast"]["findings"]
