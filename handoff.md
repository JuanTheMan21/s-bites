# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-29 · after T18C (the broadened block library)_

---

## Where we are

**T18C shipped the block-library slice only** — six items (`GRAPH_DIAGRAM` retiring
`DIAGRAM_CHAIN`, generalized `ARRAY_GRID`, `CODE_DIFF`, `SEQUENCE_DIAGRAM`, `TIMELINE`, and a new
cross-cutting annotation overlay system) plus two related pre-existing gaps this session's own
research surfaced: a real caption/content-overlap bug, and D107's unreachable mixed-tier live
test. `tasks.md`'s original T18C entry also scoped a vision critique/revision loop and a full
7-minute validation render — both **deferred, not built**, to a new, not-yet-scoped **T18D**
(decisionlog D118). A user request mid-planning to "make video making faster" is deferred into
that same T18D, unscoped as of this checkpoint.

**The annotation overlay is the genuinely novel piece**, and this session's own Phase-0
real-toolchain spike (composing hand-built scenes and running the real `hyperframes check`
against them, not just reasoning about the design) found and fixed two real positioning bugs
before they'd have shipped silently — see D115. `project-reviewer`'s own final review-gate pass
then caught a third real bug, in the *test coverage* this session added: a `SHIFT`-op fixture that
looked correct and passed offline, but never actually exercised the branch it claimed to cover
(D114). All three are fixed and re-verified against the real toolchain.

**`DIAGRAM_CHAIN` is retired, not kept alongside `GRAPH_DIAGRAM`** (D113) — a breaking change,
matching T18B's own precedent of retiring superseded templates. `ArrayEliminationStep` is renamed
`ArrayStep` and generalized to four ops (D114), also breaking, also swept through every consumer
in the same pass.

**Still on `feature/scene-composition`.** Branched from `dev` at `5b4d7ba` (T18B's own start
point) — this task's work landed on the same branch, not a new one, since T18B's own work was
never merged back to `dev` (see "Before the next session" below — this was already true at T18B's
checkpoint and remains true now). `dev` itself is unchanged since before T18B.

**Done:** T1-T18, T18A, T18B, T18C.
**Next: not yet numbered.** The unscoped future work (vision critique/revision loop, full
7-minute validation render, "make video generation faster") needs its own scoping conversation
before it becomes a real `/build-task` session — see `tasks.md`'s T18C entry, now updated to
record what actually shipped and what got pushed to "T18D."

## What T18C produced (file-by-file detail lives in the diff and in `decisionlog.md` D113-D118)

**New:** `core/block_schemas_graph.py`, `core/block_schemas_array.py`, `core/block_schemas_diff.py`,
`core/block_schemas_sequence.py` (split out of `core/block_schemas.py` to stay under the 200-line
ceiling with every new block added), `rendering/block_timing.py` (per-block narration-anchor
resolution, split out of `rendering/compose.py`), `rendering/annotations.py` (annotation target
resolution + bounds-check), `rendering/templates/_block_graph_diagram.html`,
`_block_code_diff.html`, `_block_sequence_diagram.html`, `_block_timeline.html`,
`_annotations.html` (shared JS positioning helper), `_annotation_cursor.html`,
`_annotation_check.html`, `_annotation_warning.html`, `runtime_skills/scene-authoring/1.3.md`,
`runtime_skills/visual-plan/1.1.md`, `tests/test_array_grid_and_graph_modes.py`,
`tests/test_compose_annotations.py`.

**Retired:** `rendering/templates/_block_diagram_chain.html`, `BlockType.DIAGRAM_CHAIN`,
`DiagramNode`/`DiagramChainSlots` (`core/block_schemas.py`).

**Renamed/generalized:** `ArrayEliminationStep` → `ArrayStep` (`core/block_schemas_array.py`,
moved out of `core/block_schemas.py`), now with `op` (narrow/shift/push/pop) and `end_operation`;
`ArrayGridSlots` gains `orientation`.

**`core/scene_plan_schema.py`/`core/scene_schemas.py`**: new `PlannedAnnotation`/
`ComposedAnnotation`, `SegmentScenePlan.annotations`/`ComposedScene.annotations` — annotations are
a separate concept from `BlockType`, not registered the same way (see D115, and the new paragraph
in `.claude/skills/scene-templates/SKILL.md`).

**`rendering/templates/_layout_single.html`/`_layout_split_horizontal.html`**: `#stage`'s bottom
padding `130px` → `170px` (3-value shorthand) — a real, pre-existing 24px gap against the caption
band, not hypothetical (D116). Both also gained the annotation import/loop wiring.

**`tests/test_render_segment_live.py`**: `--caption-zone` now passed to the real `hyperframes
check` call — no new assertion needed, its findings fold into the `layout` category the test
already asserts on (confirmed empirically, D116).

**`tests/test_graph_pipeline_live.py`**: D107 closed — mixed-tier test retargeted from an
unreachable `{Tier.STATIC, Tier.ANIMATED}` to `{Tier.REVEAL, Tier.ANIMATED}`, `FRAME_BUDGET`
55 → 80 (D117).

## Verify at any time

```bash
pytest                                    # offline, no network -- 640 passed, 1 skipped as of this checkpoint
ruff check . && ruff format --check .     # clean (one pre-existing unrelated file,
                                           # .claude/skills/python-pro/SKILL.md, was already
                                           # unformatted before this session and untouched by it)
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # must be empty
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # must be empty
git branch --show-current                                                    # feature/scene-composition

PYTHONPATH=. .venv/Scripts/python.exe cli.py                  # prompts for a topic, runs standalone
```

**`pytest -m local_live` (the real-render `BlockType x Tier` sweep) was NOT run this checkpoint.**
The new block types were verified via standalone `hyperframes check --json` runs against
hand-composed scenes (real toolchain, real findings caught and fixed — D114, D115), but never
through the actual `render_segment`/`PlaywrightHyperFramesRenderBackend` path the `local_live`
suite exercises. Run this before trusting the new blocks in a real render, the same trust-gap
shape D110 already left open once (see below — that one is *still* open too).

**No real end-to-end `cli.py` render was watched this checkpoint either.** Same caveat as above,
compounded: two separate real-render verifications are now owed, not one.

## Environment state

| | |
|---|---|
| Models | Opus plans, Sonnet builds — confirmed correctly this task: the plan was approved on Opus, the user then explicitly ran `/model sonnet` (setting it as their default) before the build began, and the mandatory self-check confirmed Sonnet before the first `Write`. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100) — unchanged, still temporary until T35. |
| `FRAME_BUDGET` | `9500`, unchanged this task. |
| `RENDER_MAX_CONCURRENCY` | `2`, unchanged, still unmeasured under real concurrent load (carried forward). |
| Git | `feature/scene-composition`, branched from `dev` at `5b4d7ba`. Not yet pushed to `origin` this checkpoint — see the push offer below. `dev` unchanged. |
| Blob skill registry | **Not synced this checkpoint.** Two new/bumped packs exist only on local disk: `scene-authoring/1.3.md`, `visual-plan/1.1.md`. A real `RUNTIME_ENV=azure` run right now would load the *previous* versions from Blob (`scene-authoring/1.2`, `visual-plan/1.0`) — the same silent-drift gap D107 already found once for T18A's `1.1`. Still no automated sync exists. |
| Azure spend | No real Azure calls this session — all verification was offline `pytest` plus local `hyperframes check` runs (no LLM/TTS, no network cost). |

## Before the next session

**Three real things to do, none code-blocking but all trust-blocking, in the order they'd
naturally get checked:**

1. **D110's caption fix (from T18B) still has not been watched in a real render.** Carried
   forward unresolved for a second checkpoint now — this file said the same thing after T18B and
   nothing since has watched a real render to confirm captions actually read as movie-style rather
   than trusting the description.
2. **T18C's new blocks have not been through a real render either** — see "Verify at any time"
   above. `pytest -m local_live` first (fast, no cost), then a real `cli.py` topic that would
   plausibly reach for the new blocks (a protocol/handshake topic naturally invites
   `SEQUENCE_DIAGRAM`; an algorithm with a graph or tree naturally invites `GRAPH_DIAGRAM`'s
   `GRAPH` mode), watched via extracted frames the way D109 did for T18B.
3. **Merge `feature/scene-composition` back to `dev`** once the above two are done — still not
   automatic as part of any checkpoint, per the same standing note this file has carried since
   T18B.

## Known gaps and open questions

**New this checkpoint:**
- **The SPLIT_HORIZONTAL "same panel" annotation restriction is prompt-only** — `rendering/
  annotations.py::resolve_annotations` bounds-checks `target_block_index` against the segment's
  own block count, but nothing in code stops an annotation from naming a block in the *other*
  panel. Confirmed not exploitable into a broken frame (the render container is always derived
  from the target itself), so left as a narrative constraint rather than a redundant guard — but
  worth knowing if a future session is debugging an annotation that reads as "attached to the
  wrong panel" conceptually rather than visually broken.
- **T18D is a real name collision, now resolved by convention, not yet by content.** `tasks.md`'s
  T18C entry named "T18D" as a placeholder for "push LLM compositionality further, testing the
  limits" — this checkpoint folds the vision-loop/validation-render/performance work into that
  same name rather than renaming either. Whichever session next scopes T18D should treat all of
  this as one basket to sort through, not assume any part of it is already decided.
- **`ArrayStep.op`'s cross-field consistency (does `remaining_start`/`remaining_end` actually match
  what `op` claims — a `narrow` that grows, a `shift` that changes width) is prose-only, not
  validator-enforced** — the same convention the pre-T18C "range only ever shrinks" constraint
  already used, deliberately not reopened (D114). A real render is what would actually catch a
  violation, not `pytest`.

**Carried forward, unchanged from prior checkpoints:**
- The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open (D24/D67).
- No coverage gate exists (D42).
- `Segment.scene` is still untyped by design (D29's pattern) — revisit at T24 as previously
  planned.
- `RENDER_MAX_CONCURRENCY=2` still hasn't been measured under real concurrent load.
- T10 stays `in-progress`, unclaimed. Ollama/Kokoro still don't exist.
- D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only — still open.
- `hyperframes check` is still non-deterministically flaky at times (D96) — re-run before
  trusting a single red result. Not hit this session (every real-toolchain probe this checkpoint
  came back consistent across re-runs), but the standing caveat remains.

## Gotchas worth remembering

**New this session, from T18C's own Phase-0 spike and the final review pass:**
- **`getBoundingClientRect()` returns viewport pixels, not this project's own 1920x1080 CSS-pixel
  space, whenever the capture harness renders at a different effective scale.** A real, found-live
  bug (`hyperframes check`'s own `escaped_container` finding caught it) — any future code
  measuring a real element's position for use inside a GSAP `x`/`y` transform must normalize
  against `#root`'s own known width first (`rendering/templates/_annotations.html`'s
  `hfAnnotationOffset` is the reference implementation).
- **A `position: absolute` element with no explicit `top`/`left` set does NOT default to its
  container's origin** — it defaults to wherever it would have landed in normal document flow
  (its "hypothetical box"), which for a flex child can be far from (0,0). Any element meant to be
  positioned purely via a GSAP `x`/`y` transform needs an explicit `top: 0; left: 0` in its base
  CSS, or the transform composes with an unpredictable starting point instead of a clean origin.
- **A test that passes offline does not mean the code path it claims to cover actually ran.**
  `tests/test_array_grid_and_graph_modes.py`'s first version validated a `shift` fixture against
  the schema and confirmed the string `"shift"` appeared in composed HTML — both true, and neither
  proved the template's `enter()` branch (the animation logic `shift` exists to add, distinct from
  `narrow`) ever actually executed. Caught only by a reviewer tracing the *template's own runtime
  logic* against the fixture's specific numbers, not by running the test. When a test's whole
  purpose is covering one specific branch, trace the branch condition by hand against the fixture,
  don't just confirm the test passes.
- **`hyperframes check --caption-zone`'s findings fold into the existing `layout` category, under
  no separate top-level JSON key** — confirmed by real `--json` runs, not assumed. Any future
  caption-zone-adjacent work should assert against `check["layout"]["errorCount"]`, not invent a
  `check["captionZone"]` key that doesn't exist.
- **A block whose payload has no length floor can produce an empty list a template's script macro
  then indexes into.** `_block_code_diff.html`'s caption-timing tween originally read
  `{{ prefix }}_lineStarts[{{ prefix }}_lineStarts.length - 1]` — `NaN` for a zero-line diff.
  Fixed by tracking a plain running scalar instead (matching `_block_code_panel.html`'s own
  pre-existing pattern) — worth checking any new block's script macro for the same class of
  off-the-end read wherever it indexes a per-item array by its own length.

**Carried from T18B, still true:**
- **A movie-style caption fix has two separate parts** — *retention* (does an old cue clear) and
  *reveal* (does a cue appear as one unit). Still unwatched in a real render (see "Before the next
  session").
- **A CSS initial `transform` paired with a GSAP tween on the same property is a real, currently-
  live trap.** Set every animated element's *starting* transform state via an unconditional
  `tl.set(...)` at t=0 in JS, never in static CSS.
- **A block partial's `markup()` and `script()` macros must declare the exact same parameters**,
  even ones only one of them uses — Jinja does not warn on a silently-unbound keyword argument.
- **Two Jinja templates composing into one page can collide on element ids** — check *other*
  templates' existing id suffixes when adding a new one, not just your own file.
- **The Blob skill registry does not auto-sync with local disk, ever** — confirmed drifted twice
  now (T18A once, and this checkpoint leaves it drifted again on purpose, see above). Any session
  doing a real `RUNTIME_ENV=azure` run after editing `runtime_skills/` should sync manually first.

**Carried from T18A, still true:**
- **The quality hook strips an import added before its first use** — even across separate
  Edit/Write calls in the same session. Add the import in the identical tool call that adds its
  first real usage. Bit this task multiple times (`tests/test_block_schemas.py`,
  `core/graph/nodes/visual_plan.py`, and a scratchpad probe script all needed a follow-up edit to
  re-add a stripped import) — a live, recurring trap, not a one-off.
- **A registry component's `<template>`/`window.__hyperframes` runtime doesn't fit this project's
  layout — port the technique, not the file.** Confirmed again this task for `offset-path-traveler`
  (`graph_diagram`'s traveler), `code-diff`, `success-check`, and the cursor/press-ripple
  components — every one hand-ported, none installed as-is.
- **`hyperframes lint`'s severity levels are meaningful** — only `[error]` blocks a render.
- **Windows path semantics**: a trailing dot is stripped on existence checks but not on directory
  enumeration (D46).
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress — this task split
  `core/block_schemas.py` into five modules and `rendering/compose.py` into three for exactly this
  reason.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
