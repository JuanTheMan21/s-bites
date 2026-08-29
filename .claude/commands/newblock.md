---
description: Add a new BlockType end to end
argument-hint: <block-name>
---

Add the block type **$1** across every place a block must be registered. Missing one leaves a gap
that only surfaces at scene-authoring or render time, on a specific topic, minutes into a job.

1. **Enum** — add `$1` to `BlockType` in `core/block_types.py`.
2. **Allowed-blocks hints** — add `$1` to whichever `VisualIntent`s in `ALLOWED_BLOCKS` a segment
   with this visual pattern would plausibly want. Generous, not exhaustive — this only ever feeds
   `plan_visuals`' prompt guidance, never enforced on the response.
3. **Content schema** — a `StrictSchema` in `core/block_schemas.py` for the fields this block
   needs, registered in `BLOCK_SCHEMAS`. Keep it small; block payloads are what make scene
   authoring cheap and reliable. Must satisfy Azure strict-mode constraints (all fields required,
   no additional properties, no constraint keywords — express bounds as enums).
4. **Partial template** — `rendering/templates/_block_$1.html`, exporting exactly two macros:
   `markup(prefix, payload, compact=false)` and `script(prefix, payload, entrance_start,
   item_starts, step_starts, duration_sec, compact=false)` — **match this parameter list exactly**
   even for parameters this block doesn't use; Jinja silently drops an unbound keyword argument
   rather than erroring (this is exactly how D106 item 2 shipped broken). Every element id must be
   prefixed with `{{ prefix }}` and checked against the *other* block/layout templates' existing
   id suffixes, not just this file, for collisions (D106 item 3).
5. **Compact mode** — the block must render sensibly in both `SINGLE` (full-width, alone) and
   `SPLIT_HORIZONTAL` (half-width, paired) layouts. If it only makes sense in one, say so in the
   template's own comment rather than leaving it to chance.
6. **No CSS initial transform on an animated property.** If this block has an element whose
   "from" state is meant to be invisible/collapsed, set it via an unconditional `tl.set(...)` at
   t=0 in the `script` macro's own JS — never in the partial's static `<style>` block. A GSAP tween
   and a matching CSS initial value on the same property is a real, previously-shipped bug
   (`array_grid`'s strike-through, D106 item 4), not a hypothetical.
7. **Skill pack** — add a "per block type" section to `runtime_skills/scene-authoring/<next-
   version>.md` so the model knows what makes a good `$1` payload. A block the model is never
   asked to fill correctly is dead weight.
8. **Tests** — add a realistic payload to `tests/block_examples.py` (this alone gets `$1` covered
   by `tests/test_block_schemas.py`'s parametrized tests and `tests/test_compose_scene.py`'s
   `SINGLE`/`SPLIT_HORIZONTAL` sweeps automatically). Add `$1` to
   `tests/test_render_segment_live.py`'s live sweep for a real `hyperframes check` pass.

Verify with a real render (`hyperframes check` on a hand-composed scene, not just `pytest`) before
trusting this block — three of T18B's own four found-live bugs were invisible to `pytest`/`ruff`
and surfaced only there.
