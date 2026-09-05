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

T18J: two real-render defects, both traced to this module. First, an unmatched anchor fell back
to a flat 0.75s + 0.22s-per-item cascade -- disconnected from the block's own measured duration
and, worse, from ``entrance_start`` itself, so an unmatched item could appear BEFORE the block
containing it had even entered. Replaced with ``_interpolate_missing``: an unmatched item's time
is now interpolated between its own matched neighbours (or ``entrance_start``/the segment's end
where there is no neighbour on one side), so it always lands somewhere plausible relative to the
items around it and the block's own visible window, never at a fixed instant regardless of
context. Second, items were rendered in AUTHORED order even when their resolved anchors placed
them in a different narration order -- confirmed live: a text_panel item spoken first rendered
third. ``resolve_item_starts`` now reorders a SORTABLE block type's own items (and returns the
reordered payload alongside its times) so visual top-to-bottom always matches narration order;
``_SORTABLE_ITEM_FIELDS`` is a closed, deliberately short list -- a block type belongs on it only
when its own item ORDER carries no meaning independent of when each item is mentioned.
"""

import itertools
from typing import Any, TypeVar

from interfaces.tts_provider import WordMark
from rendering.anchors import resolve_anchor

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

# T18J: block types whose ITEM order carries no meaning of its own -- a plain list of points, a
# labelled set of concepts, a title's key terms -- so reordering them to match narration order is
# a pure improvement. Deliberately excludes every other _ITEM_FIELDS entry: `graph_diagram`'s
# `nodes` (CHAIN's rail is drawn in node order, and GraphDiagramSlots requires the n-1 consecutive
# pairs edges reference) and `code_diff`'s `lines` (line order IS the code). Never add a block
# type here without confirming its own schema truly has no order dependency -- the same "closed,
# deliberately narrow" discipline `_CONTENT_SIZING_CODES` documents for itself.
_SORTABLE_ITEM_FIELDS = frozenset({"text_panel", "icon_panel", "title"})

T = TypeVar("T")


def _interpolate_missing(
    resolved: list[float | None], *, entrance_start: float, end_s: float
) -> list[float]:
    """Fill in every ``None`` by linear interpolation against ``entrance_start``/``end_s`` as
    virtual bookend anchors -- so a gap before the first real match, a gap after the last, and a
    gap between two matches are all the same one-loop case, and every returned time falls inside
    the block's own visible window regardless of how many (or how few) items actually matched.

    All-unmatched degrades to an even spread across the window (the old cascade's replacement);
    a single unmatched item lands at the window's midpoint.
    """
    n = len(resolved)
    if n == 0:
        return []
    end_s = max(end_s, entrance_start)

    points: list[tuple[int, float]] = [(-1, entrance_start)]
    points.extend((i, t) for i, t in enumerate(resolved) if t is not None)
    points.append((n, end_s))

    out = [entrance_start] * n
    for (i1, t1), (i2, t2) in itertools.pairwise(points):
        gap = i2 - i1
        for k in range(i1 + 1, i2):
            out[k] = t1 + (t2 - t1) * (k - i1) / gap

    for i, t in enumerate(resolved):
        if t is not None:
            out[i] = t
    return out


def _resolve_anchor_phrases(
    items: list[Any], word_marks: list[WordMark], *, entrance_start: float, end_s: float
) -> list[float]:
    resolved: list[float | None] = []
    for item in items:
        anchor_ms = resolve_anchor(word_marks, item.anchor_phrase)
        resolved.append(anchor_ms / 1000 if anchor_ms is not None else None)
    return _interpolate_missing(resolved, entrance_start=entrance_start, end_s=end_s)


def resolve_item_starts(
    block_type: str,
    payload: T,
    word_marks: list[WordMark],
    *,
    entrance_start: float,
    end_s: float,
) -> tuple[T, list[float] | None, list[int] | None]:
    """This block's own numbered items, timed against the narration -- and, for a sortable block
    type, reordered so visual order matches narration order. Returns the (possibly reordered)
    payload, its item start times, and (T18J) the permutation applied -- ``permutation[new] ==
    old`` for each item, or ``None`` when nothing was reordered (not sortable, one item, or
    already in order). A non-addressable block type returns ``payload`` unchanged and ``(None,
    None)`` for the other two.

    The permutation matters beyond this function: an annotation's own ``target_item_index`` is
    authored against the PRE-reorder position (``core/graph/nodes/annotation_author.py`` sees
    items in authored order, before this function ever runs) -- caught by project-reviewer, who
    confirmed live that without threading this permutation through to ``rendering/annotations.py``,
    a reordered scene's annotation silently marks the wrong item. ``rendering/compose.py`` carries
    this on ``RenderableBlock.item_permutation`` for exactly that translation.
    """
    field = _ITEM_FIELDS.get(block_type)
    if field is None:
        return payload, None, None

    items = list(getattr(payload, field))
    starts = _resolve_anchor_phrases(items, word_marks, entrance_start=entrance_start, end_s=end_s)

    if block_type in _SORTABLE_ITEM_FIELDS and len(items) > 1:
        order = sorted(range(len(items)), key=lambda i: starts[i])
        if order != list(range(len(items))):
            items = [items[i] for i in order]
            starts = [starts[i] for i in order]
            payload = payload.model_copy(update={field: items})
            return payload, starts, order

    return payload, starts, None


def resolve_step_starts(
    block_type: str,
    payload: Any,
    word_marks: list[WordMark],
    *,
    entrance_start: float,
    end_s: float,
) -> list[float] | None:
    field = _STEP_FIELDS.get(block_type)
    if field is None:
        return None
    return _resolve_anchor_phrases(
        getattr(payload, field), word_marks, entrance_start=entrance_start, end_s=end_s
    )
