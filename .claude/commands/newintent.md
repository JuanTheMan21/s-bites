---
description: Add a new visual intent end to end
argument-hint: <intent-name>
---

Add the visual intent **$1** across every place an intent must be registered. Missing one leaves a
gap that only surfaces at render time, on a specific topic, minutes into a job.

1. **Enum** — add `$1` to `VisualIntent` in `core/models.py`.
2. **Slot schema** — a pydantic model for the fields this intent needs. Keep it small; slot
   payloads are what make scene authoring cheap and reliable. Must satisfy Azure strict-mode
   constraints (all fields required, no additional properties).
3. **Template** — `rendering/templates/$1.html`, with the HyperFrames `data-*` timing attributes
   left as Jinja placeholders for measured audio duration. Never hardcode a duration.
4. **Tier support** — confirm the template renders at every tier this intent can be assigned:
   static, reveal states, and animated. If it only makes sense at some tiers, encode that in the
   resolver rather than leaving it to chance.
5. **Resolver** — add the frame-cost characteristics for `$1` in `core/tier_resolver.py`.
6. **Tests** — resolver cases for the new intent, plus a template render test against a fixed
   duration.
7. **Skill pack** — update `runtime_skills/visual-intent-selection` so the model knows when to
   choose `$1`. An intent the model never selects is dead code.

Verify with `/tiers` on a topic likely to trigger the new intent.
