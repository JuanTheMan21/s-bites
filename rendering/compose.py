"""Turning a scene-authored ``Segment`` into an HTML composition file.

T18B: replaces the one-``VisualIntent``-picks-one-whole-template dispatch (T17-T18A) with a
layout dispatch. A segment's scene now names a ``SceneLayout`` (``_layout_{layout}.html``) and a
list of blocks; the layout template places each block's markup in its region and stitches its
GSAP contribution onto the one shared timeline -- ``rendering/templates/_layout_*.html`` import
the per-block-type partials (``_block_*.html``) the same way every template already imports
``_tokens.html``/``_captions.html``.

Also where T18B's narration-anchored choreography (see ``rendering/anchors.py``) turns into a
concrete number: a block's own ``anchor_phrase`` (from the plan) and each of its items' own text
are matched against ``word_marks`` here, before a template ever sees them, so a block partial
just reads ``block.entrance_start``/``block.item_starts`` rather than re-deriving timing itself.

Per D2 the LLM never wrote HTML -- ``core/graph/nodes/scene_author.py`` filled each block's
small slot payload, and this is where those payloads become markup. The composition always
lands as ``dest_dir/index.html``: ``hyperframes lint`` (D60) hard-requires that literal name.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.block_schemas import block_schema_for
from core.models import Segment
from core.scene_schemas import ComposedBlock, ComposedScene
from interfaces.tts_provider import WordMark
from mux.caption_cues import group_into_cues
from rendering.anchors import derive_item_anchors, resolve_anchor
from rendering.palettes import select_palette

_TEMPLATES_DIR = Path(__file__).parent / "templates"
# T18A: every template references "./gsap.min.js" rather than a jsDelivr CDN URL, so a render
# needs no network egress -- this is the one copy every composition's directory gets its own of.
_VENDORED_GSAP = _TEMPLATES_DIR / "vendor" / "gsap.min.js"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)

# Fallback entrance beat when a block's anchor_phrase doesn't match the narration (or is null) --
# the same small per-block stagger every pre-T18B template hand-picked, generalised so a second
# block in a SPLIT_HORIZONTAL scene doesn't land on top of the first.
_DEFAULT_ENTRANCE_BASE = 0.15
_DEFAULT_ENTRANCE_STEP = 0.25
# Fallback per-item cascade when an item's own text doesn't match the narration -- bullet_list's
# and diagram_flow's original 0.75s-start/0.22s-stagger waterfall, unchanged.
_DEFAULT_ITEM_START = 0.75
_DEFAULT_ITEM_STAGGER = 0.22

# Field name, per block type, holding the list of item strings worth their own anchor -- a
# TEXT_PANEL's bullets, a DIAGRAM_CHAIN's node labels. Block types absent here (title,
# stat_callout, code_panel, array_grid) either have no repeated items or -- array_grid -- carry
# each step's own explicit anchor_phrase in its own schema instead of deriving one.
_ITEM_FIELDS: dict[str, str] = {"text_panel": "items", "diagram_chain": "nodes"}


@dataclass(frozen=True, slots=True)
class RenderableBlock:
    """One block, ready for a layout template: its content validated into its own typed schema
    instance (so a block partial writes ``block.payload.headline`` the same way every pre-T18B
    template wrote ``slots.headline``), an id prefix unique within the composition, and
    narration-anchored timing already resolved."""

    prefix: str
    block_type: str
    payload: Any
    entrance_start: float
    item_starts: list[float] | None
    step_starts: list[float] | None


def _item_text(item: Any) -> str:
    """A DIAGRAM_CHAIN node is a ``DiagramNode`` (``.label``); a TEXT_PANEL item is a bare
    string. Both are "the text this item is anchored by"."""
    return item.label if hasattr(item, "label") else str(item)


def _resolve_item_starts(
    block_type: str, payload: Any, word_marks: list[WordMark]
) -> list[float] | None:
    field = _ITEM_FIELDS.get(block_type)
    if field is None:
        return None
    items = getattr(payload, field)
    anchors_ms = derive_item_anchors(word_marks, [_item_text(item) for item in items])
    return [
        (ms / 1000) if ms is not None else _DEFAULT_ITEM_START + i * _DEFAULT_ITEM_STAGGER
        for i, ms in enumerate(anchors_ms)
    ]


def _resolve_step_starts(
    block_type: str, payload: Any, word_marks: list[WordMark]
) -> list[float] | None:
    """ARRAY_GRID's elimination steps carry their OWN authored ``anchor_phrase`` per step
    (unlike TEXT_PANEL/DIAGRAM_CHAIN's items, whose anchor comes from their own display text) --
    resolved the same way, one ``resolve_anchor`` call each, same fallback cascade."""
    if block_type != "array_grid":
        return None
    starts = []
    for i, step in enumerate(payload.steps):
        anchor_ms = resolve_anchor(word_marks, step.anchor_phrase)
        fallback = _DEFAULT_ITEM_START + i * _DEFAULT_ITEM_STAGGER
        starts.append(anchor_ms / 1000 if anchor_ms is not None else fallback)
    return starts


def _build_renderable(
    index: int, block: ComposedBlock, word_marks: list[WordMark]
) -> RenderableBlock:
    if block.payload is None:
        raise ValueError(
            f"block {index} ({block.block_type.value}) has no payload -- author_scene fills "
            "every planned block before a scene can compose."
        )
    schema = block_schema_for(block.block_type)
    payload = schema.model_validate(block.payload)

    anchor_ms = resolve_anchor(word_marks, block.anchor_phrase)
    entrance_start = (
        anchor_ms / 1000
        if anchor_ms is not None
        else _DEFAULT_ENTRANCE_BASE + index * _DEFAULT_ENTRANCE_STEP
    )

    return RenderableBlock(
        prefix=f"b{index}",
        block_type=block.block_type.value,
        payload=payload,
        entrance_start=entrance_start,
        item_starts=_resolve_item_starts(block.block_type.value, payload, word_marks),
        step_starts=_resolve_step_starts(block.block_type.value, payload, word_marks),
    )


def compose_scene(segment: Segment, dest_dir: Path) -> Path:
    """Render ``segment``'s scene through its layout template, write it, return the path.

    Validates ``segment.scene`` back through ``ComposedScene`` and each block's payload back
    through ``block_schema_for`` (D29 -- both are untyped on ``Segment``, so this is "the point
    of use" each model's docstring names) before either ever reaches a template, so a malformed
    payload raises pydantic's own ``ValidationError`` here rather than surfacing as a confusing
    Jinja ``AttributeError`` mid-render.

    Raises:
        ValueError: ``segment.duration_ms`` is unmeasured, ``segment.scene`` is unset, or a
            block's payload is still ``None`` (unfilled). Timing comes from measured audio only
            (Invariant 1); a caller who has not measured, planned, or authored cannot satisfy
            this function.
        pydantic.ValidationError: ``segment.scene`` or a block's payload does not match its
            schema.
    """
    if segment.duration_ms is None:
        raise ValueError(
            f"segment {segment.index} has no measured duration_ms, so its scene cannot be "
            "composed -- timing derives only from measured narration audio (Invariant 1)."
        )
    if segment.scene is None:
        raise ValueError(
            f"segment {segment.index} has no scene, so it cannot be composed -- run "
            "plan_visuals and author_scene first."
        )

    scene = ComposedScene.model_validate(segment.scene)
    renderable = [
        _build_renderable(index, block, segment.word_marks)
        for index, block in enumerate(scene.blocks)
    ]
    palette = select_palette(scene.motif)

    template = _env.get_template(f"_layout_{scene.layout.value}.html")
    html = template.render(
        blocks=renderable,
        duration_sec=segment.duration_ms / 1000,
        palette=palette,
        cues=group_into_cues(segment.word_marks),
    )

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "index.html"
    dest.write_text(html, encoding="utf-8")
    shutil.copyfile(_VENDORED_GSAP, dest_dir / "gsap.min.js")
    return dest
