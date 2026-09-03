# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached** — if you're starting cold, this file plus `tasks.md`'s T37
entry should be everything you need before opening a single source file.

_Last updated: 2026-09-04 · a fix pass on top of T24-T28+T36 (real backend bug + structural
frontend work, "Parts 1-3" below), followed by a live-UI review that scoped T37 (visual redesign,
gated behind a wireframe) · not yet reviewed by `project-reviewer` for this pass specifically_

---

## Where we are

**T24-T28 and T36 (the whole React frontend + SCORM export) were built and committed last
session (`8ebda33`).** Trying it for real, immediately after, surfaced a real backend bug the
prior session's `project-reviewer` pass didn't catch (it wasn't yet exercised against a real
Azure backend). This session fixed that bug and the structural work it exposed was needed
("Parts 1-3" below), verified against **two real Azure renders**, then had a live-UI review with
the user that concluded the visual design needs a real redo.

**Done this session (Parts 1-3):**
1. **The queue bug, fixed** (`config_queue.py`, the `QUEUE_ENV` bridge) — `RUNTIME_ENV=azure`
   alone could never complete a job through the real API; `cli.py` worked because it bypasses
   `JobQueue` entirely. Full story: decisionlog D139.
2. **Submission failures now surface as a toast**, not a silent ghost job. D140.
3. **One page, two URLs** — `/` and `/jobs/:jobId` both render `StudioPage`; submitting a topic
   never navigates away. D141.
4. **Real incremental segment persistence** — the segment grid and tier badges now actually fill
   in live during a render, instead of jumping from empty to complete at the very end. This took
   two attempts; the real story (a state-channel gap in `core/graph/state.py`, not something
   guessable from reading `api/runner.py` alone) is in D142 — read it before touching
   `api/runner.py`'s save logic again.
5. **Six progress-view enrichments** (rail-fill + pulsing halo on the phase strip, an elapsed
   clock, a live stage ticker, pulsing active segment cards, a shimmering frame-budget meter) —
   all wired to real data via a new `use-progress-model.ts`, no fabricated progress anywhere.
6. `skill-bites` rename (header, browser tab) — done, not part of T37, don't redo it.

**Verified:** 726 backend tests (was 691 before this session's earlier T24-T28 pass; +2 today),
40 frontend tests (was 30; +10 today), clean `tsc`/`eslint`/`ruff`, production build succeeds, two
full real Azure renders completed end to end (including a real SCORM package downloaded and
unzipped — `imsmanifest.xml`/`launch.html`/`video.mp4` all present).

**Next: T37 (frontend visual redesign), genuinely not started as design work.** No wireframe
exists yet; no visual/styling code has changed beyond item 6 above and un-collapsing the composer
(a structural change, not a style one). See `tasks.md`'s T37 entry for the full requirements list
— repeated in condensed form below so this file alone is enough to start from.

## T37, condensed (full version in `tasks.md`)

The user used the real, working frontend and rejected its current visual design. Gathered
requirements, their intent preserved exactly:
- **No forced dark theme** — light only, regardless of the visitor's system preference.
- **Restore and amplify real hover/motion, don't remove it.** This session initially misread "no
  fun elements" as a request to strip interactivity — that was backwards, and the user corrected
  it directly. They want *more* glow/lift/pop, not less. (The screen judged was mid-render with
  almost nothing on it yet — not representative of the app.)
- **Wireframe first, via both**: Claude's `design` skill (a clickable mockup, published as an
  Artifact, for layout/IA sign-off) **and then** Impeccable's real `craft`/`shape`/`critique`
  workflow (already installed — `.claude/skills/impeccable/`) to build the approved direction for
  real. T24-T28 installed Impeccable but never ran its actual design commands, and only read a
  prose summary of https://nomu.store/ instead of looking at it — don't repeat either shortcut.
- **Don't touch Parts 1-3's structural work** (the one-page studio, SSE progress wiring,
  incremental persistence, error toasts) — this task is the visual layer on top, not a rebuild.
- **Don't weaken the T18/frontend seam** — see CLAUDE.md's fifth invariant, added this session
  specifically so this guarantee survives into a fresh session's context (below has the short
  version too).
- **DoD gate**: the wireframe must be reviewed and explicitly approved by the user before any
  component's real visual/styling code changes. Do not skip straight to a rebuild.

## The T18/frontend seam — now a permanent CLAUDE.md invariant, repeated here

`Segment.scene` is untyped (`dict[str, Any]`) on the backend by design (D29), and the frontend
renders it with a **generic, data-driven JSON tree** (`web/src/adapters/scene-adapter.ts` +
`web/src/features/segments/SceneTree.tsx`) — never per-block-type components. A new block type or
restructured layout from a future T18 session renders correctly with zero frontend changes; proven
by a test (`scene-adapter.test.ts`) against an entirely invented future scene shape. Separately,
`web/eslint.config.js`'s `no-restricted-imports` rule mechanically blocks `features/`/
`components/`/`routes/` from importing the generated API client directly, so a backend contract
change becomes a `tsc` failure in exactly one file (`adapters/job-adapter.ts`), never a silent
break. **A T18 session can treat this as settled**: touching `rendering/`, `core/block_types.py`,
`core/scene_schemas.py`, or the block-authoring templates never requires a `web/` change. Full
account: CLAUDE.md's invariant 5, decisionlog D130-D131, D144.

## Verify at any time

```bash
pytest                                    # offline, no network -- 726 passed, 1 skipped
ruff check . && ruff format --check .     # clean
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # empty (one
                                           # docstring-text hit in node_timing.py, not a real import)
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # empty

cd web
npx tsc -b --noEmit && npx eslint . && npx vitest run && npm run build     # all clean -- 40 tests

python -m scripts.dump_openapi && cd web && npx openapi-typescript ./openapi.json -o \
  ./src/api/schema.d.ts && git diff --exit-code openapi.json src/api/schema.d.ts   # drift alarm

# Fast loop, free, no Azure spend:
python -m scripts.serve_fake                      # fake backend, port 8000
cd web && npm run dev                              # frontend, port 5173, proxies /api -> :8000

# Real end-to-end, real Azure spend (~$0.12/7-min video, ~15-20 min):
.venv/Scripts/python.exe -m uvicorn api.main:app   # real backend, port 8000 -- needs QUEUE_ENV=local
                                                    # in .env (see "Environment state" below)
cd web && npm run dev                              # same frontend, port 5173
```

## Uncommitted right now — read before running `git status` and assuming something is wrong

**This session's work is uncommitted at the time this file was written** — the plan approved for
this checkpoint is to commit and push it to `origin/dev` as part of closing this session out.
If you're reading this in a fresh session and `git log -1` on `dev` does **not** show a commit
mentioning "Parts 1-3" or "QUEUE_ENV" newer than `8ebda33`, the commit/push step did not complete
— check `git status` and finish it before assuming this file's "Done" list is actually on `dev`.

## Environment state

| | |
|---|---|
| Models | This session ran on Sonnet throughout (confirmed twice — CLAUDE.md's mandatory self-check triggers on every plan-mode re-entry, and this session re-entered plan mode twice). **Opus is still this user's saved default for new sessions** — worth fixing at the source if this keeps recurring, since the check has now caught it three sessions running. |
| Browser automation | Still no browser MCP connected this session (`playwright` MCP: `CONNECT_TIMEOUT`). All live-browser verification (multiple rounds of screenshots, the D141/D143 bugs) used Python Playwright directly — already a project dependency, Chromium already installed on this machine. Worth fixing the MCP connection before T37, which will need heavy visual iteration. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100), unchanged. |
| **`QUEUE_ENV`** | **New this session — `local`, in both `.env` and `.env.example`.** Without it, `RUNTIME_ENV=azure` cannot complete a job through the real API at all (D139). |
| `WEB_ORIGINS` | `http://localhost:5173` default, unchanged since T24-T28. |
| `FRAME_BUDGET` / `FPS` | `9500` / `24`, unchanged. |
| Git | `dev`, at `8ebda33` (T24-T28+T36) plus this session's uncommitted work on top — see "Uncommitted" above. `feature/scene-composition` still unmerged, still ahead of `dev` by the T18I WIP commit (`91f57ef`) from two sessions ago — unchanged, still the user's own call. |
| Azure spend | Two real 3-minute videos rendered this session (~$0.05-0.07 each), both to completion, one downloaded as a real SCORM package. No other real spend. |
| Node | v24.16.0 / npm 11.13.0. `web/`'s `package.json`/lockfile independent of the root's `hyperframes`-only one — unchanged. |

## Known gaps and open questions

**New, found this session:**
- **`api/runner.py::_assemble_preview` adds one extra `graph.aget_state()` + `JobStore.save()`
  call per stage "end" event** (roughly 30-65 calls for a real 6-21 segment job, per D142's own
  math) — real, if modest, extra Storage/checkpoint I/O per run. Not measured under load; worth
  keeping in mind if a future session investigates render-loop performance.
- **`web/`'s production bundle is ~509 KB JS / ~165 KB gzipped** — grew slightly this session
  (was 503/163). Still the same `motion`+Radix+Query+Router cost flagged in the T24-T28 handoff;
  code-splitting is the lever if it ever matters, still not done.
- **No real `RUNTIME_ENV=azure` run has exercised the SAS-redirect branch of `api/artifact_response.py::serve_artifact`** — both real renders this session used the same Azure Blob Storage backend as before, so this *should* be exercised now (Blob returns `https://` URLs), but wasn't specifically checked. Worth a explicit look if that branch is ever suspected.

**Carried forward, unchanged:**
- T18F and T18E's three findings — still exactly where T18E left them, untouched again this
  session (this session was pure `api/`/`web/` work, no `rendering/`/`core/block_types.py` touched
  at all, consistent with CLAUDE.md's new invariant 5 above).
- No coverage gate exists (D42). T10 (`RUNTIME_ENV=local`'s Ollama/Kokoro) still unclaimed.
- `RENDER_MAX_CONCURRENCY=2` still unmeasured under real concurrent load.
- `hyperframes check` still non-deterministically flaky at times (D96).
- `pipeline-debugging`'s documented artifact layout still stale (T18D flagged it).
- `api/runner.py::WORKING_ROOT` still has no cleanup — three real jobs' worth of directories now
  (two from this session, growing).
- Scope: 38 tasks across 8 iterations, plus T18A-F (T37 added this session).

## Before the next session

**Start with T37** unless something more urgent comes up — see "Where we are" and "T37, condensed"
above; `tasks.md` has the full version. **Do not build T29 (RAG/document upload) or any other new
feature before T37** — this was an explicit recommendation given to the user this session (polish
the working UI before adding more surface to redesign later), and the user's own framing already
agreed with it.

**`feature/scene-composition` is still unmerged into `dev`** — same standing note as every
checkpoint since T18B, still the user's own decision, not automatic.

## Gotchas worth remembering

**New this session:**
- **A graph's checkpointed state can have a field on more than one channel that looks related but
  isn't kept in sync until one specific node runs.** `state["job"].segments` (the pydantic list)
  and `state["segments"]` (the fan-out accumulator dict) are NOT the same data mid-run — only
  `finalize.py` reconciles them, at the very end. Before assuming a mid-run snapshot of any
  `GraphState` field reflects "live" progress, check whether some later node is actually the one
  that assembles it. This bit `api/runner.py` twice in the same session before the real cause was
  found (D142).
- **A React key built from a timestamp is not safe under real concurrency.** `Date.now()` (or any
  event's recorded "at" time) can collide across concurrent async tasks that fire in the same
  millisecond — T18B's own fan-out design guarantees this happens routinely. Use the item's stable
  position or a real unique id instead (D143).
- **When a user says "remove X," check whether they mean X specifically or are describing a
  symptom of something else entirely.** "No fun elements at all" was about a mostly-empty
  mid-render screen, not a request to strip the hover/motion system this frontend was explicitly
  built with. Reading it literally would have been a real regression against the original brief.
  When in doubt on a request that reverses an explicit prior instruction, confirm before acting —
  which is what surfaced the correction here.
- **`TestClient`'s SSE streaming and a concurrent REST call race unpredictably against fakes, even
  with an artificial delay in the right place.** Don't build a regression test around "observe a
  live event, then immediately GET and assert on timing" — intercept the actual function call
  (`JobStore.save`, here) instead, which is deterministic regardless of scheduling.
- **Under `FRAME_BUDGET=0`, every segment stays Tier 0/1, which renders through
  `RenderBackend.capture()` + real ffmpeg — `RenderBackend.render()` is a Tier-2-only path.**
  Slowing down or otherwise instrumenting the wrong method in a fake silently does nothing. Cost
  this session ~15 minutes of a genuinely confusing test failure before being caught.

**Carried from T24-T28 and earlier, still true:**
- The frontend's own client-side routes can collide with backend API routes proxied from the same
  origin — namespace API calls under a distinct prefix (`/api`) in the dev proxy, not in the
  backend's own paths.
- `npx --no-install X` resolves `node_modules/.bin` from cwd upward, never downward.
- A pydantic model's prompt-embedded requirement (e.g. `f"Produce exactly {N} segments"`) is a
  legitimate signal a test fixture can read back, rather than needing the count told out-of-band.
- Claude Code's PostToolUse hooks can inherit the Bash tool's persisted cwd — `cd` back to the
  repo root (or use a subshell) before an Edit/Write call, not just before Bash calls.
- `AsyncSqliteSaver.from_conn_string(path)` creates `path` on disk the instant it connects, not
  when a checkpoint is first written. Ask the checkpointer, never check file existence.
- Every real invocation of this graph must pass `durability="sync"` explicitly.
- `Storage.url()`'s scheme is the only safe way to branch redirect-vs-stream at the API layer —
  `startswith(("http://", "https://"))`, not `== "file://"`.
- `FakeLLMProvider`'s strict-FIFO queue breaks under real concurrency with mixed schema types —
  `PhaseQueueLLMProvider` (matches by type, not position) is the fix pattern.
- The quality hook strips an import added before its first use — add the import in the same tool
  call as its first real usage.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
