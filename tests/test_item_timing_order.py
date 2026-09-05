"""T18J: two real-render timing defects. First, an item rendered in authored order even when its
resolved anchor placed it earlier in the narration than an item above it -- confirmed live, one
segment's third-authored item was spoken first. Second, an unmatched anchor fell back to a flat,
context-free instant (0.75s, disconnected from the block's own visible window), confirmed live as
content appearing before the narration ever mentioned it. Both fixed in
``rendering/block_timing.py``; the headline-decoupling defect from the same render is covered in
``tests/test_block_timing_fixes.py``.
"""

import itertools
import re
from pathlib import Path

from core.block_types import BlockType
from core.scene_schemas import ComposedBlock, ComposedScene
from interfaces.tts_provider import WordMark
from rendering.block_timing import resolve_item_starts
from rendering.compose import compose_scene
from tests.segment_examples import a_segment

DURATION_MS = 21_000


def _word_marks(narration: str) -> list[WordMark]:
    words = narration.split()
    marks = []
    offset = 0
    for word in words:
        marks.append(WordMark(text=word, offset_ms=offset, duration_ms=300))
        offset += 400
    return marks


def test_text_panel_items_render_in_narration_order_not_authored_order(tmp_path: Path) -> None:
    """The exact live-confirmed defect: an item spoken FIRST rendered THIRD. Authored order is
    reversed from narration order here on purpose, to prove the fix reorders rather than merely
    computing correct-but-unused times."""
    narration = "Third point spoken first. Second point spoken next. First point spoken last."
    word_marks = _word_marks(narration)

    payload = {
        "headline": "h",
        "items": [
            {"text": "authored-first, spoken-last", "anchor_phrase": "point spoken last"},
            {"text": "authored-second, spoken-second", "anchor_phrase": "point spoken next"},
            {"text": "authored-third, spoken-first", "anchor_phrase": "point spoken first"},
        ],
    }
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.TEXT_PANEL, role="only", anchor_phrase=None, payload=payload
            )
        ],
        continues_previous=False,
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"scene": scene.model_dump(), "word_marks": word_marks}
    )

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    rows = re.findall(r'class="blk-text-copy">([^<]+)</span>', html)
    assert rows == [
        "authored-third, spoken-first",
        "authored-second, spoken-second",
        "authored-first, spoken-last",
    ]


def test_graph_diagram_nodes_are_never_reordered(tmp_path: Path) -> None:
    """graph_diagram is deliberately excluded from the sortable set -- CHAIN's rail is drawn in
    node order and GraphDiagramSlots requires edges to reference the n-1 consecutive pairs, so
    reordering nodes would silently break edges. Node order in the output must match authored
    order even when a later node's anchor resolves earlier in the narration."""
    narration = "Second node spoken first. First node spoken last."
    word_marks = _word_marks(narration)

    payload = {
        "headline": "h",
        "layout": "chain",
        "nodes": [
            {"id": "n1", "label": "First", "caption": None, "anchor_phrase": "node spoken last"},
            {"id": "n2", "label": "Second", "caption": None, "anchor_phrase": "node spoken first"},
        ],
        "edges": [],
        "positions": [],
        "traversal": [],
    }
    scene = ComposedScene(
        motif="terminal",
        layout="single",
        blocks=[
            ComposedBlock(
                block_type=BlockType.GRAPH_DIAGRAM, role="only", anchor_phrase=None, payload=payload
            )
        ],
        continues_previous=False,
    )
    segment = a_segment(0, duration_ms=DURATION_MS).model_copy(
        update={"scene": scene.model_dump(), "word_marks": word_marks}
    )

    dest = compose_scene(segment, tmp_path)
    html = dest.read_text(encoding="utf-8")

    labels = re.findall(r'class="blk-graph-label">([^<]+)</div>', html)
    assert labels == ["First", "Second"], "graph_diagram nodes must never be reordered"


def test_an_unmatched_item_interpolates_between_its_matched_neighbours() -> None:
    """The middle item's anchor never appears in the narration; it must land BETWEEN its two
    matched neighbours, not at a flat context-free instant."""
    word_marks = _word_marks("First step happens now. Third step happens later.")
    payload_cls_field = "items"

    class _Item:
        def __init__(self, anchor_phrase: str) -> None:
            self.anchor_phrase = anchor_phrase

    class _Payload:
        def __init__(self, items: list[_Item]) -> None:
            self.items = items

        def model_copy(self, update: dict) -> "_Payload":
            return _Payload(update.get(payload_cls_field, self.items))

    payload = _Payload(
        [
            _Item("first step happens now"),
            _Item("this phrase never appears anywhere"),
            _Item("third step happens later"),
        ]
    )

    _, starts = resolve_item_starts(
        "text_panel", payload, word_marks, entrance_start=0.0, end_s=10.0
    )

    assert starts is not None
    assert starts[0] < starts[1] < starts[2], f"expected increasing order, got {starts}"


def test_every_item_unmatched_spreads_evenly_across_the_visible_window() -> None:
    class _Item:
        def __init__(self, anchor_phrase: str) -> None:
            self.anchor_phrase = anchor_phrase

    class _Payload:
        def __init__(self, items: list[_Item]) -> None:
            self.items = items

        def model_copy(self, update: dict) -> "_Payload":
            return _Payload(update.get("items", self.items))

    payload = _Payload([_Item("nothing matches") for _ in range(4)])
    word_marks = _word_marks("completely unrelated narration text here")

    _, starts = resolve_item_starts(
        "text_panel", payload, word_marks, entrance_start=1.0, end_s=9.0
    )

    assert starts is not None
    assert all(1.0 < s < 9.0 for s in starts)
    assert starts == sorted(starts)
    gaps = [b - a for a, b in itertools.pairwise(starts)]
    assert all(abs(g - gaps[0]) < 1e-9 for g in gaps), f"expected even spacing, got {starts}"
