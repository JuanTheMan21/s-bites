"""T18K/D163: the user's own report -- "this graph had point number two appear first" -- is a
reveal-*timing* defect, not a draw-order defect. ``graph_diagram`` nodes are never reordered
(``tests/test_item_timing_order.py::test_graph_diagram_nodes_are_never_reordered`` covers that
half), but nothing previously stopped a later node's resolved anchor from landing earlier than an
earlier node's, so it could still visually enter first despite being drawn second.
``rendering/timing_math.py::clamp_non_decreasing`` is the fix: a running max in draw order, never
a re-sort.
"""

from interfaces.tts_provider import WordMark
from rendering.block_timing import resolve_item_starts, resolve_step_starts


def _word_marks(narration: str) -> list[WordMark]:
    words = narration.split()
    marks = []
    offset = 0
    for word in words:
        marks.append(WordMark(text=word, offset_ms=offset, duration_ms=300))
        offset += 400
    return marks


class _Anchored:
    """A minimal item/step/node stand-in -- every ``_ITEM_FIELDS``/``_STEP_FIELDS`` element this
    module resolves needs only ``anchor_phrase``."""

    def __init__(self, anchor_phrase: str) -> None:
        self.anchor_phrase = anchor_phrase


class _Payload:
    """A minimal payload stand-in, with whichever field name the block type under test reads --
    ``resolve_item_starts``'s sortable branch calls ``model_copy`` on a real match, so this
    supports that too."""

    def __init__(self, **fields: list[_Anchored]) -> None:
        self.__dict__.update(fields)

    def model_copy(self, update: dict) -> "_Payload":
        return _Payload(**{**self.__dict__, **update})


def test_graph_diagram_node_reveal_times_are_clamped_non_decreasing() -> None:
    """Node 1 (drawn second) has an anchor phrase that matches earlier in the narration than
    node 0's (drawn first) -- without a clamp, node 1's resolved reveal time is earlier, so it
    visually enters first even though it is drawn second."""
    word_marks = _word_marks("Second node spoken first. First node spoken last.")
    payload = _Payload(
        nodes=[
            _Anchored("node spoken last"),  # node 0, drawn first -- resolves LATE
            _Anchored("node spoken first"),  # node 1, drawn second -- resolves EARLY
        ]
    )

    _, starts, permutation = resolve_item_starts(
        "graph_diagram", payload, word_marks, entrance_start=0.0, end_s=10.0
    )

    assert permutation is None, "graph_diagram must never be reordered"
    assert starts is not None
    assert starts[0] > 0.0, "node 0's anchor should have resolved to a real, non-default instant"
    assert starts == sorted(starts), f"node reveal times must be non-decreasing, got {starts}"
    assert starts[1] >= starts[0], "node 1 must never visually enter before node 0"


def test_code_diff_line_times_are_clamped_non_decreasing() -> None:
    """code_diff's line order IS the code -- same structural-order reasoning as graph_diagram,
    same clamp."""
    word_marks = _word_marks("Second line spoken first. First line spoken last.")
    payload = _Payload(lines=[_Anchored("line spoken last"), _Anchored("line spoken first")])

    _, starts, permutation = resolve_item_starts(
        "code_diff", payload, word_marks, entrance_start=0.0, end_s=10.0
    )

    assert permutation is None, "code_diff must never be reordered"
    assert starts is not None
    assert starts == sorted(starts), f"line reveal times must be non-decreasing, got {starts}"


def test_array_grid_step_times_are_clamped_non_decreasing() -> None:
    """Every ``resolve_step_starts`` result is an ordered event sequence by definition -- the
    same clamp as the item-field case, applied unconditionally."""
    word_marks = _word_marks("Second step spoken first. First step spoken last.")
    payload = _Payload(steps=[_Anchored("step spoken last"), _Anchored("step spoken first")])

    starts = resolve_step_starts("array_grid", payload, word_marks, entrance_start=0.0, end_s=10.0)

    assert starts is not None
    assert starts == sorted(starts), f"step times must be non-decreasing, got {starts}"


def test_sortable_item_fields_are_unaffected_by_the_clamp() -> None:
    """text_panel/icon_panel/title reorder instead of clamping -- confirming the clamp path is
    never reached for a sortable field (a regression here would silently defeat the T18J
    reorder fix by clamping instead of sorting)."""
    word_marks = _word_marks("Second item spoken first. First item spoken last.")
    payload = _Payload(items=[_Anchored("item spoken last"), _Anchored("item spoken first")])

    _, starts, permutation = resolve_item_starts(
        "text_panel", payload, word_marks, entrance_start=0.0, end_s=10.0
    )

    assert permutation == [1, 0], "a sortable field must reorder, not clamp"
    assert starts is not None
    assert starts == sorted(starts)
