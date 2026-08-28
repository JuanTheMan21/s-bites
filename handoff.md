# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-29 · after T18B_

---

## Where we are

**T18B replaced the whole enum-picks-template rendering mechanism with a compositional one**, on
the user's explicit instruction after reviewing T18A's real output a second time: the six
`VisualIntent`-keyed whole templates are gone, replaced by two `SceneLayout`s
(`SINGLE`/`SPLIT_HORIZONTAL`) composing six `BlockType` partials, planned once per video by a new
`plan_visuals` join node (`core/graph/nodes/visual_plan.py`) rather than authored per-segment in
isolation. Full reasoning and every decision this reopens/leaves alone: `decisionlog.md` D105.

**The real structural finding this session**: the "8 of 15 segments were `diagram_flow`"
repetition D95 recorded was never a template-quality problem -- `author_scene` ran inside a
`Send` fan-out, so no segment's visual ever knew what any other segment looked like. `plan_visuals`
is the first thing in this pipeline positioned to prevent that rather than only observe it after
the fact.

**Four real bugs were found only by running the real toolchain** (not by `pytest`/`ruff`, both of
which stayed clean throughout) -- a captions macro that rendered no visible text and collided ids
across cues, a split-layout choreography flag that silently never reached its macro, an id
collision between the split layout's own wrapper and `code_panel`'s internal one (found by a real
`hyperframes check` warning during this session's own benchmark spike), and a static-CSS/GSAP
transform conflict in the one genuinely new template (`array_grid`) that produced real
`text_occluded` errors. All four fixed and verified; full detail in `decisionlog.md` D106.

**Two pre-existing gaps were found and are carried forward, not fixed here** (D107): the Blob
skill registry had silently drifted from local disk since T18A (`scene-authoring/1.1.md` was
never uploaded -- fixed as a one-off manual sync this session, no automated sync exists yet), and
`tests/test_graph_pipeline_live.py`'s mixed-tier test is mathematically unsatisfiable under the
current tier ladder (a T18A/D99-era gap, not a T18B regression -- `core/tier_resolver.py` has
zero diff this task).

**Real end-to-end render verified and watched** (D109): `cli.py "how binary search works"`, 90s
target, `RUNTIME_ENV=azure`+`RENDER_ENV=local`. 3 segments, all `Tier.ANIMATED`, 140.8s
wall-clock. Frames extracted and inspected directly: a genuinely distinct Blueprint motif (light
paper, orange accent -- the real fix for D95's "still reads navy blue"), a working `diagram_chain`
rail, a working `SPLIT_HORIZONTAL` comparison with both panels rendering correctly, captions
clearing and replacing across cues. `array_grid`/`stat_callout` and a second motif were not
exercised in *this specific run* (the plan didn't choose them for this topic/length) but both are
independently verified: `array_grid` via `hyperframes check` (see D106 item 4) and the full
18-combo `test_render_segment_live.py` sweep (every block type, every tier, all green).

**Still on `dev`'s successor branch.** `master` was fast-forwarded to `dev`'s HEAD (`5b4d7ba`)
and pushed *before* this task started, per the plan's own recommendation, to bank a known-good
rollback point ahead of an invasive rework. This task's work is on `feature/scene-composition`,
branched from `dev` at that same point. **Not yet merged back to `dev`** -- do that once this
checkpoint's review gate passes.

**Done:** T1-T18, T18A, T18B.
**Next: T18C** — the broadened primitive library (array/stack/queue generalisation, arbitrary
graph topology + traversal highlight, sequence/lane diagrams, timelines, code diff, annotation
components including a generalised "warning" motif) plus the vision critique/revision loop this
session's own harness-tightening answer named as the next real lever. See `tasks.md`'s T18C entry
for the full scope T18B's plan already reasoned out. **A possible T18D** (pushing LLM
compositionality further, "testing the limits" per the user's own framing) is named in `tasks.md`
but not scoped — that conversation has not happened yet.

## What T18B produced (file-by-file detail lives in the diff and in `decisionlog.md` D105-D109)

**New:** `core/block_types.py`, `core/scene_plan_schema.py`, `core/scene_schemas.py`,
`core/block_schemas.py` (renamed from `core/slot_schemas.py`), `core/graph/nodes/visual_plan.py`,
`rendering/anchors.py`, `mux/caption_cues.py`, `rendering/templates/_layout_single.html`,
`_layout_split_horizontal.html`, `_block_{title,text_panel,stat_callout,code_panel,
diagram_chain,array_grid}.html`, `runtime_skills/visual-plan/1.0.md`,
`runtime_skills/scene-authoring/1.2.md`, `tests/block_examples.py` (renamed from
`tests/slot_examples.py`), `tests/scene_author_fixtures.py`, `tests/test_author_scene_node.py`,
`tests/test_block_schemas.py` (renamed from `tests/test_slot_schemas.py`).

**Retired:** the six old whole-scene templates (`title_card.html`, `bullet_list.html`,
`comparison.html`, `diagram_flow.html`, `code_walkthrough.html`, `stat_callout.html`),
`core/slot_schemas.py`, `tests/slot_examples.py`, `tests/test_slot_schemas.py`.

**Motif system**: folded into `plan_visuals`' single call (`VideoScenePlan.motif`) rather than a
separate node -- simpler than the originally-scoped design, since one video only ever needs one
motif decided once, at the same time everything else about the video's visuals is decided.

**`core/models.py`**: `Segment.slots` renamed to `Segment.scene`; no new fields, no line-count
pressure (still comfortably under 200).

## Verify at any time

```bash
pytest                                    # offline, no network -- 562 passed, 1 skipped as of this checkpoint
pytest -m local_live                      # opt-in, real browser/CLI/ffmpeg -- 18-combo block x tier sweep green
pytest -m live                            # opt-in, real Azure -- not re-run this checkpoint (unchanged surface)
ruff check . && ruff format --check .     # clean as of this checkpoint
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # must be empty
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # must be empty
git branch --show-current                                                    # feature/scene-composition

PYTHONPATH=. .venv/Scripts/python.exe cli.py                  # prompts for a topic, runs standalone
PYTHONPATH=. .venv/Scripts/python.exe scripts/measure_render_throughput.py  # Phase 0's benchmark, reusable
```

## Environment state

| | |
|---|---|
| Models | Opus plans. **This build ran on Sonnet throughout, confirmed at session start** -- unlike T18A, which ran entirely on Opus because the harness was pinned before the switch could happen. Confirm again before T18C's build starts. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100) -- unchanged, still temporary until T35. |
| `FRAME_BUDGET` | `9500`, **unchanged** -- Phase 0's composite-scene measurement (~13% slower than the old single-block baseline, D108) stayed under the threshold that would have required a change. |
| `RENDER_MAX_CONCURRENCY` | `2`, unchanged this task. |
| Git | `feature/scene-composition`, branched from `dev` at `5b4d7ba`. `master` fast-forwarded to `5b4d7ba` and pushed *before* this task's work began (banked rollback point). `dev` itself unchanged until this branch merges back. |
| Blob skill registry | **Now synced with local disk** (D107) -- all five packs (`house-style`, `outline`, `scene-authoring` at `1.2`, `scripting`, `visual-plan`) uploaded manually this session. No automated sync exists; a future task should build one, or this will silently drift again exactly the way it already did once. |
| Azure spend | One real render this session (~90s/3 segments, ~140.8s wall-clock) plus the Phase 0 benchmark spikes (render-only, no LLM/TTS). Not itemized by any tooling in this repo, same standing gap as every prior checkpoint. |

## Before the next session

**Nothing code-blocking.** Read this file, then `tasks.md`'s T18C entry, then `decisionlog.md`
D105-D109, then plan mode as usual.

**Merge `feature/scene-composition` back to `dev` once this checkpoint's review gate passes** --
not done automatically as part of `/checkpoint`, since the user should see the review outcome
first.

## Known gaps and open questions

**Carried into T18C, already scoped (see `tasks.md`):** the broadened primitive library, the
vision critique/revision loop (needs a real `LLMProvider` interface change for image input --
`interfaces/llm_provider.py` stays text-only until then, with real adapter-parity work across
both Azure and local, D40's `inspect.signature` equality included), a full 7-minute validation
render across genuinely varied topic types.

**Still genuinely open, not yet scoped as any numbered task:**
- **`tests/test_graph_pipeline_live.py`'s mixed-tier test is currently unsatisfiable** (D107) --
  needs either a third segment or a different importance pairing to produce a real
  `{STATIC, ANIMATED}` split under the post-D99 ladder; a single constant tweak cannot fix it
  (worked out by hand in D107, the arithmetic doesn't close).
- **No automated Blob skill-pack sync exists** (D107) -- this drifted silently for an entire task
  once already (T18A's `scene-authoring/1.1.md` was never uploaded) and will again.
- **T18D** ("test the limits" of LLM compositionality, per the user's own framing) is named as a
  possible future task in `tasks.md` but has had no scoping conversation. Not started, not
  promised, explicitly a later decision.
- **The document-upload / cursor-navigated-UI-walkthrough direction** the user asked about
  directly this session: confirmed *not* blocked by anything T18B built (a future `UI_WALKTHROUGH`
  block type slots into the same `BlockType`/schema/partial pattern), and confirmed as the
  best-supported of everything this session researched in HyperFrames' own registry
  (`browser-device-stage`, `simulated-cursor`, `ui-focus-zoom` all already take data-driven
  coordinates/timing) -- waiting only on a document-ingestion path that does not exist yet
  (that's T29's scope, iteration 6, scheduled last per the original requirement).

**Carried forward, unchanged from prior checkpoints:**
- The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open (D24/D67).
- No coverage gate exists (D42).
- `Segment.slots` is now `Segment.scene`, still untyped by design (D29's pattern) -- revisit at
  T24 as previously planned.
- `RENDER_MAX_CONCURRENCY=2` still hasn't been measured under real concurrent load, only chosen
  from one machine's `hyperframes doctor` output.
- T10 stays `in-progress`, unclaimed. Ollama/Kokoro still don't exist.
- D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only -- still open.
- `hyperframes check` is still non-deterministically flaky at times (D96) -- re-run before
  trusting a single red result. Not hit this session, but the standing caveat remains.

## Gotchas worth remembering

**New this session:**
- **A CSS initial `transform` paired with a GSAP tween on the same property is a real, currently-
  live trap** (`_tokens.html`'s own docstring already named it; `array_grid`'s strike-through
  reintroduced it once, D106 item 4). Set every animated element's *starting* transform state via
  an unconditional `tl.set(...)` at t=0 in JS, covering every instance regardless of whether a
  later tween ever actually targets it -- never in static CSS.
- **A block partial's `markup()` and `script()` macros must declare the exact same parameters**,
  even ones only one of them uses (T18B's `compact` bug, D106 item 2) -- Jinja does not warn on a
  silently-unbound keyword argument the way a real function signature mismatch would.
- **Two Jinja templates composing into one page can collide on element ids in ways neither
  template alone reveals** (D106 item 3) -- a layout's own wrapper id and a block's internal id
  both reaching for the same short, obvious suffix (`-panel`) is a real, found-live risk once
  blocks and layouts are authored by different people at different times, not a hypothetical.
- **`hyperframes benchmark`'s default sweep covers both 30fps and 60fps** -- a `--runs N` budget
  applies to *both*, so a timeout tuned for one config's worth of runs will read as a hang. Not a
  bug, just an easy trap for a fresh timeout estimate (D108).
- **The Blob skill registry does not auto-sync with local disk, ever** -- confirmed this drifted
  silently for a full task (D107). Any session doing a real `RUNTIME_ENV=azure` run after editing
  `runtime_skills/` should sync manually first, or expect `SkillPackNotFound` or a stale pack.

**Carried from T18A, still true:**
- **The quality hook strips an import added before its first use** -- even across separate
  Edit/Write calls in the same session. Add the import in the identical tool call that adds its
  first real usage; bit this task in at least a dozen files across the rename/rewrite.
- **A wrong measurement, once written into a constant, propagates unquestioned across sessions
  until someone re-derives it from first principles** (D16 -> D99, and now the ~17fps single-block
  figure this session correctly treated as "still true for its original case, not the whole
  story" rather than silently overwriting -- both numbers are recorded, per-scenario).
- **A registry component's `<template>`/`window.__hyperframes` runtime doesn't fit this project's
  layout -- port the technique, not the file.** Directly relevant again to T18C's block library.
- **`hyperframes lint`'s severity levels are meaningful** -- only `[error]` blocks a render.
- **Windows path semantics**: a trailing dot is stripped on existence checks but not on directory
  enumeration (D46).
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
