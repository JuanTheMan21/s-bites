---
name: pipeline-debugging
description: How to diagnose failures in the video pipeline — artifact layout, replaying a single segment, and the recurring failure modes with their causes. Load when a render fails, output looks wrong, or A/V is out of sync.
---

# Debugging the pipeline

## First rule: do not re-run the whole thing

A full 7-minute run is ~15 segments through LLM, TTS, authoring, and rendering. Re-running it to
observe a bug wastes minutes and credit. The graph checkpoints per segment — resume, or replay the
single failing segment.

Use `/tiers <topic>` to inspect outline and tier assignment for one LLM call and no rendering.

## Artifact layout

Every run writes under `artifacts/<job_id>/`, and each stage leaves its output on disk deliberately
so failures can be localized without instrumentation:

```
artifacts/<job_id>/
  outline.json          segments, intents, importance scores
  segments/<n>/
    script.json         narration text + slot payload
    narration.wav       TTS output
    scene.html          rendered composition
    frames/             tier 1/2 intermediates
    segment.mp4         self-contained clip, audio already muxed
  final.mp4
```

Localize before theorizing: find the last artifact that is correct, and the bug is in the stage that
produced the next one.

## Failure modes, in order of likelihood

**Audio and video drift.** Almost always a duration that did not come from measured audio. Check
that `scene.html` timing matches `ffprobe` on `narration.wav`:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 artifacts/<job>/segments/<n>/narration.wav
ffprobe -v error -show_entries format=duration -of csv=p=0 artifacts/<job>/segments/<n>/segment.mp4
```

These must agree within ~50ms. If they do, drift is not in this segment — check the concat step.
Because each segment is muxed independently before concatenation, drift cannot accumulate across
segments; if the final file drifts but every segment is clean, the bug is in the concat, not the
pipeline.

**A frozen Tier 2 render.** The animation is not seekable. HyperFrames steps frame by frame rather
than playing, so anything driven by `Date.now()`, `setInterval`, or un-seekable JS produces the
same frame repeatedly. Use CSS keyframes, WAAPI, or GSAP.

**Composition rejected.** Run `npx hyperframes lint <file>` directly for the real error. Usually a
missing `class="clip"`, a missing `data-track-index`, or seconds/milliseconds confusion.

**Structured output failures.** On Azure, strict mode requires every field `required` and
`additionalProperties: false` — a schema that violates this is rejected outright rather than
returning bad data. On Ollama, the constraint is softer and malformed output is possible; that
handling belongs in the adapter.

**Rate limiting.** 429s under fan-out mean `AZURE_OPENAI_MAX_CONCURRENCY` exceeds the deployment's
TPM. Lower it. An uncapped fan-out plus retry storm is slower in wall-clock time than a bounded one.

**Everything landed on one tier.** `FRAME_BUDGET` is mistuned. Too high promotes everything to
Tier 2; too low demotes everything to Tier 0. Check with `/tiers` before rendering.

**Blank screenshots.** Playwright captured before fonts or layout settled. Wait on a load state or
a specific element, not a fixed sleep.

## Isolating a stage

Because artifacts persist, any stage can be exercised against saved input from the one before it.
Prefer that to adding logging — the data is already on disk.

Run with `RUNTIME_ENV=local` to take Azure out of the picture entirely. If a bug reproduces on both
stacks it is in `core/`; if only on one, it is in that adapter — and that is also a parity finding
worth reporting.
