# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

## What just happened

**T18M shipped in full, then a live user report chain surfaced (and fixed) three more real bugs
this session hadn't caught: SSE events never replay for a mid-job connection (D197), and two
separate, structurally different causes of a black waveform (D195, D198).** Full chain:
D191 (diagnosis, nothing built) → D192 (T18M items 1-3) → D193 (T40 diagnosis) → D194 (T18M item
4, CORS) → D195 (waveform dim-color) → D196 (full redeploy + a real `az acr build` bug) → D197
(SSE event history replay) → D198 (waveform under `prefers-reduced-motion`). Read D197/D198 in
full before assuming the waveform or progress panel is "fixed" — this took real, hard-won evidence
to actually pin down, twice, after two earlier attempts that looked complete but weren't.

### T18M (all four items done) — `tasks.md`'s own entry has the full list, D192/D194 the reasoning
Fallback rate 27% → 6.7% (measured), blank-stage entrance capped, fallback cards get real chips,
Blob CORS fixed. Not repeated here — see `tasks.md`.

### D197 — SSE event history replay (`cloud`-only; `dev` never had the architecture this needs)
`EventChannel` had no history at all — a browser tab that connects to a job already in progress
(a refresh, opening a job from the list) permanently missed everything before that connection: not
a rare race, the ordinary case. Added `EventChannel.history(job_id)`; `api/jobs.py` replays it
before tailing live events. Two real bugs `project-reviewer` caught before commit: events needed a
server-stamped `at` (a naive fix would've replayed history with every tick showing "just now"),
and a reconnect to a terminal job was double-sending the terminal ping. **This could only live on
`cloud`** — `dev` predates T34/T38A entirely and has no `EventChannel`/auth code; discovered via a
stash-pop conflict after first (wrongly) trying to build it on `dev`.

### D198 — waveform blank under `prefers-reduced-motion: reduce` (shared file, `dev` and `cloud`)
A *different* bug from D195 (which only fixed low-but-nonzero `fillPct` visibility). This one:
the reduced-motion path draws exactly once, ever — and any later `ResizeObserver` firing (DevTools
opening, a font loading) wipes the canvas via the `canvas.width` reassignment side effect, with
nothing left to redraw it. Found only by getting a real pixel read (`[0,0,0,0]`, fully
transparent) directly from the user's own failing browser after two of this session's own
Playwright repros against the same job both failed to reproduce it. `resize()` now redraws after
every resize in both motion modes.

## Environment state

- **Both `dev` and `cloud` pushed, in sync** (`dev` has no commits `cloud` lacks; `cloud` has
  infra-only commits on top, per the branch-split rule). Confirm with `git log origin/cloud..cloud`
  / `git log origin/dev..dev` (both should be empty) before assuming this is still true.
- **The DEPLOYED Azure stack reflects D196's redeploy — NOT D197 or D198.** Those two were built
  and pushed to git *after* the last live redeploy. The event-history replay and the
  reduced-motion fix are **not live** on `https://lively-meadow-05448450f.6.azurestaticapps.net`
  yet. A real redeploy (`scripts/deploy_cloud.sh rg-sbites-cloud eastus <email>`) is needed before
  a real user sees either fix on the actual deployed site.
- **Local dev servers from this session's testing:** the API (`uvicorn api.main:app --port 8000`,
  on `dev`'s code) may still be running (check `netstat -ano | grep :8000`) — the Vite dev server
  was stopped to free a file lock for `cloud`'s own `npm ci` and was not restarted. If picking this
  back up, confirm which branch is actually checked out before restarting either — **a running
  local server keeps serving whatever branch it started on, even after `git checkout` switches the
  repo to a different one.** This exact mistake cost real time this session (D198's own note).
- **`web/node_modules` reflects whatever branch's `package.json` was last `npm ci`'d against** —
  `cloud` has `@azure/msal-*` deps `dev` does not. Switching branches does not update
  `node_modules`; forgetting this produces confusing "module not found" errors that look like a
  real bug but are only a stale install.
- `RUNTIME_ENV=azure`, `QUEUE_ENV=local`, `EVENTS_ENV=local`, `RUN_INPROC_WORKER=true` (local),
  `RENDER_ENV=local` — all unchanged. Local dev talks to real Azure Blob Storage even locally (not
  a local-disk stub) — confirmed useful this session for testing the CORS fix without a full
  cloud redeploy.
- `RENDER_MAX_CONCURRENCY=1` — still unmeasured/untuned, still T39, still nobody's task.
- **A real, recurring operational hazard this session hit four separate times:** running a local
  Vite dev server and `scripts/deploy_cloud.sh`'s own `npm ci` in the same `web/` directory at the
  same time causes a Windows file-lock (`EPERM`/`unlink`) on native `.node` binaries. **Stop any
  local dev server before running the deploy script, every time**, not just when it happens to
  collide.

## Known gaps / open questions, unresolved this session

- **Redeploy needed for D197/D198 to reach the live site.** See above — this is the single most
  actionable next step if the goal is the live user experience, not just the source tree.
- **Confirm playback in an actual signed-in browser session** — T18M item 4's CORS fix was
  verified via direct HTTP requests, never by actually pressing play as a signed-in user. Still
  true, still worth checking once a redeploy happens.
- **T40 (`graph_diagram` deep-chain layout capacity)** — diagnosed exactly (D193), not built. Real
  scope: a new zigzag/serpentine layout mode in a heavily-shared, five-times-hardened template.
- **T39 (Dockerfile `USER`, `RENDER_MAX_CONCURRENCY` tuning)** — still nobody's task, deferred
  three times now plus mentioned again this session without being scheduled.
- D141's `Copy Link` UI feature — still not redesigned, still not blocking anything.
