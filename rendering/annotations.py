"""Resolving authored annotations (``core.scene_schemas.ComposedAnnotation``) into renderable
overlays: which real element id each one targets, which container it must render inside (so it
shares its target's transformed ancestor chain -- camera drift, panel idle-bob -- and stays
seek-safe), and when it appears.

T18C's annotation overlay is a cross-cutting mark on another block's content, not a ``BlockType``
occupying its own layout region -- see ``core/scene_schemas.py::ComposedAnnotation``'s docstring.
Each annotation names exactly one target block, and always renders as a sibling inside THAT
block's own container -- there is no scenario where an annotation ends up nested in a different
SPLIT_HORIZONTAL panel than its target, because the container is derived from the target itself,
never assumed.

T18E: every annotation now names a real, already-numbered item (``core/graph/nodes/
annotation_author.py`` authors them only after block content exists, D121/D122) -- so this module
no longer has a "whole block" fallback and drops an annotation outright rather than guessing at
one, on every axis that can go wrong.

T18H: the target id a block/annotation-type pair resolves to can now vary by ``annotation_type``,
not just ``block_type`` -- see ``_ANNOTATION_TARGET_SUFFIX_OVERRIDE``'s own docstring for why
(CURSOR's precise-point design needs a more specific target than CHECK/WARNING's whole-item one,
on GRAPH_DIAGRAM nodes specifically).

T18I: an annotation can now target a LINE-shaped element (a GRAPH_DIAGRAM edge, a
SEQUENCE_DIAGRAM message arrow) via ``ComposedAnnotation.target_kind``, not just a point-shaped
item -- see ``_ANNOTATION_LINK_SUFFIX`` and ``RenderableAnnotation.is_line``.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.block_items import item_count, link_count
from core.block_types import AnnotationTargetKind, GraphLayoutMode, SceneLayout
from core.scene_schemas import ComposedScene
from interfaces.tts_provider import WordMark
from rendering.anchors import resolve_anchor

if TYPE_CHECKING:
    from rendering.compose import RenderableBlock

# Suffix, per block type, an annotation's target_item_index resolves against -- must match the
# id each block partial actually emits for its per-item elements (`{prefix}-{suffix}-{index}`),
# and must name the same set of block types as core.block_items._ITEM_FIELD (a block type added
# to one belongs in the other). Every annotation now targets a real item (T18E, D121/D122) -- a
# block type absent here has no addressable sub-items and can never be a target at all.
_ANNOTATION_TARGET_SUFFIX: dict[str, str] = {
    "array_grid": "cell",
    "graph_diagram": "node",
    "code_panel": "line",
    "code_diff": "line",
    "sequence_diagram": "msg",
    "timeline": "event",
    "text_panel": "row",
    "icon_panel": "chip",
}

# T18I: suffix, per LINE-addressable block type, an annotation's target_item_index resolves
# against when target_kind is LINK -- must match core.block_items._LINK_FIELD's own key set, the
# same paired-map discipline _ANNOTATION_TARGET_SUFFIX/_ITEM_FIELD already establish above. Both
# ids this names (`{prefix}-edge-{i}`, `{prefix}-msg-{i}`) are already-real SVG <line> elements
# -- no template change was needed to make a link targetable, only this resolution.
#
# GRAPH_DIAGRAM is special: `edges` is authored (and real) in BOTH layout modes -- CHAIN's own
# schema requires "exactly the n-1 consecutive pairs in node order" (core/block_schemas_graph.py
# ::GraphDiagramSlots), it is not empty the way a first pass at this assumed. But CHAIN's own rail
# segments render with a DIFFERENT id suffix than GRAPH's canvas edges
# (`_block_graph_diagram.html`: `{prefix}-seg-{i}`, looped over `payload.nodes`, one line short of
# the node count, vs. `{prefix}-edge-{i}`, looped over `payload.edges`) -- so this map alone is
# not enough for graph_diagram; _annotation_target_id below reads the target's own resolved
# `payload.layout` to pick between them.
_ANNOTATION_LINK_SUFFIX: dict[str, str] = {
    "graph_diagram": "edge",
    "sequence_diagram": "msg",
}
_GRAPH_DIAGRAM_CHAIN_LINK_SUFFIX = "seg"

# T18H: only where one specific (block_type, annotation_type) pair needs a MORE PRECISE target
# than the block's own default suffix above -- every other pair falls through to it unchanged.
# CURSOR's glyph tip lands on its target's own bounding-box CENTRE (hfAnnotationPlace's "tip"
# candidate, _annotations.html), which is fine for a single compact element but wrong for
# GRAPH_DIAGRAM's node div: a marker+label+(caption) stack whose bounding-box centre can fall in
# label or caption text rather than the marker circle CURSOR is meant to point at -- confirmed in
# a real render. The marker carries its own id (`_block_graph_diagram.html`) precisely so this can
# target it directly; CHECK/WARNING keep targeting the whole node, since their captions are
# designed to sit beside it, not on a single point.
_ANNOTATION_TARGET_SUFFIX_OVERRIDE: dict[tuple[str, str], str] = {
    ("graph_diagram", "cursor"): "node-marker",
}


@dataclass(frozen=True, slots=True)
class RenderableAnnotation:
    """One annotation, ready for a layout template: its own id prefix, which real element id it
    targets, which container it must render inside, when it appears, and (T18E) its target
    block's own headline element id -- the second thing ``hfAnnotationPlace``
    (``_annotations.html``) keeps an annotation from landing on top of, alongside the caption
    band.

    T18I: ``is_line`` is true when ``target_id`` names a line-shaped element -- either a resolved
    ``LINK`` target, or a SEQUENCE_DIAGRAM message (whose sole addressable item, ``msg``, IS a
    line regardless of ``target_kind``). A partial reads this to choose ``hfAnnotationPlace``'s
    candidate order (``["parallel", ...]`` vs. the point-shaped default); ``hfAnnotationPlace``
    itself separately detects the target element's own tag to compute the parallel geometry --
    two checks with different jobs, not a duplicated one."""

    prefix: str
    annotation_type: str
    caption: str | None
    entrance_start: float
    target_id: str
    container_id: str
    headline_id: str
    is_line: bool


def _annotation_target_id(
    prefix: str,
    block_type: str,
    annotation_type: str,
    target_kind: AnnotationTargetKind,
    item_index: int,
    payload: object,
) -> str:
    # KeyError here is a real bug (the two maps this module and core.block_items keep in sync
    # have drifted), not a case to swallow -- resolve_annotations only reaches this once
    # item_count/link_count has already confirmed item_index is real, which is only possible when
    # block_type has a field in core.block_items, and therefore a suffix here too.
    if target_kind == AnnotationTargetKind.LINK:
        if block_type == "graph_diagram" and getattr(payload, "layout", None) == (
            GraphLayoutMode.CHAIN
        ):
            suffix = _GRAPH_DIAGRAM_CHAIN_LINK_SUFFIX
        else:
            suffix = _ANNOTATION_LINK_SUFFIX[block_type]
    else:
        suffix = _ANNOTATION_TARGET_SUFFIX_OVERRIDE.get(
            (block_type, annotation_type), _ANNOTATION_TARGET_SUFFIX[block_type]
        )
    return f"{prefix}-{suffix}-{item_index}"


def resolve_annotations(
    scene: ComposedScene, blocks: list["RenderableBlock"], word_marks: list[WordMark]
) -> dict[int, list[RenderableAnnotation]]:
    """Resolved annotations, grouped by ``target_block_index`` -- so a layout template can emit
    each block's own annotations as siblings immediately after that block's own markup/script.

    Four ways an annotation is dropped rather than guessed at (T18E, D121/D122 -- a wrong
    annotation is worse than a missing one, the same reasoning as an unresolvable block
    ``anchor_phrase`` falling back to a beat rather than never appearing was the *opposite* call,
    made deliberately different here because a mistargeted overlay actively misleads a viewer
    where a late block entrance does not): ``target_block_index`` out of range (nothing in
    strict-mode structured output can be forced to stay in range -- the same defensive-default
    reasoning ``core/graph/nodes/visual_plan.py::_fallback_scene`` applies to a segment plan's own
    index); ``target_item_index`` outside the target block's real item/link count (T18I: a LINK
    annotation on a block type with no addressable links resolves ``link_count`` to 0 and is
    dropped the same way); or ``anchor_phrase`` not found in this segment's narration."""
    grouped: dict[int, list[RenderableAnnotation]] = {}
    for i, annotation in enumerate(scene.annotations):
        if not 0 <= annotation.target_block_index < len(blocks):
            continue
        target = blocks[annotation.target_block_index]
        is_link = annotation.target_kind == AnnotationTargetKind.LINK
        count = (
            link_count(target.block_type, target.payload)
            if is_link
            else item_count(target.block_type, target.payload)
        )
        # T18J: authored against the PRE-reorder position -- translate through the same
        # permutation resolve_item_starts applied, or a reordered scene mismarks the item.
        target_item_index = annotation.target_item_index
        permutation = target.item_permutation
        if not is_link and permutation is not None and 0 <= target_item_index < len(permutation):
            target_item_index = permutation.index(target_item_index)
        if not 0 <= target_item_index < count:
            continue
        anchor_ms = resolve_anchor(word_marks, annotation.anchor_phrase)
        if anchor_ms is None:
            continue
        container_id = "stage" if scene.layout == SceneLayout.SINGLE else f"{target.prefix}-region"
        grouped.setdefault(annotation.target_block_index, []).append(
            RenderableAnnotation(
                prefix=f"a{i}",
                annotation_type=annotation.annotation_type.value,
                caption=annotation.caption,
                entrance_start=anchor_ms / 1000,
                target_id=_annotation_target_id(
                    target.prefix,
                    target.block_type,
                    annotation.annotation_type.value,
                    annotation.target_kind,
                    target_item_index,
                    target.payload,
                ),
                container_id=container_id,
                headline_id=f"{target.prefix}-headline",
                is_line=is_link or target.block_type == "sequence_diagram",
            )
        )
    return grouped
