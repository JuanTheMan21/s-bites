# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-09-02 · after T18G ran to completion (F1-F7 plus a new ICON_PANEL block), one
real ~7-minute validation render found and fixed three more bugs, `project-reviewer`'s close-out
pass found a fourth (fixed and re-verified), the branch was merged to `dev` and pushed, and a
second showcase render (topic: Git internals) surfaced two new, real, not-yet-fixed findings_

---

## Where we are

**T18G is done.** Full scope, reasoning, and the two explicit user scope choices (both of D121's
deferred analysis items pulled forward; `ICON_PANEL` scoped to abstract/generated graphics, not
real photo/logo sourcing): decisionlog **D123**. Summary of what shipped, by area:

- **F1 (the headline fix)** — `graph_diagram.nodes`, `text_panel.items`, `code_diff.lines` each
  gained an authored `anchor_phrase` (new `TextPanelItem` in `core/block_schemas.py`,
  `core/block_schemas_graph.py`, `core/block_schemas_diff.py`); `rendering/block_timing.py
  ::resolve_item_starts` now resolves it exactly the way `resolve_step_starts` always has (one
  shared `_resolve_anchor_phrases` helper) — the D119 fix, finally extended past
  `sequence_diagram`/`timeline` to the three types T18E's E1 left out. `rendering/anchors.py
  ::derive_item_anchors` (the old display-text-matching path) is gone.
- **F2** — `_block_graph_diagram.html`'s circular/row-packed fallback replaced by a real
  layered/rank-based layout (`computeLayeredLayout`: DFS cycle-breaking, longest-path ranking,
  two-pass barycenter cross-axis ordering) — the full build of D121's analysis item 7.
- **F3** — `TitleSlots` gained `key_terms` (0-4, each its own `anchor_phrase`); `_block_title.html`
  stages them across the segment's real duration plus one continuous ambient tween, closing
  D120's "structural title card" finding.
- **F4** — `_annotations.html::hfAnnotationPlace` gained a shared per-container collision registry
  and a vertical nudge-search, closing D122 finding 1. `_block_graph_diagram.html` registers its
  own edge-label boxes into the same registry.
- **F5** — `core/block_triggers.py::_looks_chronological`, a regex-based version-number detector,
  closes D122 finding 2 (the "HTTP 1.0...HTTP/3..." blind spot).
- **F6** — `runtime_skills/annotation-authoring/1.1.md`: concrete CURSOR/CHECK/WARNING
  right/wrong examples.
- **F7** — `_block_sequence_diagram.html` and vertical `_block_array_grid.html` shrink their own
  row/cell height to fit a computed max, with a floor (added at review), instead of growing into
  the caption band.
- **New block: `ICON_PANEL`** — 16 hand-authored inline-SVG icons (`core/block_types.py
  ::IconName`), built end to end via `/newblock`'s checklist (`core/block_schemas_icon.py`,
  `rendering/templates/_block_icon_panel.html`, `runtime_skills/visual-plan/1.3.md`).

**Two real `RUNTIME_ENV=azure` ~7-minute renders this session, both watched frame by frame, not
sampled:**
1. `t18g-validation-render` ("how HTTPS keeps your connection private") — F9's own closing
   verification. Found and fixed three more bugs live: bottom-rank `GRAPH_DIAGRAM` node captions
   reaching the caption band (coordinate-mapping fix), `marker-end` arrowheads rendering at their
   destination before the line/node itself appeared (opacity-gate fix, both CHAIN and GRAPH mode),
   and single-candidate annotation placements (CURSOR's own `["tip"]`) never actually benefiting
   from collision avoidance (nudge-search fix). Full account: D123.
2. `t18g-showcase-git` ("how Git commits, branches, and merges work") — run after `/checkpoint`
   started, at the user's own request to showcase this session's work. Confirmed F3/F4/F7 all
   working well on fresh content (title chips, a clean SEQUENCE_DIAGRAM with two non-colliding
   annotations, a clean STAT_CALLOUT). **Also found two new, real, not-yet-fixed issues** — see
   "Known gaps" below; not fixed this session, this checkpoint's own render came after the
   review gate had already passed.

**`project-reviewer` ran twice** — once mid-build against the working diff (found the shrink-to-fit
height floor gap, fixed), once against the final committed commit `4f10ae7` (clean). Both accounts
in D123.

**Merged and pushed.** `feature/scene-composition` (11 commits ahead of `dev`, including the
previously-unpushed T18D/T18E commit from a prior session) was pushed to `origin`, then fast-forward
merged into `dev` (`dev` had not diverged since the branch point, so this was a clean
fast-forward, no conflicts) and `dev` pushed too. Both branches now sit at `4f10ae7`. **Still on
`feature/scene-composition`** as the active branch — matches this project's own established
pattern (every prior T18-series checkpoint commit landed there first, `dev` only fast-forwards at
merge points); keep committing there, merge to `dev` again at the next checkpoint.

**Done:** T1-T18, T18A-T18G.
**Next:** T18F ("vision critique/revision loop, full validation render, rendering/pipeline speed")
is the next placeholder in sequence — its own validation-render item is now informed by (not
closed by) T18G's two real renders, per the note added to its `tasks.md` entry. But the two new
findings from `t18g-showcase-git` (below) are real, freshly-discovered, un-scoped work competing
for the same slot — worth a conversation with the user before assuming T18F is next by default,
same standing advice this file has carried every checkpoint since T18C.

## What T18G produced

**New:** `core/block_schemas_icon.py`, `rendering/templates/_block_icon_panel.html`,
`runtime_skills/annotation-authoring/1.1.md`, `runtime_skills/scene-authoring/1.5.md`,
`runtime_skills/visual-plan/1.3.md`, `tests/block_examples_extra.py`,
`tests/test_graph_diagram_layout_live.py`, `tests/test_item_anchor_resolution.py`.

**Modified:** `core/block_items.py`, `core/block_schemas.py`, `core/block_schemas_diff.py`,
`core/block_schemas_graph.py`, `core/block_triggers.py`, `core/block_types.py`,
`rendering/anchors.py`, `rendering/annotations.py`, `rendering/block_timing.py`,
`rendering/templates/_annotations.html`, `rendering/templates/_block_array_grid.html`,
`rendering/templates/_block_graph_diagram.html`, `rendering/templates/_block_sequence_diagram.html`,
`rendering/templates/_block_text_panel.html`, `rendering/templates/_block_title.html`, plus the
test files these changes touched (`tests/block_examples.py`, `tests/graph_pipeline_fixtures.py`,
`tests/test_block_triggers.py`, `tests/test_graph_diagram_edges.py`, `tests/test_runtime_skills.py`).

**Real render artifacts** (gitignored, not committed): `artifacts/_cli_run/t18g-validation-render/`,
`artifacts/_cli_run/t18g-showcase-git/`, plus the scratch verification renders under this session's
temp scratchpad (not in the repo at all).

## Verify at any time

```bash
pytest                                    # offline, no network -- 653 passed, 1 skipped
ruff check . && ruff format --check .     # clean except one pre-existing, unrelated drift
                                           # (.claude/skills/python-pro/SKILL.md, carried forward
                                           # since T18E, still not this task's)
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # empty (one
                                           # docstring-text hit in node_timing.py, not a real import)
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # empty
git branch --show-current                                                    # feature/scene-composition
git log -1 --format="%H"                                                     # 4f10ae7, == dev

PYTHONPATH=. .venv/Scripts/python.exe cli.py                  # prompts for a topic, runs standalone
```

## Environment state

| | |
|---|---|
| Models | Session ended pinned to Sonnet (the user's own explicit `/model sonnet` right after this session's own planning phase, which ran on Opus per the standing `build-task` convention). **Check the model banner before the next session's build phase regardless** — same standing mandatory self-check `CLAUDE.md` requires every time. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100) — unchanged, still temporary until T35. |
| `FRAME_BUDGET` | `9500`, unchanged. Still not retuned. |
| `RENDER_MAX_CONCURRENCY` | `2`, unchanged, still unmeasured under real concurrent load. |
| `AZURE_OPENAI_MAX_CONCURRENCY` | `4`, unchanged. |
| Git | `feature/scene-composition` and `dev` both at `4f10ae7`, both pushed to `origin`. `master` untouched — not part of this project's merge target, no evidence it should be. |
| Blob skill registry | **Synced this session** — `scene-authoring/1.5.md`, `visual-plan/1.3.md`, `annotation-authoring/1.1.md` uploaded via `az storage blob upload` (verified via `az storage blob list`). **Gotcha, worth reading before trying this again:** `source .env` in bash corrupts `AZURE_STORAGE_CONNECTION_STRING` (the file has CRLF line endings; bash `source` leaves a trailing `\r` on the last field of each line, which broke Azure CLI's connection-string parser with "missing required connection details"). Use Python's `dotenv.dotenv_values('.env')` to read it instead, never `source`/`set -a && source .env`. |
| Azure spend | Two real full-length `RUNTIME_ENV=azure` renders this session (~13 min and ~9 min wall-clock, ~$0.095 and ~$0.087 TTS each), plus several short scratch/live-test renders. Trivial against the $200/30-day credit. No render-backend Azure cost (`RENDER_ENV=local`). |

## Before the next session

1. **Decide what's next.** T18F is the next placeholder, but the two new findings below
   (both from watching `t18g-showcase-git`, found after this checkpoint's own review gate had
   already passed, so deliberately not fixed mid-checkpoint) are real, currently-unscoped work
   competing for the same slot.
2. Nothing environment-side is outstanding — Blob registry synced, both branches pushed and in
   sync with `origin`.

## Known gaps and open questions

**New this checkpoint, both found by watching `t18g-showcase-git`, neither fixed (found after the
checkpoint's own review gate had passed):**
- **`GRAPH_DIAGRAM`'s layered layout doesn't account for a node's own rendered size when spacing
  same-rank nodes in a compact canvas.** A real render (`t18g-showcase-git` segment 2,
  `n1->n2, n2->n3, n1->n4, n1->n5` in a `SPLIT_HORIZONTAL` compact canvas, verified directly
  against the composed HTML — `payload.positions` is empty, so this is NOT an authored-vs-fallback
  mixing issue, that was this session's own first, wrong guess before checking) showed `n2`/`n4`/
  `n5` (all rank 1, since all three are direct children of `n1`, and no other edges touch them)
  rendering with visually overlapping labels. Root cause: `computeLayeredLayout`'s coordinate
  mapping spreads a rank's N members evenly across the *cross-axis fraction range* (correctly
  giving each a mathematically distinct center point), but never checks whether that fraction
  spacing, multiplied by the compact canvas's actual short pixel height (220px real / 400 viewBox
  units), leaves enough room for each node's own marker+label+caption stack (which alone can be
  60-90px tall) to not visually collide with its neighbors. Three or more same-rank nodes in a
  compact canvas is the concrete failure case; two or fewer per rank hasn't shown this. A real fix
  needs the coordinate mapping to reserve a minimum per-node cross-axis pixel budget (derived from
  compact vs. non-compact node dimensions, already known constants in the same template) and
  either compress the overall spread or promote some same-rank nodes to an adjacent rank when a
  compact canvas can't fit them at the naive even spacing — a real algorithmic extension, not a
  one-line fix.
- **`visual-plan`'s "no block type as primary of more than a third of segments" rule did not hold**
  for a topic that is genuinely graph-shaped throughout: `GRAPH_DIAGRAM` was the/a primary block in
  roughly 12 of `t18g-showcase-git`'s 15 segments. This may be a real gap in how that rule is
  enforced (guidance-only, per D121's own finding about `visual-plan`'s existing limits) or it may
  be a legitimately hard case (a topic where one structural shape dominates the whole subject) —
  worth checking against `plan_visuals`'s actual reasoning/output for this job before assuming it's
  a bug rather than a defensible choice for this specific topic.

**Carried forward from T18E's own checkpoint, still true:**
- Two annotations targeting nearby items in the same block **no longer collide** (F4 fixed this,
  confirmed live) — this line is kept only so a future reader doesn't wonder why it's missing;
  D122 finding 1 is closed.
- E4's version-number chronology blind spot **is now fixed** (F5) — D122 finding 2 is closed.
- The dense-scene E2.4/E3/E1 interaction (edge labels/captions/annotations colliding) **is
  addressed** by F4's shared collision registry — D122 finding 3 is substantially closed, though
  not exhaustively re-tested against every possible combination.

**Carried forward, unchanged from prior checkpoints:**
- CURSOR's `"tip"` position targets a `GRAPH_DIAGRAM` node's whole div (marker+label+caption
  stack), so on a captioned node it can land on the label text rather than the marker circle — a
  narrower, distinct issue from the collision-avoidance bug F4 fixed. Needs
  `_ANNOTATION_TARGET_SUFFIX` to vary by annotation type as well as block type. D123 has the full
  account.
- The shrink-to-fit height floor (F7 + review fix) stops a single row/cell from collapsing, but
  total content height can still exceed the caption-band budget once item count is far enough past
  the advisory schema range that `floor * count` alone exceeds it. Narrow exposure, not chased
  further — see D123.
- The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open (D24/D67).
- No coverage gate exists (D42).
- `Segment.scene` is still untyped by design (D29's pattern) — revisit at T24 as previously
  planned.
- D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only — still open.
- T10 stays `in-progress`, unclaimed. Ollama/Kokoro still don't exist.
- `hyperframes check` is still non-deterministically flaky at times (D96) — re-run before
  trusting a single red result. Not hit this session.
- `pipeline-debugging`'s documented artifact layout is stale (no `script.json`/`scene.html`; the
  real layout is `segments/<n>/composition/index.html` + `clip.mp4` + `narration.wav` +
  `silent.mp4`) — flagged by T18D, still not fixed.
- A real photo/logo image-sourcing pipeline (new `interfaces/`+adapter pair) and the general
  payload-driven block-*variants* system (D121's analysis item 8 proper) both remain deliberately
  out of scope — the user's own choice at T18G's planning time, not silently dropped.

## Gotchas worth remembering

**New this session:**
- **`source .env` in bash corrupts a connection-string value if the file has CRLF line endings** —
  the trailing `\r` from each line's own terminator sticks to the last field, breaking strict
  parsers (Azure CLI's connection-string parser specifically). Use `dotenv.dotenv_values()` from
  Python instead of shell-sourcing `.env` whenever a value needs to reach a subprocess exactly.
- **Passing `run_in_background: true` to the Bash tool AND also appending your own `&` inside the
  command is a real footgun** — the tool's own tracking only sees the trivial wrapper (e.g. an
  `echo`) finish instantly, reports "completed," and the actual long-running process becomes
  effectively untracked (though still running, detached). Use `run_in_background: true` alone, with
  no manual `&`, for a single long command; if you need to attach a *separate* wait/watch on an
  already-detached process, `kill -0 <pid>` in an `until` loop (itself passed to
  `run_in_background: true`, no double `&`) works as a one-shot completion notifier.
- **An SVG `marker-end` arrowhead is not hidden by `stroke-dasharray`/`stroke-dashoffset`** — the
  marker renders at the path's endpoint geometry regardless of how much of the stroke's dash
  pattern is "drawn." Any edge/line reveal technique built on stroke-dashoffset needs its own
  separate opacity gate if it also carries a marker, or the arrowhead shows before the line (and
  before whatever it points at) has actually appeared.
- **A collision-avoidance fallback that "accepts the first in-bounds candidate when nothing is
  fully clear" silently defeats itself for any caller with only one candidate** — there is no
  second option to fall through to, so Pass 1 fails once and Pass 2 immediately re-accepts the
  same colliding position. A nudge-search (try small offsets around each candidate before moving
  to the next) is the fix, not a smarter "which candidate" pass — the candidate that's problematic
  needs to move, not be swapped for a different one that doesn't exist.
- **A layout algorithm scoped to "only place nodes lacking an authored position" needs to actually
  account for where the authored ones ARE, not just skip touching them** — omitting authored nodes
  from the algorithm's own bookkeeping (ranks, occupied space) means a fallback-placed node can
  land exactly on top of one. Confirmed live this session (see Known gaps above); the bounded-scope
  version shipped works well when a graph is entirely fallback or entirely authored, not reliably
  when the two are mixed in one diagram.

**Carried from T18D/E, still true:**
- **A GRAPH_DIAGRAM node div's CSS center is not its visible marker circle's center** — fixed for
  edges/traversal (T18E), still true of the div itself.
- **`[await x() for i in xs]` inside a list comprehension is sequential, not concurrent.**
- **The Azure adapter's own `asyncio.Semaphore(max_concurrency)` already makes concurrent calls
  from any caller safe.**
- **`mcp__azure__storage`'s AAD-login path can't write blobs on this account; use `az storage blob
  upload` with the connection string instead** (now via `dotenv_values`, not `source`, per above).
- **Python's logging module drops `INFO` and below by default until something calls
  `logging.basicConfig`.** `cli.py::main()` already does this; nothing else should need to.
- **A Jinja `loop.index0` inside one `{% for %}` block and a JS counter incremented only under a
  condition are NOT the same index** — always use the same index both places.
- **`hfAnnotationOffset`/`hfAnnotationPlace`'s scale-cancellation trick works for any ratio
  computation, not just absolute-pixel deltas.**

**Carried from T18C, still true:**
- **`getBoundingClientRect()` returns viewport pixels, not this project's own 1920x1080 CSS-pixel
  space** whenever the capture harness renders at a different effective scale.
- **A `position: absolute` element with no explicit `top`/`left` does NOT default to its
  container's origin.**
- **A test that passes offline does not mean the code path it claims to cover actually ran.**
- **The Blob skill registry does not auto-sync with local disk, ever** — confirmed drifted a fifth
  time now (T18A, T18B, T18D, T18E, and this task started with three packs missing too).

**Carried from T18A/T18B, still true:**
- **The quality hook strips an import added before its first use** — add the import in the same
  tool call as its first real usage. Hit again this session (`core/block_schemas_icon.py`'s
  import into `core/block_schemas.py`).
- **`hyperframes lint`'s severity levels are meaningful** — only `[error]` blocks a render.
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
