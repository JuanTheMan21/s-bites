# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-09-03 · after T19-T23 (Iteration 4: the FastAPI backend), built in one
combined session by the user's own choice · reviewed twice by `project-reviewer`, three real bugs
found and fixed on the first pass, one more (low-severity) on the re-review, also fixed_

---

## Where we are

**This session did three things, in order: synced this machine with a laptop that had pushed 11
commits ahead on `origin/dev` (T18B through T18E all shipped there already); paused T18's
iteration chain on the user's own explicit instruction; and built all of Iteration 4 (T19-T23,
the FastAPI backend) in one combined session.** Full reasoning for each: decisionlog D123-D129.

**Done:** T1-T18, T18A, T18B, T18C, T18D, T18E, **T19, T20, T21, T22, T23**.
**Paused, not abandoned:** T18F ("vision critique/revision loop, full validation render,
rendering/pipeline speed") and three real-render findings T18E recorded but did not fix
(inter-annotation collision, a version-number-driven `TIMELINE` blind spot, combined-effects
layout collisions in a dense `GRAPH_DIAGRAM`). Untouched this session — still exactly where T18E
left them, `tasks.md` unedited.
**Next: genuinely open, same as T18E's own handoff left it, and for the same reason.** Iteration 4
is a clean stopping point (T24+ is a different tech stack, Vite/React) and T18's pause was a
one-session redirect, not a decision to abandon it. Three real candidates exist, and this file
does not pick one: **T24** (frontend scaffold, next in `tasks.md` sequence), **resuming T18F or
the three T18E findings**, or **the artifact-streaming gap this session's own review surfaced**
(see "Known gaps" below — genuinely new information, not previously scoped anywhere). Worth a real
conversation with the user before assuming any of the three.

## What T19-T23 built

All new, under `api/` (previously a single empty `__init__.py`) and `tests/test_api_*.py` +
`tests/api_fixtures.py`:

- **`api/app.py`** — `create_app(adapters, *, frame_budget, fps) -> FastAPI`, a pure factory that
  takes an already-resolved `Adapters` bundle rather than building one itself, so tests inject
  `tests/fakes/*` directly instead of a second, environment-dependent construction path only
  production exercises. Lifespan starts/stops the runner and calls `close_adapters`.
- **`api/main.py`** — the real ASGI entrypoint (`uvicorn api.main:app`), the one place `api/`
  reads `RUNTIME_ENV`/`FRAME_BUDGET`/`FPS` from the environment, mirroring `cli.py`'s own
  edge-reads-env pattern rather than sharing a helper across the two entrypoints.
- **`api/jobs.py`** — `POST /jobs` (submit), `GET /jobs` (list), `GET /jobs/{id}` (lookup),
  `POST /jobs/{id}/resume`, `GET /jobs/{id}/events` (SSE).
- **`api/artifacts.py`** — `GET /jobs/{id}/video`, `GET /jobs/{id}/subtitles`, both through
  `Storage`, never a raw filesystem path.
- **`api/runner.py`** — the single background task that dequeues, drives the graph, and closes
  out the queue receipt. **This is where D67's long-open cross-requeue attempt ceiling finally
  closes** (`MAX_ATTEMPTS = 3`) — full story in D126.
- **`api/events.py`** — `JobEventBus` (per-job pub/sub, since `astream_events` has exactly one
  consumer and an HTTP request can arrive after a run has already started) and
  `summarize_node_event`, which reduces a raw LangGraph event to one stage transition.
- **`api/job_store.py`** — `VideoJob` snapshots persisted through `Storage` (`jobs/{id}/job.json`)
  plus a small `jobs/index.json` standing in for a `Storage.list()` that does not exist (D127).
- **`api/schemas.py`** — `JobSubmission`, the request body (`topic`, optional
  `target_duration_ms`) — deliberately not `VideoJob` itself, since `job_id`/`status`/`created_at`
  are server-assigned and `VideoJob`'s own `extra="forbid"` would reject a client that supplied
  them, even correctly.

**14 new tests, all exercising the real `langgraph` library end to end against `tests/fakes/*`
only** (never mocked LangGraph itself) — a real job is submitted, streamed, resumed, and its
artifacts fetched through the actual FastAPI app via `TestClient`. This caught real bugs a
lighter-weight test style would have missed; see below.

## Two review passes, real bugs found and fixed — read before touching `api/runner.py` again

**First pass, three bugs:**
1. **Critical.** `api/runner.py` decided "first attempt vs. resume" by checking whether
   `checkpoints.sqlite` existed on disk. Wrong: `AsyncSqliteSaver.from_conn_string` creates that
   file the instant it connects, before any checkpoint is written. A failure before a job's first
   checkpointed superstep (e.g. `plan_segments` itself failing) made every retry after the first
   wrongly think it was resuming an empty thread, crashing on LangGraph's `EmptyInputError` until
   permanently dead-lettered — and the explicit resume endpoint couldn't recover it either, since
   it re-enqueues into the identical broken check. **Fixed:** ask the checkpointer directly
   (`await saver.aget_tuple(gconfig)`), not the filesystem. Verified empirically against the real
   `langgraph` library, not just by reading the diff. Full account: D126.
2. **High.** The `astream_events` call was missing `durability="sync"`, unlike every other real
   call site of this graph (`cli.py`, `tests/test_graph_pipeline.py`,
   `tests/test_graph_resume.py`) — silently reopening the async-durability gap D68 closed. Fixed.
3. **Medium.** `GET /jobs/{id}/events` never checked whether a job already existed or had already
   finished before subscribing — a late or nonexistent subscriber hung the request open forever.
   Fixed: load the job first (404 if unknown), short-circuit to one status event if already
   terminal. D129.

**Second pass (verifying the fixes), one more:**
4. **Low.** `POST /jobs/{id}/resume` didn't flip the job's persisted status to `queued` before
   returning/enqueueing, so the response body (and any poll landing inside the runner's up-to-1s
   dequeue interval) still showed `"failed"` right after a successful resume. Fixed to match
   `submit_job`'s own pattern.

All four are covered by regression tests (`tests/test_api_resume.py`,
`tests/test_api_events.py`) that fail on the pre-fix code and pass now.

## Verify at any time

```bash
pytest                                    # offline, no network -- 666 passed, 1 skipped
ruff check . && ruff format --check .     # clean except test.py (see "Uncommitted", not this
                                           # session's code, explicitly left alone by user request)
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # empty (one
                                           # docstring-text hit in node_timing.py, not a real import)
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # empty
git branch --show-current                                                    # dev

PYTHONPATH=. .venv/Scripts/python.exe -m uvicorn api.main:app --reload       # real entrypoint,
                                                                              # needs a real .env
PYTHONPATH=. .venv/Scripts/python.exe cli.py                  # still works, unaffected by T19-T23
```

## Uncommitted right now — read before running `git status` and assuming something is wrong

Nothing from T19-T23 is committed yet (offered to the user at the end of this session, not pushed
automatically). Alongside the new `api/`/`tests/test_api_*.py` files, three pre-existing items:
- **`mux/ffmpeg_run.py`** (`DEFAULT_TIMEOUT_S` 60.0 -> 300.0) and **`.mcp.json`** (this machine's
  own repo path) — both predate this session, both deliberately left uncommitted per the user's
  own "decide later" call (D123). `.mcp.json`'s path must **never** be committed as-is; it would
  overwrite the other machine's own path on its next pull.
- **`test.py`** (repo root, untracked) — an unrelated personal scratch script (LiteLLM/cert
  testing), explicitly left alone per the user's own call this session. Not part of any task.

## Environment state

| | |
|---|---|
| Models | This session ran on Sonnet throughout, confirmed via the mandatory self-check CLAUDE.md now requires before any build step. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100) — unchanged, still the bridge T35 removes the need for. |
| `FRAME_BUDGET` / `FPS` | `9500` / `24`, unchanged. `api/main.py` reads both the same way `cli.py` does. |
| Git | `dev`, fast-forwarded to `origin/dev`'s `4f10ae7` this session (D123), then T19-T23 built on top, **uncommitted**. `origin/feature/scene-composition` still exists, still ahead of `dev`, still unmerged — same standing note as every checkpoint since T18B. |
| RepoWise | **Real Azure embedder now wired in on this machine** (`text-embedding-3-small`, `skill-bites` resource, credentials in `.repowise/.env`, gitignored) — this machine had been running on the mock embedder before this session (D112 wired it in on the *other* machine; this repeats that setup locally). `repowise doctor` confirms 0% SQL/vector drift. **This session's own live MCP connection is still on the mock embedder** — it only reads `.repowise/.env` at startup, same caveat D112 already recorded. Reconnect before trusting `search_codebase`/`get_answer`'s semantic quality next session. |
| Node / HyperFrames | Unchanged from T18E. |
| Azure spend | No new real `RUNTIME_ENV=azure` render this session — T19-T23 was verified entirely against `tests/fakes/*`, by design (T23's own DoD: "no network, no Azure"). The only real Azure calls this session were the embedder reindex (negligible, embeddings-only). |

## Known gaps and open questions

**New, found by this session's own review, not previously scoped anywhere:**
- **`api/artifacts.py`'s byte-streaming branch (`DiskStorage`'s `file://`, `FakeStorage`'s
  `memory://`) loads the whole artifact into memory and has no HTTP Range/206 support.** A
  ~7-minute rendered MP4 is a full in-memory buffer per request, and — more visibly — video
  seeking in a `<video>` element won't work against local disk storage, which is this project's
  primary day-to-day `RUNTIME_ENV`. Not blocking T21's stated DoD (basic playback does work,
  tested), but a real gap before this is genuinely user-facing. Reviewer's own assessment: low
  severity, not blocking, worth a follow-up.
- **`api/runner.py::WORKING_ROOT = artifacts/_api_run` has no cleanup**, same as `cli.py`'s
  existing `artifacts/_cli_run` — every job leaves a permanent directory behind. Gitignored, no
  repo-hygiene issue, but unbounded disk growth over time in both dev and CI. Not new to this
  session's design (matches the existing `cli.py` pattern exactly), just newly doubled up.

**Carried forward, unchanged:**
- **T18F and T18E's three findings** — see "Where we are" above.
- **`Segment.scene` is untyped by design (D29's pattern)** — still open, revisit at T24 as
  previously planned.
- **No coverage gate exists (D42).**
- **T10 stays `in-progress`, unclaimed.** Ollama/Kokoro still don't exist.
- **`RENDER_MAX_CONCURRENCY=2` was picked from one machine's `hyperframes doctor` output, not
  measured under real concurrent load** — still open, unchanged since T18A.
- **D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only** — still open.
- **`hyperframes check` is still non-deterministically flaky at times (D96)** — re-run before
  trusting a single red result.
- **`pipeline-debugging`'s documented artifact layout is stale** (flagged by T18D, not yet fixed).
- **Scope: 37 tasks across 8 iterations, plus T18A-F.**

## Before the next session

**Nothing code-blocking.** Read this file, then have the "what's next" conversation the "Where we
are" section above flags — T18F, T24, or the artifact-streaming gap all count as reasonable next
work, and nothing here should be read as a recommendation among the three.

**If the two uncommitted pre-existing files still matter**, decide `mux/ffmpeg_run.py`'s timeout
bump and `.mcp.json`'s local path before they're forgotten entirely (see "Uncommitted" above).

**`feature/scene-composition` is still unmerged into `dev`**, ahead of it, standing note since
T18B — still the user's own decision, not automatic as part of any checkpoint.

## Gotchas worth remembering

**New this session:**
- **`AsyncSqliteSaver.from_conn_string(path)` creates `path` on disk the instant it connects, not
  when a checkpoint is first written.** File-existence is never a valid proxy for "has this thread
  run before" — ask the checkpointer (`saver.aget_tuple(config)`) instead. This bit `api/runner.py`
  for real this session (D126); if a future task touches checkpoint-existence logic anywhere else,
  re-read D126 first.
- **Every real invocation of this graph must pass `durability="sync"` explicitly** (D68, reaffirmed
  by D126) — the library's own default (`"async"`) lets a checkpoint write still be in flight when
  the next superstep starts, which is exactly the failure mode this project's resume guarantee
  exists to rule out.
- **`Storage.url()`'s scheme is the only safe way to branch redirect-vs-stream at the API layer**
  (D128) — checking for `file://` specifically is not enough; `FakeStorage`'s `memory://` (and any
  future non-web scheme) needs the same "stream it myself" treatment, so the correct test is
  `startswith(("http://", "https://"))`, not `== "file://"`.

**Carried from T18E, still true:**
- **`FakeLLMProvider`'s strict-FIFO queue breaks the moment a phase makes calls of more than one
  distinct schema type under real concurrency** — `tests/graph_pipeline_fixtures.py
  ::PhaseQueueLLMProvider` is the fix pattern, used only where this specific problem exists.
- **Python's logging module drops `INFO` and below by default until something calls
  `logging.basicConfig`.** `cli.py::main()` does this once; `api/main.py` does not yet (worth
  adding if a future session needs per-node timing visible from a real `uvicorn` run).
- **A Jinja `loop.index0` inside one `{% for %}` block and a JS counter incremented only under a
  condition are NOT the same index** — any per-item id emitted conditionally from a Jinja loop
  needs the SAME index used on both the markup and script sides.
- **The quality hook strips an import added before its first use** — add the import in the same
  tool call as its first real usage.

**Carried from T18C/T18D, still true:**
- **A GRAPH_DIAGRAM node div's CSS center is not its visible marker circle's center.**
- **`[await x() for i in xs]` inside a list comprehension is sequential, not concurrent.**
- **The Blob skill registry does not auto-sync with local disk, ever.**
- **`getBoundingClientRect()` returns viewport pixels, not this project's own 1920x1080 CSS-pixel
  space** whenever the capture harness renders at a different effective scale.

**Carried from T18A/T18B, still true:**
- **`hyperframes lint`'s severity levels are meaningful** — only `[error]` blocks a render.
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
