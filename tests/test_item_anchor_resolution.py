"""T18G: pins that ``resolve_item_starts`` resolves each item's own authored ``anchor_phrase``,
not the item's short display text (``GraphNode.label``, ``CodeDiffLine.text``, a bare
``text_panel`` string) -- the mechanism D119 already proved for ``_STEP_FIELDS`` block types,
extended here to the three ``_ITEM_FIELDS`` types that used to fall back to matching a short
label against the narration (D121's headline finding: 9 of ~20 sampled ``*Starts`` arrays in
T18D's real-render matrix hit this).

Each fixture below deliberately gives an item a display text that does NOT appear anywhere in the
narration -- so a resolver still keyed to display text would find no match at all and fall back to
the positional default for every item, while the fix (keyed to ``anchor_phrase``) resolves a real,
narration-anchored time.

T18J: ``resolve_item_starts`` gained required ``entrance_start``/``end_s`` keywords and now
returns ``(payload, starts)`` rather than bare ``starts`` -- the fallback-behavior test below was
rewritten for the new interpolation-based fallback (``tests/test_item_timing_order.py`` covers
that fallback and the reordering fix in full); the three anchor-resolution proofs are unaffected
since every item in them matches, so neither change alters their expected values.
"""

from core.block_schemas import TextPanelSlots
from core.block_schemas_diff import CodeDiffSlots
from core.block_schemas_graph import GraphDiagramSlots
from interfaces.tts_provider import WordMark
from rendering.block_timing import resolve_item_starts

_ENTRANCE_START = 0.15
_END_S = 10.0


def _word_marks(narration: str) -> list[WordMark]:
    words = narration.split()
    marks = []
    offset = 0
    for word in words:
        marks.append(WordMark(text=word, offset_ms=offset, duration_ms=300))
        offset += 400
    return marks


def test_graph_diagram_nodes_resolve_via_anchor_phrase_not_label() -> None:
    word_marks = _word_marks("First the request reaches a gateway then it forwards onward")
    payload = GraphDiagramSlots.model_validate(
        {
            "headline": "h",
            "layout": "graph",
            "nodes": [
                # "Ingress" never appears in the narration -- a label-text match would find
                # nothing and fall back to the positional default.
                {
                    "id": "n1",
                    "label": "Ingress",
                    "caption": None,
                    "anchor_phrase": "the request reaches",
                },
                {
                    "id": "n2",
                    "label": "Relay",
                    "caption": None,
                    "anchor_phrase": "it forwards onward",
                },
            ],
            "edges": [],
            "positions": [],
            "traversal": [],
        }
    )

    _, starts, _permutation = resolve_item_starts(
        "graph_diagram", payload, word_marks, entrance_start=_ENTRANCE_START, end_s=_END_S
    )

    assert starts is not None
    # "the request reaches" starts at word index 1 (0.4s); "it forwards onward" at index 7 (2.8s).
    assert starts[0] == 0.4
    assert starts[1] == 2.8


def test_text_panel_items_resolve_via_anchor_phrase_not_text() -> None:
    word_marks = _word_marks("Untrusted input reaches the query before anything checks it")
    payload = TextPanelSlots.model_validate(
        {
            "headline": "h",
            "items": [
                {
                    # The item's own paraphrased `text` doesn't appear verbatim in the
                    # narration -- only `anchor_phrase` does.
                    "text": "Nothing validates the value first.",
                    "anchor_phrase": "reaches the query before anything checks",
                }
            ],
        }
    )

    _, starts, _permutation = resolve_item_starts(
        "text_panel", payload, word_marks, entrance_start=_ENTRANCE_START, end_s=_END_S
    )

    assert starts is not None
    assert starts[0] == 0.8  # "reaches" is word index 2


def test_code_diff_lines_resolve_via_anchor_phrase_not_source_text() -> None:
    word_marks = _word_marks("The driver escapes the value before the query ever runs")
    payload = CodeDiffSlots.model_validate(
        {
            "headline": "h",
            "language": "python",
            "caption": None,
            "lines": [
                {
                    # Source code text never appears in spoken narration -- only anchor_phrase
                    # does.
                    "op": "add",
                    "text": 'query = "SELECT * FROM users WHERE name = %s"',
                    "anchor_phrase": "the driver escapes the value",
                }
            ],
        }
    )

    _, starts, _permutation = resolve_item_starts(
        "code_diff", payload, word_marks, entrance_start=_ENTRANCE_START, end_s=_END_S
    )

    assert starts is not None
    assert starts[0] == 0.0


def test_unresolved_anchor_phrases_interpolate_across_the_visible_window() -> None:
    """T18J: replaces the old flat-cascade fallback proof. Neither anchor matches, so both items
    must land somewhere in ``[entrance_start, end_s]``, in order -- not at a fixed instant
    disconnected from the block's own timing."""
    word_marks = _word_marks("Nothing here mentions the anchor at all")
    payload = GraphDiagramSlots.model_validate(
        {
            "headline": "h",
            "layout": "graph",
            "nodes": [
                {
                    "id": "n1",
                    "label": "Node",
                    "caption": None,
                    "anchor_phrase": "a phrase never spoken in this narration",
                },
                {
                    "id": "n2",
                    "label": "Node2",
                    "caption": None,
                    "anchor_phrase": "also never spoken here",
                },
            ],
            "edges": [],
            "positions": [],
            "traversal": [],
        }
    )

    _, starts, _permutation = resolve_item_starts(
        "graph_diagram", payload, word_marks, entrance_start=_ENTRANCE_START, end_s=_END_S
    )

    assert starts is not None
    assert starts[0] < starts[1]
    assert all(_ENTRANCE_START <= s <= _END_S for s in starts)
