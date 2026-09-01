"""``GRAPH_DIAGRAM``'s ``GRAPH`` layout mode -- split out of ``test_array_grid_and_graph_modes.py``
once T18E's edge-anchoring/gating/label/compact-layout additions pushed that file over the
200-line ceiling.

``EXAMPLES`` only exercises ``chain`` (the retired ``DIAGRAM_CHAIN``'s direct replacement), so the
``GRAPH`` mode fixture below is this project's only real-toolchain coverage of it -- found missing
by ``project-reviewer`` during T18C's own build.
"""

from pathlib import Path

from core.block_schemas_graph import GraphDiagramSlots
from core.block_types import BlockType
from core.scene_schemas import ComposedBlock, ComposedScene
from rendering.compose import compose_scene
from tests.block_examples import EXAMPLES
from tests.segment_examples import a_segment

DURATION_MS = 21_000

GRAPH_DIAGRAM_GRAPH_MODE: dict = {
    "headline": "A small service graph",
    "layout": "graph",
    "nodes": [
        {
            "id": "a",
            "label": "Gateway",
            "caption": None,
            "anchor_phrase": "starts at the gateway",
        },
        {"id": "b", "label": "Auth", "caption": None, "anchor_phrase": "checks auth first"},
        {
            "id": "c",
            "label": "Orders",
            "caption": None,
            "anchor_phrase": "reaches the order service",
        },
    ],
    "edges": [
        # The UNLABELLED edge comes first, deliberately -- a labelled-only counter (rather than
        # the edge's own overall index) would look up the wrong element for "b" -> "c" here,
        # a real bug this ordering is chosen specifically to catch (T18E).
        {"from_id": "a", "to_id": "b", "label": None},
        {"from_id": "a", "to_id": "c", "label": "auth token"},
    ],
    "positions": [],
    "traversal": [
        {"anchor_phrase": "starts at the gateway", "node_id": "a"},
        {"anchor_phrase": "checks auth first", "node_id": "b"},
    ],
}


def _a_composed_segment(block_type: BlockType, payload: dict):
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(block_type=block_type, role="role", anchor_phrase=None, payload=payload)
        ],
        continues_previous=False,
    )
    return a_segment(0, duration_ms=DURATION_MS).model_copy(update={"scene": scene.model_dump()})


def _a_split_composed_segment(block_type: BlockType, payload: dict):
    """A SPLIT_HORIZONTAL scene -- exactly two blocks, ``compact=true`` for both (T18E's E2.4
    compact-canvas layout only applies under this layout)."""
    scene = ComposedScene(
        motif="terminal",
        layout="split_horizontal",
        blocks=[
            ComposedBlock(block_type=block_type, role="role", anchor_phrase=None, payload=payload),
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL,
                role="role",
                anchor_phrase=None,
                payload=EXAMPLES[BlockType.TEXT_PANEL],
            ),
        ],
        continues_previous=False,
    )
    return a_segment(0, duration_ms=DURATION_MS).model_copy(update={"scene": scene.model_dump()})


def test_graph_diagram_graph_mode_validates_against_the_schema() -> None:
    payload = GraphDiagramSlots.model_validate(GRAPH_DIAGRAM_GRAPH_MODE)
    assert payload.layout.value == "graph"
    assert len(payload.traversal) == 2


def test_graph_diagram_graph_mode_renders_the_free_canvas_not_the_rail(tmp_path: Path) -> None:
    segment = _a_composed_segment(BlockType.GRAPH_DIAGRAM, GRAPH_DIAGRAM_GRAPH_MODE)

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    assert 'id="b0-canvas"' in html
    assert 'id="b0-rail"' not in html
    assert 'id="b0-traveler"' in html
    assert 'from: "a"' in html
    assert 'to: "b"' in html


def test_graph_diagram_edges_gate_on_both_endpoints_and_carry_arrowheads(tmp_path: Path) -> None:
    """T18E, E2: an edge used to draw at node 0's own start regardless of which nodes it
    connected -- now every edge's reveal is gated on `max(fromStart, toStart)`. Also pins that an
    arrowhead marker is wired to every graph edge line."""
    segment = _a_composed_segment(BlockType.GRAPH_DIAGRAM, GRAPH_DIAGRAM_GRAPH_MODE)

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    assert "Math.max(fromStart, toStart)" in html
    assert 'marker-end="url(#b0-arrow)"' in html


def test_graph_diagram_edge_labels_render_only_when_authored(tmp_path: Path) -> None:
    """T18E, E3: GraphEdge.label is a short weight/cost/condition, rendered as its own div at
    the edge's midpoint -- present for the labelled edge, absent for the plain one."""
    segment = _a_composed_segment(BlockType.GRAPH_DIAGRAM, GRAPH_DIAGRAM_GRAPH_MODE)

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    assert "auth token" in html
    # The labelled edge is index 1 (the unlabelled one is index 0, deliberately first in the
    # fixture) -- the div's id must carry the edge's own OVERALL index, matching what the
    # script's "-edge-label-" + i lookup (i = the edges array's own map index) will look for,
    # not a separate labelled-only counter that would drift as soon as an earlier edge lacked
    # a label (the real bug this ordering caught during this session's own review).
    assert 'id="b0-edge-label-1"' in html
    assert 'id="b0-edge-label-0"' not in html
    # Only one of the two edges is labelled -- exactly one edge-label div, not two.
    assert html.count('class="blk-graph-edge-label"') == 1


def test_graph_diagram_fallback_layout_is_aspect_ratio_aware(tmp_path: Path) -> None:
    """T18G (the full build of D121's analysis item 7 -- T18E's E2.4 only shipped a bounded
    circle/row-packed fallback): unauthored nodes now go through a real rank-based layered
    layout, called with `rankAxisIsX` true for a SPLIT_HORIZONTAL compact canvas and false for
    SINGLE -- the aspect-ratio-awareness principle E2.4 established, carried into the real
    algorithm rather than lost when the circle/row formulas were replaced."""
    single_segment = _a_composed_segment(BlockType.GRAPH_DIAGRAM, GRAPH_DIAGRAM_GRAPH_MODE)
    split_segment = _a_split_composed_segment(BlockType.GRAPH_DIAGRAM, GRAPH_DIAGRAM_GRAPH_MODE)

    single_html = compose_scene(single_segment, tmp_path / "single").read_text(encoding="utf-8")
    split_html = compose_scene(split_segment, tmp_path / "split").read_text(encoding="utf-8")

    assert "function computeLayeredLayout(" in single_html
    assert "function computeLayeredLayout(" in split_html
    assert "computeLayeredLayout(nodeIds, layoutEdges, false)" in single_html
    assert "computeLayeredLayout(nodeIds, layoutEdges, true)" in split_html
