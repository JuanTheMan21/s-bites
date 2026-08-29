"""Resolving a block's own internal timing -- which beat each of its repeated items or steps
lands on.

Split out of ``rendering/compose.py`` (T18C) once that file would have crossed the 200-line
ceiling with annotation wiring added on top of everything T18C's new blocks need -- this module
holds the per-block-type resolution functions; ``compose.py`` calls them and stays the
orchestration layer.

GRAPH_DIAGRAM's traversal points share the same ``step_starts`` slot ARRAY_GRID's elimination
steps use, rather than a new macro parameter -- both are "a block's own authored,
narration-anchored sub-events," and every block macro's ``script()`` signature already carries
one ``step_starts`` list. GRAPH_DIAGRAM's node *positions* (as opposed to timing) are computed in
the template's own JS instead of here -- they are a one-time layout, never a tracked GSAP tween
property, so nothing about them belongs in this module or in ``RenderableBlock``.
"""

from typing import Any

from interfaces.tts_provider import WordMark
from rendering.anchors import derive_item_anchors, resolve_anchor

# Fallback per-item cascade when an item's own text (or an authored anchor_phrase) doesn't match
# the narration -- the original 0.75s-start/0.22s-stagger waterfall, unchanged since T18B.
_DEFAULT_ITEM_START = 0.75
_DEFAULT_ITEM_STAGGER = 0.22

# Field name, per block type, holding the list of item strings worth their own anchor. Block
# types absent here either have no repeated items, or (array_grid, graph_diagram) carry each
# step/traversal-point's own explicit anchor_phrase in its own schema instead of deriving one
# from display text.
_ITEM_FIELDS: dict[str, str] = {
    "text_panel": "items",
    "graph_diagram": "nodes",
    "code_diff": "lines",
    "sequence_diagram": "messages",
    "timeline": "events",
}

# Block types whose own sub-events carry an authored anchor_phrase, resolved the same way
# (one resolve_anchor call each) rather than derived from an item's display text.
_STEP_FIELDS: dict[str, str] = {"array_grid": "steps", "graph_diagram": "traversal"}


def item_text(item: Any) -> str:
    """A GraphNode/SequenceMessage/TimelineEvent is `.label`; a CodeDiffLine is `.text`; a
    TEXT_PANEL item is a bare string. All are "the text this item is anchored by"."""
    if hasattr(item, "label"):
        return item.label
    if hasattr(item, "text"):
        return item.text
    return str(item)


def resolve_item_starts(
    block_type: str, payload: Any, word_marks: list[WordMark]
) -> list[float] | None:
    field = _ITEM_FIELDS.get(block_type)
    if field is None:
        return None
    items = getattr(payload, field)
    anchors_ms = derive_item_anchors(word_marks, [item_text(item) for item in items])
    return [
        (ms / 1000) if ms is not None else _DEFAULT_ITEM_START + i * _DEFAULT_ITEM_STAGGER
        for i, ms in enumerate(anchors_ms)
    ]


def resolve_step_starts(
    block_type: str, payload: Any, word_marks: list[WordMark]
) -> list[float] | None:
    """ARRAY_GRID's elimination steps and GRAPH_DIAGRAM's traversal points both carry their OWN
    authored ``anchor_phrase`` (unlike items, whose anchor comes from their own display text) --
    resolved the same way, one ``resolve_anchor`` call each, same fallback cascade."""
    field = _STEP_FIELDS.get(block_type)
    if field is None:
        return None
    steps = getattr(payload, field)
    starts = []
    for i, step in enumerate(steps):
        anchor_ms = resolve_anchor(word_marks, step.anchor_phrase)
        fallback = _DEFAULT_ITEM_START + i * _DEFAULT_ITEM_STAGGER
        starts.append(anchor_ms / 1000 if anchor_ms is not None else fallback)
    return starts
