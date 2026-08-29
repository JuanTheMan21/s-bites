---
name: scene-templates
description: How scene authoring works — layouts, blocks, Jinja partials, HyperFrames timing attributes, and the three render tiers. Load when touching rendering/, scene_author, visual_plan, block types, or scene templates.
---

# Scene templates

## T18B: compositional, not one-template-per-intent

A segment's scene is a `SceneLayout` (`single` or `split_horizontal`) filled with 1-2 `BlockType`
blocks, planned once for the *whole video* by `plan_visuals` (`core/graph/nodes/visual_plan.py`)
and filled one block at a time by `author_scene` (`core/graph/nodes/scene_author.py::fill_block`).
`rendering/compose.py` dispatches by layout, not by `VisualIntent` — `VisualIntent` (chosen at
outline time) is now only a coarse hint feeding `core/block_types.py::ALLOWED_BLOCKS`; it does not
select a template.

## The division of labor

**The LLM never writes HTML.** Two calls per block-bearing segment, never one call for a whole
scene: `plan_visuals` asks for a `VideoScenePlan` (motif + per-segment layout + an ordered list of
`{block_type, role, anchor_phrase}` — plain enums, no content), then one further call per planned
block asks for that block's own small pydantic-validated payload (a headline, a list of items,
array cells). Hand-authored Jinja partials (`rendering/templates/_block_*.html`) own every byte of
markup, including all HyperFrames timing attributes. Two calls instead of one is not a style
choice — Azure strict structured output cannot express a discriminated union, so a single call
asking "one of several possible block shapes" is not buildable at all (see decisionlog D29, D105).

This is deliberate and worth defending when it feels limiting:

- Output tokens are the expensive side of inference. A block payload is ~100 tokens against ~1500
  for a full composition.
- Invalid HTML becomes structurally impossible rather than something a lint-and-repair loop catches
  most of the time.
- Animation richness lives in partials, where it is version-controlled, diffable, and debuggable —
  instead of being re-rolled by the model on every run, with the quality variance that implies.

If a scene needs expressiveness a block's payload cannot carry, the fix is a richer block (or a new
one) — not letting the model emit markup.

## Timing comes from measured audio, always

Every `data-duration` traces back to a real `duration_ms` returned by the TTS adapter. Never an LLM
estimate, never a word-count heuristic, never a constant.

```jinja
<div class="clip" data-start="0" data-duration="{{ duration_sec }}" data-track-index="0">
```

`fill_block`/`compose_scene` both take `duration_ms`/`segment.duration_ms` as a required input
precisely so this cannot be gotten wrong by accident (Invariant 1). If you find yourself computing
a duration inside a template, stop — that is the drift bug reintroducing itself.

**Narration-anchored timing, not just narration-derived duration.** `rendering/anchors.py` matches
a block's own `anchor_phrase` (from the plan) and, for blocks with repeated items (`text_panel`'s
items, `graph_diagram`'s nodes), each item's own text against `segment.word_marks` — real timing
when a match is found, a fixed cascade otherwise. This resolution now lives in
`rendering/block_timing.py` (split out of `rendering/compose.py` in T18C), called from
`compose.py` before a template ever sees it; a block partial reads
`block.entrance_start`/`item_starts`/`step_starts`, already resolved.

**T18C added annotations — a separate concept from a `BlockType`.** An annotation (cursor/check/
warning) targets a specific element *inside* an already-planned block rather than filling its own
`SceneLayout` region — see `core/scene_plan_schema.py::PlannedAnnotation`'s docstring and
`rendering/annotations.py`. Do not register a new annotation type the same way as "Adding a block
type" below; it follows its own pattern (`_annotation_<name>.html`, `AnnotationType` in
`core/block_types.py`, no `BLOCK_SCHEMAS`/`ALLOWED_BLOCKS` entry).

## HyperFrames essentials

HyperFrames is a **Node CLI** (`npx hyperframes render|lint|check|doctor`), not a Python library.
Compositions are plain HTML with data attributes:

- Root carries `data-composition-id`, dimensions, and fps
- Timed elements need `class="clip"`, `data-start`, `data-duration`, `data-track-index`
- Times are in **seconds** (the pipeline stores milliseconds — convert at the template boundary,
  and only there)
- `data-track-index` controls layering
- Animations must be *seekable* — CSS keyframes, WAAPI, GSAP. Anything driven by wall-clock time or
  un-seekable JS renders as a frozen frame, because the renderer steps frame by frame rather than
  playing in real time
- **Never a CSS initial `transform` on a property a GSAP tween also targets.** Set the from-state
  in JS via an unconditional `tl.set(...)` at t=0, covering every instance regardless of whether a
  later tween ever actually retargets it. `array_grid`'s strike-through line reintroduced this
  trap once already, D106 item 4 — it is a real, currently-live risk, not a hypothetical.

Lint before rendering. Catching an invalid composition at write time costs a second; catching it
mid-render costs minutes of a job. The asset-quality hook does this automatically for files in
`rendering/templates/`.

## Layouts and blocks are separate concerns

A layout template (`_layout_single.html`, `_layout_split_horizontal.html`) owns the `#root`/
`#camera`/`#stage` shell, the shared paused `gsap.timeline`, and the scene-level camera drift.
It dynamically imports each planned block's partial (`{% import "_block_" ~ block.block_type ~
".html" as blk %}`) and places its markup in a region. A block partial exports two macros with
**identical parameter lists** — `markup(prefix, payload, compact)` and `script(prefix, payload,
entrance_start, item_starts, step_starts, duration_sec, compact)` — even for parameters only one
of the two actually uses. Jinja does not warn on a silently-unbound keyword argument the way a
real function signature mismatch would; a layout passing `compact=true` to a macro that never
declared the parameter just silently does nothing (D106 item 2, found live).

**Every element id must be unique within the whole composition, not just within one block.**
`block.prefix` (`b0`, `b1`, ...) namespaces a block's own ids, but a block's *internal* id
suffixes can still collide with a layout's own wrapper ids if both reach for the same obvious
name — `code_panel`'s own `-panel` div collided with `_layout_split_horizontal.html`'s own
`-panel` wrapper this way (D106 item 3, found only by a real `hyperframes check` warning, not by
reading either template alone). When adding a block or a layout, check the *other* templates'
existing id suffixes, don't just check your own file for internal collisions.

## The three tiers

The same composed scene renders at any tier — the tier changes how it is captured, not what it
says.

| Tier | Method | Cost |
|---|---|---|
| 0 | One Playwright screenshot, held for the audio duration | 1 frame |
| 1 | 3-5 screenshots at different reveal states, crossfaded with ffmpeg | ~8 frames |
| 2 | Full HyperFrames render, frame by frame | `duration_sec × fps` |

Tier assignment comes from `core/tier_resolver.py`, a pure function working against a global frame
budget, still keyed by `VisualIntent` (unchanged by T18B — see `core/block_types.py`'s own
docstring for why that boundary was deliberately left alone). A scene must degrade sensibly to
Tier 0: if it is meaningless as a single static frame, its blocks need a reveal-state design that
ends in a complete picture.

## Adding a block type

Use `/newblock <name>`. This is the common case now — a new visual pattern is almost always a new
`BlockType`, not a new `VisualIntent`. Registration points: `core/block_types.py` (`BlockType`
enum, `ALLOWED_BLOCKS` entries), `core/block_schemas.py` (a `StrictSchema` for the block's
content), two Jinja partial macros (`markup`, `script`) in `rendering/templates/_block_<name>.
html`, `runtime_skills/scene-authoring/<next-version>.md`'s per-block-type guidance, and tests
(`tests/test_block_schemas.py`'s parametrized coverage picks a new `BlockType` up automatically;
add a realistic payload to `tests/block_examples.py` so it does). Missing one leaves a gap that
surfaces only at render time, on one particular topic, minutes into a job.

## Adding a visual intent (the rarer case)

Use `/newintent <name>`. `VisualIntent` is now just an outline-time hint — the registration list is
short: the enum in `core/models.py`, an `ALLOWED_BLOCKS` entry (which block types this intent
plausibly becomes), a `TIER_SUPPORT` entry in `core/tier_resolver.py`, and a row in
`runtime_skills/outline/1.0.md`'s table. No template, no slot schema, no tier-cost characteristics
of its own — those all belong to whichever block type(s) `plan_visuals` ends up choosing for a
segment with this intent, not to the intent itself.
