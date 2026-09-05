# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

_Last updated: 2026-09-05 · T18I (video-quality fixes from the user's own direct complaints on
real rendered output) advanced substantially this session, not yet closed · `project-reviewer` run
and its findings fixed · not yet checkpointed/pushed_

---

## Where we are

**The two branches are reunited.** `feature/scene-composition` (T18G/T18H, a WIP T18I slice, all
one week old) was merged into `dev` this session, curated: `VideoJob`/`JobStatus` moved to
`core/video_job.py` (mechanical import fix across `api/`+`cli.py`, no API contract change —
confirmed via `dump_openapi` diff), everything else taken wholesale after review. The WIP
retry/fallback scaffolding (`scene_reauthor.py`/`scene_fallback.py`/`render_scene.py`'s rewrite)
was reviewed rather than trusted and found complete and correct — see `tasks.md`'s T18I entry for
the full account of what was already done vs. built fresh this session.

**One real bug found live, fixed, re-verified**: `rendering/geometry_findings.py` was missing
`text_occluded` from its retryable-finding set, so two segments in this session's own baseline
render skipped the re-author step entirely and fell straight to the fallback. Fixed; a second
render confirmed both segments now retry correctly.

**New scope, from fresh direct user complaints mid-session (variety, sequence-diagram overuse,
annotation density/coherence)** — all built, code-enforced, tested, and verified on a real render:
`core/scene_variety.py`, `core/scene_content_normalize.py`, `core/annotation_normalize.py`, and a
newly-real `core/graph/nodes/collect_scenes.py` (previously an empty join). `project-reviewer`
found three real bugs in this new code (a rounding false-negative on the sequence_diagram cap, an
ITEM/LINK index-space conflation in CURSOR coherence, a non-adjacent-segments-compared-as-adjacent
gap) — all three fixed, each with a regression test reproducing the reviewer's own repro.

**Verified, live, same topic before/after (D152 has the full numbers):**

| | Before | After |
|---|---|---|
| `sequence_diagram` message counts | `[6,6,6,6,6,5,7]` | `[3,3,3,3,3]` — hard-capped now |
| Segments with any annotation | 13 of 15 (87%) | 4 of 15 (27%) |
| `text_occluded` triggers a retry | No | Yes |

**Full regression, current state:** `pytest` 1046 passed / 1 skipped, `ruff check .` clean, both
boundary greps clean (one docstring-text hit, not a real import), no `.py` over 200 lines,
`openapi.json` unchanged (all this session's backend work is pipeline-internal), `web/`'s
`tsc`/`eslint`/`vitest`/`build` all clean (unaffected — this session touched no frontend files).

## Known gaps and open questions

**New, found or left open this session:**
- **The `sequence_diagram` FREQUENCY cap is a soft one-shot nudge, not a guarantee** — confirmed
  live it can still miss after the one bounded re-ask (same documented shape as
  `missed_block_opportunities`). If the user wants a hard guarantee, it needs the same
  deterministic-downgrade treatment `scene_content_normalize.py` gives message *length*, not a
  second LLM call.
- **New `SceneLayout` members (`STACKED`, an asymmetric split) were scoped, not built** —
  deprioritized this session in favor of the enforcement/correctness work above.
- **Latency**: the closing render ran 18.1 min against a ~15 min target for a 10-min-equivalent
  video, because both degraded segments needed a full retry-then-fallback cycle (each a real
  render+validate round trip). Expected to shrink as the geometry-gap-closure work below reduces
  how often that cycle fires at all — the fix is fewer failures, not weaker recovery.
- **No test yet for the whole-video annotation budget wired at the `collect_scenes` GRAPH level**
  beyond `tests/test_collect_scenes_node.py`'s direct node test — no end-to-end graph test exercises
  it through a real fan-out.

**Carried forward, genuinely still open (T18I's original scope, `tasks.md` has the full text):**
- `hyperframes check`/`validate_geometry` still occasionally non-deterministically flaky (D96).
- No coverage gate exists (D42). T10 (`RUNTIME_ENV=local`'s Ollama/Kokoro) still unclaimed.
- `RENDER_MAX_CONCURRENCY=2` still unmeasured under real concurrent load.
- `api/runner.py::WORKING_ROOT` still has no cleanup routine.
- Frontend items from T37 (still open, not touched this session — out of this task's territory
  per CLAUDE.md's invariant 5): `Pill`/`StatusPill`'s WCAG contrast gap (2.82-4.43:1), `StageTicker`
  occasionally showing a repeated generic label instead of the real segment title, no automated
  tests for `ClipTrack`/`ClipStrip`/`use-placeholder-cycle.ts`/`theme-store.ts`, ~516KB JS bundle
  (not code-split).

## Before the next session

**T18I is not closed.** A `/checkpoint` has not run yet this session (this handoff is being
written manually mid-session, not at a normal checkpoint boundary) — do one before starting new
work, so decisionlog/tasks.md/handoff.md all agree and this gets pushed.

Real remaining choices, not yet decided:
1. Keep going on T18I (new `SceneLayout`s, a hard sequence-diagram-frequency guarantee, more live
   geometry verification) vs. call the current state "good enough" and move to the deferred cloud
   work (T34/T35, see the plan file this session started from,
   `C:\Users\juant\.claude\plans\foamy-sparking-swing.md`, for the two-session split already
   scoped) vs. T29-T33 (RAG, scheduled last per the backlog).
2. `feature/scene-composition` is now merged — that standing note from every checkpoint since
   T18B is finally retired.

## Environment state

| | |
|---|---|
| Model | This session ran on Opus for the planning/discussion phase; `/model sonnet` was run explicitly before any build/Edit/Bash, per CLAUDE.md's mandatory self-check. Verify again at the start of the next session — this has now been the wrong-model failure mode multiple sessions running. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100), unchanged — real render, in-process. |
| `QUEUE_ENV` | `local`, unchanged. |
| Git | `dev`, at the tip of this session's commits (merge commit, then two follow-up commits for the new enforcement code and its review-fix pass). Not yet pushed to `origin/dev`. |
| Azure spend | Two real ~15-18 min renders this session (`RUNTIME_ENV=azure`, real LLM+TTS+Storage) — check `/costs` before assuming the trial credit is untouched. |
| Local artifacts | `artifacts/_cli_run/` now has two more job directories from this session's renders (`b7696e12...`, `91c3dbeb...`) plus their `checkpoints.sqlite` files — gitignored, safe to leave or clean up. |

## Gotchas worth remembering

**New this session:**
- **A `dict`/`list` value change that a merge auto-resolves cleanly can still land two unrelated
  classes' bodies interleaved** if the base and incoming sides both edited near the same class
  boundary (`core/models.py`'s `VideoJob` fields ended up pasted mid-`Segment` by git's own
  3-way merge) — always re-read a conflict-adjacent region after resolving markers, don't trust
  that "no `<<<<<<<`  left" means the file is structurally sound.
- **The quality hook's import-stripping gotcha bit this session three separate times** (once per
  new cross-module call added in one `Edit` and used in a later one) — CLAUDE.md already documents
  this; it is worth re-reading before a session with several small sequential edits to the same
  new import, not just once at session start.
- **A fraction-based threshold check needs an explicit floor for small `total`, and needs to avoid
  `round()` if the general/sibling check it's modeled on doesn't round either** — a `round()` on a
  cap silently loosens it for whichever totals happen to round up, invisible until someone runs the
  actual numbers (this session's own `project-reviewer` catch, `core/scene_variety.py`).
- **Two annotation "index spaces" on the same block (ITEM vs. LINK) must never be compared against
  each other for ordering** — grouping by block alone when a block can carry both silently produces
  a nonsense comparison. Group by `(block, kind)`, not `block`.
- **A checkpointed job's `AsyncSqliteSaver` state is queryable directly** (`saver.aget({"configurable": {"thread_id": job_id}})` against `artifacts/_cli_run/<job_id>/checkpoints.sqlite`) for post-hoc analysis of exactly what a `cli.py` run produced — `cli.py` itself persists no `job.json` the way the API path does (`api/job_store.py`), so this is the only way to inspect a bare-CLI run's actual scene/annotation content after the fact.

**Carried from earlier sessions, still true:**
- `AsyncSqliteSaver.from_conn_string(path)` creates `path` on disk the instant it connects.
- Every real invocation of this graph must pass `durability="sync"` explicitly.
- `Storage.url()`'s scheme is the only safe way to branch redirect-vs-stream at the API layer.
- `FakeLLMProvider`'s strict-FIFO queue breaks under real concurrency with mixed schema types —
  `PhaseQueueLLMProvider` is the fix pattern; a fixture that deliberately uses one interchangeable
  block type everywhere (for that reason) may need its LLM response queued twice if new
  code-enforced rules (like this session's variety check) now correctly re-ask against it.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
