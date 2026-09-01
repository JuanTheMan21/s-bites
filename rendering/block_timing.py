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

T18G: ``_ITEM_FIELDS`` used to resolve each item's anchor from its own short *display text*
(``GraphNode.label``, a bare ``text_panel`` string, ``CodeDiffLine.text``) via
``derive_item_anchors`` -- a substring match against a 2-3 word label that D119/D121 found
matches the wrong, out-of-order occurrence in real narration (the same failure mode D119 already
fixed for ``sequence_diagram``/``timeline`` by giving those items their own authored
``anchor_phrase`` instead). ``GraphNode``, ``CodeDiffLine``, and the new ``TextPanelItem`` now
each carry that same authored ``anchor_phrase`` field, so ``resolve_item_starts`` resolves it
exactly the way ``resolve_step_starts`` always has -- the two functions differ only in which
field name they read, not in mechanism, now that every _ITEM_FIELDS item has its own anchor too.
"""

from typing import Any

from interfaces.tts_provider import WordMark
from rendering.anchors import resolve_anchor

# Fallback per-item cascade when an item's own authored anchor_phrase doesn't match the narration
# -- the original 0.75s-start/0.22s-stagger waterfall, unchanged since T18B.
_DEFAULT_ITEM_START = 0.75
_DEFAULT_ITEM_STAGGER = 0.22

# Field name, per block type, holding a list of items that each carry their own authored
# anchor_phrase but are exposed to a block's script() macro as `item_starts` rather than
# `step_starts` -- the split is purely about which macro parameter a block partial reads, not
# about resolution mechanism (identical to _STEP_FIELDS below since T18G).
_ITEM_FIELDS: dict[str, str] = {
    "text_panel": "items",
    "graph_diagram": "nodes",
    "code_diff": "lines",
    "title": "key_terms",
    "icon_panel": "items",
}

# Block types whose own sub-events carry an authored anchor_phrase, exposed as `step_starts`.
_STEP_FIELDS: dict[str, str] = {
    "array_grid": "steps",
    "graph_diagram": "traversal",
    "sequence_diagram": "messages",
    "timeline": "events",
}


def _resolve_anchor_phrases(items: list[Any], word_marks: list[WordMark]) -> list[float]:
    starts = []
    for i, item in enumerate(items):
        anchor_ms = resolve_anchor(word_marks, item.anchor_phrase)
        fallback = _DEFAULT_ITEM_START + i * _DEFAULT_ITEM_STAGGER
        starts.append(anchor_ms / 1000 if anchor_ms is not None else fallback)
    return starts


def resolve_item_starts(
    block_type: str, payload: Any, word_marks: list[WordMark]
) -> list[float] | None:
    field = _ITEM_FIELDS.get(block_type)
    if field is None:
        return None
    return _resolve_anchor_phrases(getattr(payload, field), word_marks)


def resolve_step_starts(
    block_type: str, payload: Any, word_marks: list[WordMark]
) -> list[float] | None:
    field = _STEP_FIELDS.get(block_type)
    if field is None:
        return None
    return _resolve_anchor_phrases(getattr(payload, field), word_marks)
