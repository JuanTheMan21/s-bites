---
description: Add a new outline-time visual archetype hint
argument-hint: <intent-name>
---

Add the visual intent **$1** to `VisualIntent`. As of T18B, this is a much shorter list than it
used to be — `VisualIntent` is a coarse, outline-time hint that feeds `plan_visuals`' judgement,
not a template-selection key. If what you actually need is a new visual *pattern* (a block that
doesn't exist yet), use `/newblock` instead — that is the common case now.

1. **Enum** — add `$1` to `VisualIntent` in `core/models.py`.
2. **Allowed blocks** — add an entry to `core/block_types.py::ALLOWED_BLOCKS` naming which
   `BlockType`s a segment with this intent plausibly becomes. Generous, not exhaustive — this
   feeds `plan_visuals`' prompt guidance and a coverage test, and is never enforced on the LLM's
   actual response (strict-mode structured output cannot make a per-item enum choice conditional
   on another field).
3. **Tier support** — add a `TIER_SUPPORT` entry in `core/tier_resolver.py` (this ladder is still
   keyed by `VisualIntent`, unchanged by T18B).
4. **Skill pack** — add a row to `runtime_skills/outline/1.0.md`'s "choosing the visual" table so
   the outline model knows when to reach for `$1`. An intent the model never selects is dead code.
5. **Tests** — a `TIER_SUPPORT`/`ALLOWED_BLOCKS` coverage case for the new intent.

No template, no slot schema, no per-intent tier-cost characteristics belong here — those are
`BlockType`'s concerns, decided per-segment by `plan_visuals` once it has the real narration, not
baked into the intent itself.

Verify with `/tiers` on a topic likely to trigger the new intent.
