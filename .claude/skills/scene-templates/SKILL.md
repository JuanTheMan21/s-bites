---
name: scene-templates
description: How scene authoring works — slot payloads, Jinja templates, HyperFrames timing attributes, and the three render tiers. Load when touching rendering/, scene_author, visual intents, or scene templates.
---

# Scene templates

## The division of labor

**The LLM never writes HTML.** It returns a small pydantic-validated slot payload — a headline, a
list of bullets, node labels. Hand-authored Jinja templates own every byte of markup, including all
HyperFrames timing attributes.

This is deliberate and worth defending when it feels limiting:

- Output tokens are the expensive side of inference. A slot payload is ~100 tokens against ~1500
  for a full composition.
- Invalid HTML becomes structurally impossible rather than something a lint-and-repair loop catches
  most of the time.
- Animation richness lives in templates, where it is version-controlled, diffable, and debuggable —
  instead of being re-rolled by the model on every run, with the quality variance that implies.

If a scene needs expressiveness the slot schema cannot carry, the fix is a richer template or a new
visual intent — not letting the model emit markup.

## Timing comes from measured audio, always

Every `data-duration` traces back to a real `duration_ms` returned by the TTS adapter. Never an LLM
estimate, never a word-count heuristic, never a constant.

```jinja
<div class="clip" data-start="0" data-duration="{{ duration_ms / 1000 }}" data-track-index="0">
```

`scene_author` takes `duration_ms` as a required parameter precisely so this cannot be gotten wrong
by accident. If you find yourself computing a duration inside a template, stop — that is the drift
bug reintroducing itself.

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

Lint before rendering. Catching an invalid composition at write time costs a second; catching it
mid-render costs minutes of a job. The asset-quality hook does this automatically for files in
`rendering/templates/`.

## The three tiers

The same slot payload renders at any tier — the tier changes how it is captured, not what it says.

| Tier | Method | Cost |
|---|---|---|
| 0 | One Playwright screenshot, held for the audio duration | 1 frame |
| 1 | 3-5 screenshots at different reveal states, crossfaded with ffmpeg | ~8 frames |
| 2 | Full HyperFrames render, frame by frame | `duration_sec × fps` |

Tier assignment comes from `core/tier_resolver.py`, a pure function working against a global frame
budget. A template must degrade sensibly to Tier 0: if it is meaningless as a single static frame,
it needs a reveal-state design that ends in a complete picture.

## Adding a visual intent

Use `/newintent <name>`. It touches every registration point — enum, slot schema, template, resolver
cost, tests, and the `visual-intent-selection` runtime skill pack. Missing one leaves a gap that
surfaces only at render time, on one particular topic, minutes into a job.

An intent the model is never told to select is dead code, so the skill-pack update is not optional.
