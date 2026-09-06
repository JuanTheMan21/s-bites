"""Turning one authored ``ComposedBlock`` into a ``RenderableBlock`` -- content validated into its
own typed schema instance, an id prefix unique within the composition, and narration-anchored
timing already resolved.

Split out of ``rendering/compose.py`` (T18K) once that file would have crossed the 200-line
ceiling with still-sampling wired on top of everything already there -- this module holds the
per-block build step; ``compose.py`` calls it once per block and stays the orchestration layer.
"""

from dataclasses import dataclass
from typing import Any

from core.block_schemas import block_schema_for
from core.scene_schemas import ComposedBlock
from interfaces.tts_provider import WordMark
from rendering.anchors import resolve_anchor
from rendering.annotations import RenderableAnnotation
from rendering.block_timing import resolve_item_starts, resolve_step_starts

# Fallback entrance beat when a block's anchor_phrase doesn't match the narration (or is null) --
# the same small per-block stagger every pre-T18B template hand-picked, generalised so a second
# block in a SPLIT_HORIZONTAL scene doesn't land on top of the first.
_DEFAULT_ENTRANCE_BASE = 0.15
_DEFAULT_ENTRANCE_STEP = 0.25


@dataclass(frozen=True, slots=True)
class RenderableBlock:
    """One block, ready for a layout template: its content validated into its own typed schema
    instance (so a block partial writes ``block.payload.headline`` the same way every pre-T18B
    template wrote ``slots.headline``), an id prefix unique within the composition, narration-
    anchored timing already resolved, and (T18C) the annotations that target it."""

    prefix: str
    block_type: str
    payload: Any
    entrance_start: float
    item_starts: list[float] | None
    step_starts: list[float] | None
    annotations: list[RenderableAnnotation]
    item_permutation: list[int] | None


def build_renderable(
    index: int,
    block: ComposedBlock,
    word_marks: list[WordMark],
    *,
    is_multi_block: bool,
    duration_s: float,
) -> RenderableBlock:
    if block.payload is None:
        raise ValueError(
            f"block {index} ({block.block_type.value}) has no payload -- author_scene fills "
            "every planned block before a scene can compose."
        )
    schema = block_schema_for(block.block_type)
    payload = schema.model_validate(block.payload)
    block_type = block.block_type.value

    structural_start = _DEFAULT_ENTRANCE_BASE + index * _DEFAULT_ENTRANCE_STEP
    # T18J: in a multi-block scene (SPLIT_HORIZONTAL, the only one today) both panels are already
    # visually present from the layout's own tilt-in tween -- a block's headline is that panel's
    # identity label, not content to reveal partway through the segment. Gating it on the block's
    # own anchor_phrase (as a single-block scene correctly does, to reveal content exactly when
    # narration introduces it) stranded a headline until whatever the narration said about that
    # specific panel's topic -- confirmed live, one panel's headline waited until 80% through its
    # segment. A single-block scene keeps the narration-anchored behavior: there the block IS the
    # segment's content, and revealing it on cue is correct choreography.
    if is_multi_block:
        entrance_start = structural_start
    else:
        anchor_ms = resolve_anchor(word_marks, block.anchor_phrase)
        entrance_start = anchor_ms / 1000 if anchor_ms is not None else structural_start

    payload, item_starts, item_permutation = resolve_item_starts(
        block_type, payload, word_marks, entrance_start=entrance_start, end_s=duration_s
    )
    step_starts = resolve_step_starts(
        block_type, payload, word_marks, entrance_start=entrance_start, end_s=duration_s
    )

    return RenderableBlock(
        prefix=f"b{index}",
        block_type=block_type,
        payload=payload,
        entrance_start=entrance_start,
        item_starts=item_starts,
        step_starts=step_starts,
        annotations=[],
        item_permutation=item_permutation,
    )
