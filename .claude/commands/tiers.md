---
description: Dry-run outline and tier assignment for a topic, without rendering
argument-hint: <topic>
---

Run the pipeline for **$ARGUMENTS** only as far as tier assignment, then stop. No scene authoring,
no rendering.

Print a table: segment index, title, visual intent, importance score, estimated duration, assigned
tier, and cumulative frame cost against `FRAME_BUDGET`.

Then report:

- Total frames committed vs the budget
- The tier spread — how many segments at each of Tier 0, 1, 2
- Which segments were demoted, and what they were demoted from

This is the cheap iteration loop. Rendering a 7-minute video to discover the tier distribution is
wrong costs minutes; this costs one LLM call. Use it whenever tuning `FRAME_BUDGET`, importance
scoring, or intent classification.

Flag it if all segments landed on one tier — that means the budget is mistuned and the tier system
is doing nothing.
