# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

_Last updated: 2026-09-05 · T18J (five concrete defects the user reported with screenshots/
timestamps against a real rendered video, plus the frontend's first live run) — substantial
progress, not closed · `project-reviewer` run twice, all findings fixed · about to be pushed_

---

## Where we are

**T18I closed out D149-D154 last session** (the branch merge, variety/annotation enforcement, the
latency Tier.REVEAL fix) — see decisionlog for that history. **This session (T18J) started from
five concrete defects the user reported with timestamps/screenshots against the D152/D154 closing
render**, fixed three outright, diagnosed the geometry gate's real blind spot, did latency work,
and — once the frontend went live — found and fixed one more real defect from the user's own first
live render through it.

**Three timing defects, confirmed against the exact job's checkpoint before any fix (D155):**
1. A `SPLIT_HORIZONTAL` panel's headline could wait until 80% through its segment, gated on the
   block's own content anchor even though both panels are already visually present from the
   layout's own entrance tween. Fixed in `rendering/compose.py::_build_renderable` — a multi-block
   scene's headline now enters structurally, with its panel; single-block scenes are unaffected.
2. Items rendered in authored order even when resolved anchors placed them in a different
   narration order. Fixed: `text_panel`/`icon_panel`/`title` items are now reordered to match
   (`core/scene_variety.py`'s `_SORTABLE_ITEM_FIELDS`, deliberately excluding `graph_diagram`/
   `code_diff` where order is semantic).
3. An unmatched anchor fell back to a flat 0.75s instant, sometimes before the block itself had
   even entered. Fixed: `rendering/block_timing.py::_interpolate_missing` interpolates against
   the block's own entrance/exit window instead.

**The geometry gate's real blind spot, measured against the two exact compositions the user
flagged (D156):** NOT sample density (raising `--samples` and enabling `--at-transitions` were
both tested directly against the real compositions and changed nothing). The actual bug:
`render_segment.py` treated every `[warning]`-severity finding the same as `[info]` — never
fatal — which silently waved through real `content_overlap` findings `hyperframes check` was
already correctly detecting. Fixed: `rendering/geometry_findings.py::is_fatal_geometry_finding`
promotes a `[warning]` to fatal when its code is in the existing content-sizing vocabulary.
`caption_zone` and `motion` findings also now flow through, at zero measured added cost.

**Latency (D157):** removed the one genuinely decorative perpetual tween (the user's own
observation — "them two cards floating up and down") from `SPLIT_HORIZONTAL`, verified safe via a
real recomposed segment still passing the frozen-sweep guard. Measured the frame budget's real
cost/benefit with a new `scripts/tier_budget_sweep.py` and put the trade-off to the user (a
demoted segment loses the smooth entrance-timing work, not just ambient motion) — **user chose to
keep `FRAME_BUDGET=9500`**, every segment fully animated. `RENDER_MAX_CONCURRENCY` raised 2→3 (not
config's own default of 4) after checking actual free RAM (~4GB, with a known drop to ~2.4GB under
load) rather than assuming CPU was the only constraint. Geometry re-author scoping (refill only
the failing block, not the whole scene) was investigated and deliberately deferred — the flattened
finding-string contract loses the block-attribution data a real fix would need; not a one-line
patch, recorded rather than rushed.

**`project-reviewer` caught two real bugs across two passes, both fixed and confirmed by
reproduction (D158):**
1. The item-reorder fix (above) silently broke annotation targeting whenever a reorder actually
   fired — an annotation authored against pre-reorder item position kept targeting that same
   numeric position after the reorder, marking the wrong item. Fixed by threading the permutation
   through `RenderableBlock.item_permutation` and translating in `rendering/annotations.py`.
   Verified by deliberately reverting the fix and confirming the exact mistargeting reproduces,
   then restoring it.
2. `caption_zone_collision` (newly reachable once the geometry fix started passing
   `caption_zone`) was fatal but not in `_CONTENT_SIZING_CODES`, so a segment failing purely on
   caption-band overflow skipped its retry and degraded unconditionally. Added.

**The frontend went live this session — first real run, first real bug found live (D159).** Backend
+ frontend dev servers started and verified end-to-end through the real Vite proxy. **Caught after
the fact: the backend was started without `--reload` and was never restarted after the D155-D158
code fixes landed**, so the user's first real job (`436c209225f848b39db5e698ac3aac1a`) ran on
pre-fix code. Cross-referencing the user's screenshots against that job's own segment data found a
real, additional bug regardless of the stale-code issue: **4 of 15 segments rendered as `title`**
(only 1 legitimately the forced opener) — a static headline+paragraph with no progressive reveal,
used for regular content segments the skill pack's own guidance says `title` is explicitly not
for. Fixed: `core/scene_variety.py` gained a `title`-specific cap (`1/10`, tighter than the general
rule, same shape as the existing `sequence_diagram` cap), folded into the same bounded re-ask.
Backend restarted with `--reload` immediately after being caught.

**Full regression, current state:** `pytest` full suite green (see git log for exact counts per
commit), `ruff check .` clean, both boundary greps clean, no `.py` over 200 lines, `openapi.json`
unchanged across every commit this session (all work was backend/render-internal).

## Known gaps and open questions

**New, found or left open this session:**
- **Two of the user's five original defects (annotation/cursor placement "not nice," a graph
  diagram called "a little messy") were NOT independently diagnosed** — the only real render
  available to check them against (`436c209225f848b39db5e698ac3aac1a`) predates every code fix
  from this session, so a placement complaint on it could be explained by bugs already fixed
  (the annotation-reorder bug is a strong candidate) or could be a genuine separate issue. **A
  fresh render on today's code is needed before any further placement work is scoped** — do not
  guess at a fix without one.
- **CURSOR's "tip lands on the target's own centre" design may itself read as visually rough** on
  a `graph_diagram` node (the screenshot showed the cursor glyph overlapping the node marker) —
  this is by design (`_annotation_cursor.html`'s own comment: the glyph's tip is meant to land on
  the point), not a bug, but worth a design judgment call once a fresh render confirms it's still
  happening: is the current glyph/angle just visually unrefined, or is "tip on centre" itself the
  wrong choice for a small circular marker specifically.
- **The `title` cap (`1/10`) and the `sequence_diagram` cap (`1/5`) are both soft, one-shot
  nudges** — `plan_visuals` spends its single bounded re-ask on whichever violations exist, but
  the second plan is taken as final even if it still misses (documented, same shape as
  `missed_block_opportunities` since T18E). Confirmed live for `sequence_diagram` (D152); not yet
  separately confirmed for the new `title` cap.
- **Latency fixes from Phase 3 have not been re-measured on a real render this session** — the
  idle-bob removal was verified safe (no new frozen-sweep finding) but not measured for actual
  time saved; concurrency=3 has never run under real load.
- **New `SceneLayout` members and the rest of the visual-polish plan (motif-driven typography,
  syntax highlighting, icon two-toning, a `text_panel` redesign) were scoped but explicitly not
  attempted this session** — flagged in the plan itself as the largest, least mechanical phase,
  likely wanting its own session.
- **No test yet for the whole-video annotation budget wired at the `collect_scenes` GRAPH level**
  beyond `tests/test_collect_scenes_node.py`'s direct node test.

**Carried forward, genuinely still open:**
- `hyperframes check`/`validate_geometry` still occasionally non-deterministically flaky (D96).
- No coverage gate exists (D42). T10 (`RUNTIME_ENV=local`'s Ollama/Kokoro) still unclaimed.
- `api/runner.py::WORKING_ROOT` still has no cleanup routine.
- `artifacts/_api_run/` and `artifacts/_cli_run/` both growing with every real render this
  session added several more job directories to each; gitignored, safe to clean up locally.
- Frontend items from T37 (out of this task's territory, per CLAUDE.md's invariant 5):
  `Pill`/`StatusPill`'s WCAG contrast gap, `StageTicker`'s occasional generic label,
  no automated tests for `ClipTrack`/`ClipStrip`/`use-placeholder-cycle.ts`/`theme-store.ts`,
  ~516KB JS bundle (not code-split).

## Before the next session

**T18J is not closed** — real, named gaps above, most importantly the two placement complaints
that need a fresh render to even diagnose properly.

**The most useful thing to do first: generate one real video on today's fully-fixed code** (either
via `cli.py` or the frontend, both work) and check, specifically: do the three D155 timing fixes
hold up, does the geometry gate now catch what it should without over-blocking, is `title` no
longer overused, and — the two genuinely open items — does annotation placement still look wrong,
and does the graph diagram still look "messy." That render is what turns the two open complaints
from a guess into a real diagnosis.

Real remaining choices, not yet decided:
1. Continue T18J's visual-polish plan (motif-driven typography, new layouts, syntax highlighting)
   vs. move to the deferred cloud work (T34/T35, see
   `C:\Users\juant\.claude\plans\foamy-sparking-swing.md`) vs. T29-T33 (RAG).
2. Whether the `title`/`sequence_diagram` caps need to become hard guarantees (deterministic
   downgrade) rather than soft nudges, if they keep missing in practice.

## Environment state

| | |
|---|---|
| Model | Session ran on Opus for planning; `/model sonnet` run explicitly before the build phase, per CLAUDE.md's mandatory self-check. Verify again at the start of the next session. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local`, unchanged — real render, in-process. |
| `FRAME_BUDGET` | `9500`, unchanged — user's explicit choice this session, see D157. |
| `RENDER_MAX_CONCURRENCY` | `3` in this machine's own `.env` (gitignored) — raised from 2 after checking actual free RAM; `.env.example`'s own default stays `2`, unchanged, for other environments. |
| Git | `dev`, at the tip of this session's commits, pushed to `origin/dev`. |
| Backend/frontend servers | Both were left running at session end: `uvicorn api.main:app --reload` on `127.0.0.1:8000`, `npm run dev` (Vite) on `127.0.0.1:5173`. **Started with `--reload` this time** — the first backend start this session was NOT, which is exactly how a stale-code job got submitted (see D159). Check they're still up before assuming the frontend works; restart if not. |
| Azure spend | Multiple real renders this session (`RUNTIME_ENV=azure`, real LLM+TTS+Storage): the D155/D156 closing-scope render, the tier-budget-sweep's real TTS pass, and the user's own API-submitted job. Check `/costs`. |
| Local artifacts | `artifacts/_cli_run/` and `artifacts/_api_run/` both gained job directories this session (gitignored, safe to clean up). |

## Gotchas worth remembering

**New this session:**
- **A backend process started without `--reload` silently keeps running old code through every
  subsequent edit** — cost a full render cycle on stale code before being caught (D159), and was
  only caught by cross-referencing user-reported screenshots against the job's own data, not by
  anything that would have surfaced it automatically. Always start a long-lived dev server with
  `--reload`/equivalent, and if one is already running when a session starts making code changes,
  restart it rather than assume it's current.
- **A pure function that changes item ORDER can silently break something else's item-index
  assumptions** — the `resolve_item_starts` reorder fix broke annotation targeting because
  `core/graph/nodes/annotation_author.py` authors indices against a different ordering than what
  ends up on screen. Any function that reorders/filters/re-indexes a list needs an explicit check
  for every OTHER place that list's original indices are referenced, not just its own callers.
- **Enabling a new check/finding type is incomplete without also updating every classification
  set that reads finding CODES** — `caption_zone_collision` was correctly fatal but silently
  unretryable because `_CONTENT_SIZING_CODES` (a different set, same module) wasn't told about it.
- **A geometry finding's severity (`[warning]` vs `[error]`) is not reliably tied to how visible
  or real the defect is** — measured directly: the same `content_overlap` finding stayed
  `[warning]` regardless of sample density or `--at-transitions`. Don't assume severity alone is a
  safe fatal/non-fatal signal without checking the actual finding CODE too.
- **A checkpointed job's `AsyncSqliteSaver` state is queryable directly**
  (`saver.aget({"configurable": {"thread_id": job_id}})` against a job's own `checkpoints.sqlite`)
  for post-hoc analysis of exactly what a run produced — works for both `cli.py`'s
  `artifacts/_cli_run/` and the API's `artifacts/_api_run/` layouts. The API path additionally
  persists a `job.json` via `api/job_store.py`, reachable through `GET /jobs/{id}` — a faster
  check when only segment metadata (not the full scene/word_marks state) is needed.
- **File birth/modify timestamps (`stat`) on a job's `checkpoints.sqlite` give real wall-clock
  render duration** when nothing else recorded it explicitly — birth time = job start, last
  modify = job completion.

**Carried from earlier sessions, still true:**
- `AsyncSqliteSaver.from_conn_string(path)` creates `path` on disk the instant it connects.
- Every real invocation of this graph must pass `durability="sync"` explicitly.
- `Storage.url()`'s scheme is the only safe way to branch redirect-vs-stream at the API layer.
- `FakeLLMProvider`'s strict-FIFO queue breaks under real concurrency with mixed schema types —
  `PhaseQueueLLMProvider` is the fix pattern; a fixture using one interchangeable block type
  everywhere may need its LLM response queued twice once a new code-enforced variety rule
  correctly re-asks against it.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
- The quality hook strips an import added in one tool call and used only in a later one — add the
  import in the same call as its first real usage, every time, no exceptions found yet.
