"""Resolving planned annotations (``core.scene_schemas.ComposedAnnotation``) into renderable
overlays: which real element id each one targets, which container it must render inside (so it
shares its target's transformed ancestor chain -- camera drift, panel idle-bob -- and stays
seek-safe), and when it appears.

T18C's annotation overlay is a cross-cutting mark on another block's content, not a ``BlockType``
occupying its own layout region -- see ``core/scene_plan_schema.py::PlannedAnnotation``'s
docstring. Each annotation names exactly one target block, and always renders as a sibling
inside THAT block's own container -- there is no scenario where an annotation ends up nested in
a different SPLIT_HORIZONTAL panel than its target, because the container is derived from the
target itself, never assumed.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.block_types import SceneLayout
from core.scene_schemas import ComposedScene
from interfaces.tts_provider import WordMark
from rendering.anchors import resolve_anchor

if TYPE_CHECKING:
    from rendering.compose import RenderableBlock

# Suffix, per block type, an annotation's target_item_index resolves against -- must match the
# id each block partial actually emits for its per-item elements (`{prefix}-{suffix}-{index}`).
# A block type absent here (title, stat_callout) has no addressable sub-items; an annotation
# targeting one of those always attaches to the whole block instead.
_ANNOTATION_TARGET_SUFFIX: dict[str, str] = {
    "array_grid": "cell",
    "graph_diagram": "node",
    "code_panel": "line",
    "code_diff": "line",
    "sequence_diagram": "msg",
    "timeline": "event",
    "text_panel": "row",
}

# An annotation with no matching narration anchor appears this long after its target block's own
# entrance -- late enough that the target has visibly settled first.
_DEFAULT_ANNOTATION_DELAY = 0.5


@dataclass(frozen=True, slots=True)
class RenderableAnnotation:
    """One annotation, ready for a layout template: its own id prefix, which real element id it
    targets, which container it must render inside, and when it appears."""

    prefix: str
    annotation_type: str
    caption: str | None
    entrance_start: float
    target_id: str
    container_id: str


def _annotation_target_id(prefix: str, block_type: str, item_index: int | None) -> str:
    if item_index is None:
        return f"{prefix}-wrap"
    suffix = _ANNOTATION_TARGET_SUFFIX.get(block_type)
    if suffix is None:
        return f"{prefix}-wrap"
    return f"{prefix}-{suffix}-{item_index}"


def resolve_annotations(
    scene: ComposedScene, blocks: list["RenderableBlock"], word_marks: list[WordMark]
) -> dict[int, list[RenderableAnnotation]]:
    """Resolved annotations, grouped by ``target_block_index`` -- so a layout template can emit
    each block's own annotations as siblings immediately after that block's own markup/script.

    An annotation whose ``target_block_index`` is out of range is dropped silently -- nothing in
    strict-mode structured output can be forced to stay in range (the same defensive-default
    reasoning ``core/graph/nodes/visual_plan.py::_fallback_scene`` already applies to a segment
    plan's own index)."""
    grouped: dict[int, list[RenderableAnnotation]] = {}
    for i, annotation in enumerate(scene.annotations):
        if not 0 <= annotation.target_block_index < len(blocks):
            continue
        target = blocks[annotation.target_block_index]
        container_id = "stage" if scene.layout == SceneLayout.SINGLE else f"{target.prefix}-region"
        anchor_ms = resolve_anchor(word_marks, annotation.anchor_phrase)
        entrance_start = (
            anchor_ms / 1000
            if anchor_ms is not None
            else target.entrance_start + _DEFAULT_ANNOTATION_DELAY
        )
        grouped.setdefault(annotation.target_block_index, []).append(
            RenderableAnnotation(
                prefix=f"a{i}",
                annotation_type=annotation.annotation_type.value,
                caption=annotation.caption,
                entrance_start=entrance_start,
                target_id=_annotation_target_id(
                    target.prefix, target.block_type, annotation.target_item_index
                ),
                container_id=container_id,
            )
        )
    return grouped
