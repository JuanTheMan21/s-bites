"""T18I: an annotation can target a LINE-shaped element (``AnnotationTargetKind.LINK``) --
a GRAPH_DIAGRAM edge or a SEQUENCE_DIAGRAM message arrow -- not just a point-shaped item.
Offline, no browser, through ``compose_scene`` the same way ``tests/test_compose_annotations.py``
already exercises ITEM targeting.
"""

from pathlib import Path

from core.block_types import AnnotationTargetKind, BlockType
from core.scene_schemas import ComposedAnnotation, ComposedBlock, ComposedScene
from interfaces.tts_provider import WordMark
from rendering.compose import compose_scene
from tests.block_examples import EXAMPLES
from tests.segment_examples import a_segment

DURATION_MS = 21_000

# Matches EXAMPLES[BlockType.GRAPH_DIAGRAM]'s own node[1] anchor_phrase -- reused verbatim, same
# pair test_compose_annotations.py already proved resolves.
_GRAPH_ANCHOR = "concatenated straight into the query"
_GRAPH_WORD_MARKS = [
    WordMark(text=word, offset_ms=i * 300, duration_ms=250)
    for i, word in enumerate(
        ["it", "gets", "concatenated", "straight", "into", "the", "query", "unsanitized"]
    )
]

_SEQ_ANCHOR = "sends the query and the value separately"
_SEQ_WORD_MARKS = [
    WordMark(text=word, offset_ms=i * 300, duration_ms=250)
    for i, word in enumerate(
        ["the", "app", "sends", "the", "query", "and", "the", "value", "separately"]
    )
]

# A GRAPH-mode (not CHAIN) graph_diagram -- CHAIN's own rail segments render with a DIFFERENT id
# suffix (`-seg-`) than GRAPH's canvas edges (`-edge-`), so this exercises the other branch.
_GRAPH_MODE_PAYLOAD = {
    "headline": "A small network",
    "layout": "graph",
    "nodes": [
        {"id": "n1", "label": "A", "caption": None, "anchor_phrase": "it gets"},
        {"id": "n2", "label": "B", "caption": None, "anchor_phrase": "concatenated"},
    ],
    "edges": [{"from_id": "n1", "to_id": "n2", "label": None}],
    "positions": [],
    "traversal": [],
}


def _scene_with(block_type: BlockType, payload, annotation: ComposedAnnotation) -> Path:
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(block_type=block_type, role="role", anchor_phrase=None, payload=payload)
        ],
        continues_previous=False,
        annotations=[annotation],
    )
    return scene


def _compose(block_type, payload, annotation, word_marks, tmp_path: Path) -> str:
    scene = _scene_with(block_type, payload, annotation)
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"scene": scene.model_dump(), "word_marks": word_marks}
    )
    dest = compose_scene(segment, tmp_path)
    return dest.read_text(encoding="utf-8")


def test_a_link_annotation_on_a_chain_mode_graph_targets_the_rail_segment_not_a_node(
    tmp_path: Path,
) -> None:
    """CHAIN's own edges ARE real (n-1 consecutive pairs, core/block_schemas_graph.py) but its
    rail segments render as `-seg-{i}`, not `-edge-{i}` -- GRAPH's own canvas id suffix."""
    annotation = ComposedAnnotation(
        annotation_type="check",
        target_block_index=0,
        target_kind=AnnotationTargetKind.LINK,
        target_item_index=0,
        anchor_phrase=_GRAPH_ANCHOR,
        caption="here",
    )
    html = _compose(
        BlockType.GRAPH_DIAGRAM,
        EXAMPLES[BlockType.GRAPH_DIAGRAM],
        annotation,
        _GRAPH_WORD_MARKS,
        tmp_path,
    )
    assert '"b0-seg-0"' in html
    assert '"b0-edge-0"' not in html
    # is_line=True routes CHECK's own sides list to lead with "parallel".
    assert '["parallel", "above", "below", "center"]' in html


def test_a_link_annotation_on_a_graph_mode_diagram_targets_the_canvas_edge(tmp_path: Path) -> None:
    annotation = ComposedAnnotation(
        annotation_type="check",
        target_block_index=0,
        target_kind=AnnotationTargetKind.LINK,
        target_item_index=0,
        anchor_phrase="it gets",
        caption="here",
    )
    html = _compose(
        BlockType.GRAPH_DIAGRAM,
        _GRAPH_MODE_PAYLOAD,
        annotation,
        [
            WordMark(text=w, offset_ms=i * 300, duration_ms=250)
            for i, w in enumerate(["it", "gets"])
        ],
        tmp_path,
    )
    assert '"b0-edge-0"' in html
    assert '"b0-seg-0"' not in html


def test_a_link_annotation_out_of_range_is_dropped_not_guessed(tmp_path: Path) -> None:
    """EXAMPLES[GRAPH_DIAGRAM] has exactly 2 edges (indices 0-1) -- index 5 names nothing real."""
    annotation = ComposedAnnotation(
        annotation_type="warning",
        target_block_index=0,
        target_kind=AnnotationTargetKind.LINK,
        target_item_index=5,
        anchor_phrase=_GRAPH_ANCHOR,
        caption="unreachable",
    )
    html = _compose(
        BlockType.GRAPH_DIAGRAM,
        EXAMPLES[BlockType.GRAPH_DIAGRAM],
        annotation,
        _GRAPH_WORD_MARKS,
        tmp_path,
    )
    assert "unreachable" not in html
    assert "anno-warn-wrap" not in html


def test_an_item_annotation_on_a_graph_node_is_not_line_shaped(tmp_path: Path) -> None:
    """The ordinary case, unchanged: an ITEM (the default target_kind) on a node targets the
    node, not a line, and does not lead with "parallel"."""
    annotation = ComposedAnnotation(
        annotation_type="check",
        target_block_index=0,
        target_item_index=1,
        anchor_phrase=_GRAPH_ANCHOR,
        caption="here",
    )
    html = _compose(
        BlockType.GRAPH_DIAGRAM,
        EXAMPLES[BlockType.GRAPH_DIAGRAM],
        annotation,
        _GRAPH_WORD_MARKS,
        tmp_path,
    )
    assert '"b0-node-1"' in html
    # The shared hfAnnotationPlace function always DEFINES a "parallel" candidate (it is generic
    # over every target) -- what this checks is that THIS annotation's own call site was not
    # handed it, i.e. is_line routed it to the point-shaped sides list, not the line-shaped one.
    assert '["above", "below"]' in html
    assert '["parallel", "above", "below", "center"]' not in html


def test_a_sequence_diagram_message_is_line_shaped_even_addressed_as_an_item(
    tmp_path: Path,
) -> None:
    """A SEQUENCE_DIAGRAM message arrow IS a line whichever way it's addressed -- ITEM (the
    default, and the only addressable field it has) resolves to the same `-msg-` id a LINK target
    would, and is_line is true either way (rendering/annotations.py::resolve_annotations)."""
    annotation = ComposedAnnotation(
        annotation_type="check",
        target_block_index=0,
        target_item_index=0,
        anchor_phrase=_SEQ_ANCHOR,
        caption="here",
    )
    html = _compose(
        BlockType.SEQUENCE_DIAGRAM,
        EXAMPLES[BlockType.SEQUENCE_DIAGRAM],
        annotation,
        _SEQ_WORD_MARKS,
        tmp_path,
    )
    assert '"b0-msg-0"' in html
    assert '["parallel", "above", "below", "center"]' in html
