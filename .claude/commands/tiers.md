---
description: Dry-run outline and tier assignment for a topic, without rendering
argument-hint: <topic>
---

Run the pipeline for **$ARGUMENTS** only as far as tier assignment, then stop. No scene authoring,
no rendering.

```bash
PYTHONPATH=. .venv/Scripts/python.exe scripts/tier_dry_run.py "$ARGUMENTS"
```

It prints a table — segment index, title, visual intent, importance score, **measured** duration,
assigned tier, and cumulative frame cost against `FRAME_BUDGET` — then:

- Total frames committed vs the budget
- The tier spread — how many segments at each of Tier 0, 1, 2
- Which segments were demoted, and what they were demoted from

Read the numbers back to the user, then say what they mean for the budget.

**The duration is measured, never estimated.** Tier 2 costs duration × fps, so a tuning run against
guessed durations tunes against fiction — and Invariant 1 says timing derives from measured audio
everywhere else, so it may as well be true here too. That means this run makes real TTS calls: one
outline completion, one narration completion per segment, and one synthesis per segment. A few
cents and a couple of minutes for a seven-minute topic, against minutes of render time to discover
the same thing the expensive way. Pass `--target-duration-ms` for a shorter, cheaper run.

Flag it if all segments landed on one tier, or if any tier is empty — that means the budget is
mistuned and the tier system is doing nothing (D32).
