"""Coverage for the branches ``tests/block_examples.py::EXAMPLES`` doesn't reach: ``ArrayStep``'s
``shift``/``push``/``pop`` ops (``EXAMPLES[BlockType.ARRAY_GRID]`` only exercises ``narrow``, the
one T18B already had) and ``GRAPH_DIAGRAM``'s ``GRAPH`` layout mode (``EXAMPLES`` only exercises
``chain``, the retired ``DIAGRAM_CHAIN``'s direct replacement).

Found missing by ``project-reviewer`` during T18C's own build: every parametrized sweep over
``BlockType`` draws from ``EXAMPLES``, so three of ``ArrayStep``'s four ops and one of
``GraphLayoutMode``'s two modes were exercised only by this task's own ad-hoc real-toolchain
probes, never by anything that runs in CI. Not part of ``EXAMPLES`` itself, the same reason
``STAT_CALLOUT_WITH_COUNT_UP`` isn't -- these are additive scenario coverage for block types that
already have one canonical fixture, not a second "the" payload.
"""

from pathlib import Path

from core.block_schemas_array import ArrayGridSlots
from core.block_schemas_graph import GraphDiagramSlots
from core.block_types import BlockType
from core.scene_schemas import ComposedBlock, ComposedScene
from rendering.compose import compose_scene
from tests.segment_examples import a_segment

DURATION_MS = 21_000

# Forward-only, matching the schema's own field description ("SHIFT: ... a sliding window
# ADVANCING") -- a window moving backward is not a supported input, the same way ArrayEliminationStep's
# pre-T18C "the range only ever shrinks" constraint was never validator-enforced either, only
# documented.
#
# A leading `narrow` establishes a genuine SUB-window (0-6 -> 0-4) before the `shift` step --
# found necessary by project-reviewer during this task's own checkpoint: the template's active
# range starts as the WHOLE array (prevStart=0, prevEnd=cellCount), so a `shift` step whose own
# remaining_end sits BELOW that starting prevEnd never runs the "enter" loop at all (prevEnd >=
# step.end means zero iterations) -- it silently degenerates into a plain narrow. With a real
# sub-window in place first, the shift step (0-4 -> 1-5, same width) makes prevEnd(4) < step.end(5)
# true, so the enter() branch -- SHIFT's whole reason for existing, distinct from NARROW -- is the
# one actually exercised, not just the leave() branch every op already shares.
ARRAY_GRID_ALL_OPS: dict = {
    "headline": "Every step op in one array",
    "orientation": "horizontal",
    "cells": ["1", "2", "3", "4", "5", "6"],
    "steps": [
        {
            "op": "narrow",
            "anchor_phrase": "first narrows to four cells",
            "remaining_start": 0,
            "remaining_end": 4,
            "end_operation": "none",
        },
        {
            "op": "shift",
            "anchor_phrase": "the window slides forward",
            "remaining_start": 1,
            "remaining_end": 5,
            "end_operation": "plus",
        },
        {
            "op": "push",
            "anchor_phrase": "one more joins the end",
            "remaining_start": 1,
            "remaining_end": 6,
            "end_operation": "plus",
        },
        {
            "op": "pop",
            "anchor_phrase": "the last one leaves",
            "remaining_start": 1,
            "remaining_end": 5,
            "end_operation": "minus",
        },
    ],
}

GRAPH_DIAGRAM_GRAPH_MODE: dict = {
    "headline": "A small service graph",
    "layout": "graph",
    "nodes": [
        {"id": "a", "label": "Gateway", "caption": None},
        {"id": "b", "label": "Auth", "caption": None},
        {"id": "c", "label": "Orders", "caption": None},
    ],
    "edges": [
        {"from_id": "a", "to_id": "b"},
        {"from_id": "a", "to_id": "c"},
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


def test_array_grid_all_ops_validate_against_the_schema() -> None:
    payload = ArrayGridSlots.model_validate(ARRAY_GRID_ALL_OPS)
    ops = [step.op.value for step in payload.steps]
    assert ops == ["narrow", "shift", "push", "pop"]


def test_the_shift_step_genuinely_translates_not_just_narrows() -> None:
    """The fixture bug project-reviewer caught: a `shift` step whose remaining_end sits below the
    active range's starting prevEnd (the whole array, before any narrow) never runs the
    'enter' loop -- it silently degenerates into a plain narrow. Pin the shape that actually
    exercises SHIFT's enter branch, not just its leave branch."""
    payload = ArrayGridSlots.model_validate(ARRAY_GRID_ALL_OPS)
    narrow, shift = payload.steps[0], payload.steps[1]
    assert narrow.op.value == "narrow"
    assert shift.op.value == "shift"
    width = narrow.remaining_end - narrow.remaining_start
    assert shift.remaining_end - shift.remaining_start == width, "shift must preserve width"
    assert shift.remaining_end > narrow.remaining_end, (
        "shift must extend past the prior step's own remaining_end, or the template's enter() "
        "loop (prevEnd..step.end) never runs a single iteration"
    )


def test_array_grid_all_ops_render_without_error_and_each_op_reaches_the_template(
    tmp_path: Path,
) -> None:
    segment = _a_composed_segment(BlockType.ARRAY_GRID, ARRAY_GRID_ALL_OPS)

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    for op in ("shift", "push", "pop"):
        assert f'"{op}"' in html, f"op {op!r} never reaches the composed script"
    assert 'endOp: "plus"' in html
    assert 'endOp: "minus"' in html


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
    assert 'from: "a", to: "b"' in html
