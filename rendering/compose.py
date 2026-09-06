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
T18C split the per-item/per-step/per-node resolution itself into ``rendering/block_timing.py``,
and added ``rendering/annotations.py`` for the new cross-cutting overlay marks; T18K split the
per-block build step into ``rendering/renderable.py`` -- this module stays the orchestration
layer: build every block, resolve every annotation, plan captions/stills, render.

Per D2 the LLM never wrote HTML -- ``core/graph/nodes/scene_author.py`` filled each block's
small slot payload, and this is where those payloads become markup. The composition always
lands as ``dest_dir/index.html``: ``hyperframes lint`` (D60) hard-requires that literal name.
"""

import shutil
from dataclasses import replace
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.models import Segment, Tier
from core.scene_schemas import ComposedScene
from mux.caption_cues import cues_for_segment
from rendering.annotations import resolve_annotations
from rendering.palettes import select_palette
from rendering.renderable import build_renderable
from rendering.still_plan import plan_still_samples, write_still_plan

_TEMPLATES_DIR = Path(__file__).parent / "templates"
# T18A: every template references "./gsap.min.js" rather than a jsDelivr CDN URL, so a render
# needs no network egress -- this is the one copy every composition's directory gets its own of.
_VENDORED_GSAP = _TEMPLATES_DIR / "vendor" / "gsap.min.js"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
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
    duration_s = segment.duration_ms / 1000
    is_multi_block = len(scene.blocks) > 1
    renderable = [
        build_renderable(
            index,
            block,
            segment.word_marks,
            is_multi_block=is_multi_block,
            duration_s=duration_s,
        )
        for index, block in enumerate(scene.blocks)
    ]
    annotations_by_block = resolve_annotations(scene, renderable, segment.word_marks)
    renderable = [
        replace(block, annotations=annotations_by_block.get(index, []))
        for index, block in enumerate(renderable)
    ]
    palette = select_palette(scene.motif)

    # T18K/D161: Tier 0 is one still held for the whole segment -- it cannot show more than one
    # of a multi-cue segment's captions, and one wrong frozen caption is worse than none. The
    # `.srt` sidecar (mux/subtitles.py) still carries every cue regardless of tier.
    cues = (
        []
        if segment.tier is Tier.STATIC
        else cues_for_segment(segment.word_marks, segment.narration, segment.duration_ms)
    )

    template = _env.get_template(f"_layout_{scene.layout.value}.html")
    html = template.render(blocks=renderable, duration_sec=duration_s, palette=palette, cues=cues)

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "index.html"
    dest.write_text(html, encoding="utf-8")
    shutil.copyfile(_VENDORED_GSAP, dest_dir / "gsap.min.js")
    # T18K: a still-sampling plan for Tier 1's crossfade -- every cue start plus every block's own
    # reveal timing, so `rendering/reveal.py` can capture at cue boundaries instead of blindly
    # even-spaced instants. Written for every tier (cheap); only Tier 1 reads it back.
    candidate_times = [
        t
        for block in renderable
        for t in (block.entrance_start, *(block.item_starts or []), *(block.step_starts or []))
    ]
    write_still_plan(
        dest_dir,
        plan_still_samples(
            [cue.start_ms / 1000 for cue in cues], candidate_times, duration_s=duration_s
        ),
    )
    return dest
