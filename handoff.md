# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

## What just happened

**T34 shipped and is checkpointed on a new `cloud` branch** (created off `dev`, not yet merged —
see "Before the next session" below). Full context: the user asked for a cloud deployment plan
first; that produced an architecture writeup for their company's architect
(`https://claude.ai/code/artifact/16c2937c-f019-454c-88e0-5dc6f5e99199`, covers topology, cost,
identity, storage retention, and the provisioning request), then the user approved building it in
as few tasks as possible. Iteration 5.5 is now three tasks, not two: **T34 (this session, done)**,
**T35** (image + IaC + first real cloud run), **T38** (new — auth/ownership/Static-Web-Apps
deploy, the task that produces an actual shareable link). Full reasoning for every non-obvious
choice: `decisionlog.md` D173-D177.

### T34 — what actually shipped
- **Real `ServiceBusJobQueue`** (`adapters/azure/job_queue.py`) — was a T12 `NotImplementedError`
  stub, now fills in `enqueue`/`dequeue`/`complete`/`fail` for real. Lease/renew via a fresh
  `AutoLockRenewer` **per in-flight message** (not one shared for the adapter's lifetime — the
  first version leaked memory on a long-lived worker; found by review, fixed, see D175).
  Receipt scheme is `f"{message_id}:{delivery_count}"`; **this SDK's `delivery_count` is 0 on
  first delivery, not 1** — found live against the real namespace, not assumed (D174). Errors
  translate through new `adapters/azure/servicebus_errors.py`, mirroring `blob_errors.py`'s shape.
- **A 7th interface, `EventChannel`** (`interfaces/event_channel.py`) — **not in the original task
  text**, added because the old in-process `JobEventBus` cannot cross a process boundary, and
  splitting the worker out with nothing replacing it would make `/jobs/{id}/events` go silently
  and permanently dead the moment worker and API are actually separate processes.
  `LocalEventChannel`/`FakeEventChannel` are the old `JobEventBus` moved verbatim.
  `ServiceBusEventChannel` publishes to a topic and runs a background pump reading one fixed
  subscription — **the pump retries forever with capped backoff on any connection failure**
  (found by review: the first version let one transient network blip kill it silently and
  permanently, D176). `check_event_serialisable` (mirrors `JobQueue`'s own precondition) is
  enforced in every implementation's `publish`.
- **`worker.py`** — new standalone entry point (repo root, third edge alongside `cli.py`/
  `api/main.py`), runs the same `JobRunner` in its own process. **Deliberately never calls
  `adapters.events.start()`** — it only ever publishes, never subscribes; calling `start()` there
  too would open a second competing receiver on the same fixed subscription and silently steal
  roughly half of every job's progress events. Has SIGTERM/SIGINT shutdown handling with a
  Windows `ProactorEventLoop` fallback (`add_signal_handler` isn't implemented there).
- **`api/app.py::create_app`** gained `run_worker: bool = True` — default unchanged, every
  existing test still gets the in-process worker it always had. `api/main.py` reads
  `RUN_INPROC_WORKER` (default `true`) to pass this through.
- **`JobRunner._run_one` now has an outer safety net** (`api/runner.py`) — found by a second
  review pass, after the first four fixes were already verified: a `JobStore` failure in the
  prelude (or inside the graph-failure handler's own save call) used to escape with the Service
  Bus receipt never settled, stranding a locked message forever. Fixed with a thin wrapper that
  makes a best-effort `queue.fail(..., requeue=...)` on any escaping exception (D177).
  `_assemble_preview` moved to new `api/job_preview.py` in the same change, to stay under 200
  lines. Regression test: `tests/test_runner_receipt_safety.py`.
- **Two deliberate deviations from the original brief**, both load-bearing, both in D173:
  `ContainerAppsRenderBackend` **stays a stub permanently** — a 15-segment video makes ~45
  render-backend calls, so dispatching each one to the cloud individually would add tens of
  minutes of overhead for no gain; the correct move is containerising the **worker**, not the
  renderer (T35's actual job). **No Cosmos DB** — Blob keys scoped by owner (`jobs/{owner}/...`,
  T38) get per-user isolation with no new service; Cosmos returns when RAG needs a vector store
  (T30).

## Verified for real, not just by pytest

Two-terminal end-to-end run against the **real** `sbites-servicebus` Azure namespace (not a local
stand-in): `uvicorn api.main:app` with `RUN_INPROC_WORKER=false` in one process, `python worker.py`
in a completely separate one. A job was submitted via `POST /jobs`, dequeued and entirely driven by
the separate worker process, live progress arrived over `curl`-streamed SSE on the API process the
whole time (proving the cross-process channel actually works, not just the happy-path code), and
the job reached `status: succeeded` with a real `video_key`/`subtitles_key` — confirmed the
artifact endpoint 307-redirects to a real Blob SAS URL. Both background processes were stopped
cleanly afterward; `.env`'s `QUEUE_ENV`/`EVENTS_ENV`/`RUN_INPROC_WORKER` were restored to their
fast local-iteration defaults (`local`/`local`/`true`) once verification finished.

`pytest -m live tests/test_job_queue_parity.py tests/test_event_channel_parity.py` — 12/12,
green, against the real namespace (uses new `tests/azure_live.py::throwaway_queue`/
`throwaway_topic_subscription`, built on `azure.servicebus.aio.management
.ServiceBusAdministrationClient` — no new dependency beyond `azure-servicebus` itself, no ARM
credentials needed). Full offline `pytest` green throughout. `ruff check .` clean. Every `.py`
file under 200 lines. Both `core/` boundary greps clean (only two pre-existing comment mentions,
untouched by this session).

## Environment state

- **New Azure resource, provisioned this session:** Service Bus **Standard** SKU namespace
  `sbites-servicebus` in `resource-skill-bites`/eastus (Standard, not Basic — Basic has no topics,
  and the progress channel needs one). Queue `video-jobs` (5-min lock, 10 max deliveries — above
  `api.runner.MAX_ATTEMPTS=3`, so our own dead-lettering decides, not the broker's). Topic
  `job-events` with subscription `api`. Connection string is in `.env` (not `.env.example`) —
  `.env.example` documents the four new variables
  (`AZURE_SERVICE_BUS_TOPIC`/`AZURE_SERVICE_BUS_SUBSCRIPTION`/`EVENTS_ENV`/`RUN_INPROC_WORKER`)
  with placeholder/default values only.
- `RUNTIME_ENV=azure`. `.env` currently has `QUEUE_ENV=local`, `EVENTS_ENV=local`,
  `RUN_INPROC_WORKER=true`, `RENDER_ENV=local` — the fast local-iteration defaults, **not** what
  was used for the real end-to-end verification (see above). To repeat that verification: set
  `QUEUE_ENV`/`EVENTS_ENV` to `azure` (or unset both), `RUN_INPROC_WORKER=false`, then run
  `uvicorn api.main:app` (never `--reload` on Windows) and `python worker.py` in two terminals.
- New dependency: `azure-servicebus>=7.14.0` (installed in `.venv`, added to `requirements.txt`).
- Branch `cloud` created off `dev`, not yet merged or pushed — **the user has not yet been asked
  whether to merge or keep iterating here for T35/T38.**
- No stray backend/worker processes left running from this session's verification (both stopped
  and confirmed gone via `netstat`/`pgrep` before `.env` was restored). If a `uvicorn` or
  `worker.py` process from a much earlier session is still alive on port 8000 when you start
  work, it predates this session and was already stale when found here — kill and restart rather
  than trust it, per the existing gotcha below.

## Gotchas carried forward, still true

- **Never run `uvicorn --reload` on Windows for this app** — breaks every subprocess-shelling call
  non-deterministically (documented in `api/main.py`'s own docstring).
- **A backend started without `--reload` gives no signal that it's serving stale code.** Restart
  it by hand after any pipeline-relevant edit, every time — this session hit exactly this: a
  stray uvicorn process from many hours earlier was still holding port 8000 and had to be killed
  before a freshly-configured one could bind.
- **The frontend dev server can serve a stale/broken module across many HMR updates.** Prefer
  restarting with `.vite` cache cleared over debugging a symptom that doesn't match current source.
- **The `PostToolUse` quality hook only fires on Edit/Write, never on a raw Bash file write.**
- **An import added in one Edit/Write and only used in a later one gets silently stripped by the
  hook's `ruff --fix` in between** — hit repeatedly this session (`config.py`, `api/runner.py`,
  `tests/azure_live.py`, `adapters/azure/event_channel.py`, `adapters/local/event_channel.py`,
  `tests/fakes/event_channel.py`, `api/job_preview.py` all needed a stripped import re-added).
  Always re-check with `ruff check .` after a multi-edit sequence that touches imports, not just
  once at the end.
- **Opus plans, Sonnet builds — this is not self-enforcing.** Check the current-model line after a
  plan is approved and before the first `Write`/`Edit`/`Bash` of a build.
- **A silent, unexplained failure with no visible error is worse than a visible one, everywhere in
  this codebase.** T34 alone found three more instances of this exact lesson (D175's memory leak,
  D176's permanently-dead pump, D177's stranded queue receipt) — when adding a new failure path
  anywhere, ask what it looks like to someone with no access to the source when it breaks.
- **An SDK's documented behavior is a claim, not a fact, until checked against the real thing.**
  D174's `delivery_count` 0-vs-1-indexing is the latest instance of a lesson this project keeps
  re-learning (D89/D106/D109/D119/D124/D172).
- `graph_diagram` is deliberately excluded from `_SORTABLE_ITEM_FIELDS` and must stay that way.
- `logging.basicConfig` is called in `api/main.py`; a no-op once root handlers exist elsewhere.

## Known gaps / open questions, unresolved this session

- **No offline regression test for three of T34's four review-found fixes** — `_pump`'s
  backoff/reconnect behavior, the per-message renewer's cleanup-on-settle, and the `isinstance`
  body-decode fix are only exercised by the `-m live` parity suite (opt-in, deselected by
  default, happy-path only). `tests/test_azure_retry.py` already has the right pattern (stub the
  SDK client to provoke a failure offline) if a future session wants to close this cheaply.
- **The pump's retry loop cannot distinguish "transient" from "permanently broken"** (a deleted
  subscription, revoked credentials) — it retries at the 60s ceiling forever either way, logging
  an identical line each time. Accepted as-is per D176 (this project has no alerting configured
  anywhere else either), but worth knowing if a future on-call situation needs to tell the two
  apart.
- **T35's Dockerfile must fix a real portability bug before the image is trustworthy**:
  `adapters/local/hyperframes_process.py`'s stalled-process kill shells out to Windows
  `taskkill /T /F`; on Linux this silently no-ops (`except OSError: pass`), leaking orphaned
  Chrome/Node children on every render timeout. Found during T34 planning, not yet fixed —
  recorded in `tasks.md`'s T35 entry so it isn't lost.
- T18F (vision critique/revision loop, full validation render, pipeline speed) is still `todo`,
  unchanged. T18I is still `in progress`, unchanged, not investigated this session.
- Whether to merge `cloud` into `dev` now or keep both T35 and T38 on it before merging is an open
  question for the user, not decided here.
