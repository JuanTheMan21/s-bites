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
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.block_items import item_count
from core.block_types import SceneLayout
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
}


@dataclass(frozen=True, slots=True)
class RenderableAnnotation:
    """One annotation, ready for a layout template: its own id prefix, which real element id it
    targets, which container it must render inside, when it appears, and (T18E) its target
    block's own headline element id -- the second thing ``hfAnnotationPlace``
    (``_annotations.html``) keeps an annotation from landing on top of, alongside the caption
    band."""

    prefix: str
    annotation_type: str
    caption: str | None
    entrance_start: float
    target_id: str
    container_id: str
    headline_id: str


def _annotation_target_id(prefix: str, block_type: str, item_index: int) -> str:
    # KeyError here is a real bug (the two maps this module and core.block_items keep in sync
    # have drifted), not a case to swallow -- resolve_annotations only reaches this once
    # item_count has already confirmed item_index is real, which is only possible when
    # block_type has a field in core.block_items, and therefore a suffix here too.
    return f"{prefix}-{_ANNOTATION_TARGET_SUFFIX[block_type]}-{item_index}"


def resolve_annotations(
    scene: ComposedScene, blocks: list["RenderableBlock"], word_marks: list[WordMark]
) -> dict[int, list[RenderableAnnotation]]:
    """Resolved annotations, grouped by ``target_block_index`` -- so a layout template can emit
    each block's own annotations as siblings immediately after that block's own markup/script.

    Three ways an annotation is dropped rather than guessed at (T18E, D121/D122 -- a wrong
    annotation is worse than a missing one, the same reasoning as an unresolvable block
    ``anchor_phrase`` falling back to a beat rather than never appearing was the *opposite* call,
    made deliberately different here because a mistargeted overlay actively misleads a viewer
    where a late block entrance does not): ``target_block_index`` out of range (nothing in
    strict-mode structured output can be forced to stay in range -- the same defensive-default
    reasoning ``core/graph/nodes/visual_plan.py::_fallback_scene`` applies to a segment plan's own
    index); ``target_item_index`` outside the target block's real item count; or ``anchor_phrase``
    not found in this segment's narration."""
    grouped: dict[int, list[RenderableAnnotation]] = {}
    for i, annotation in enumerate(scene.annotations):
        if not 0 <= annotation.target_block_index < len(blocks):
            continue
        target = blocks[annotation.target_block_index]
        if not 0 <= annotation.target_item_index < item_count(target.block_type, target.payload):
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
                    target.prefix, target.block_type, annotation.target_item_index
                ),
                container_id=container_id,
                headline_id=f"{target.prefix}-headline",
            )
        )
    return grouped
