# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-09-04 · after T24-T28 (Iteration 5: the React frontend) + T36 (SCORM export,
new task), built in one combined session by the user's own choice · reviewed once by
`project-reviewer`, two real bugs found and fixed (D138) — full account below_

---

## Where we are

**Built the entire React frontend in one session — T24 scaffold through T28 error states, plus a
new T36 (SCORM 1.2 export) added mid-session at the user's explicit request.** Full reasoning for
every non-obvious call: decisionlog D130-D137.

**Done:** T1-T18, T18A-E, T19-T23, **T24, T25, T26, T27, T28, T36**.
**Still paused, untouched this session:** T18F and T18E's three real-render findings (inter-
annotation collision, a version-number-driven `TIMELINE` blind spot, combined-effects layout
collisions in a dense `GRAPH_DIAGRAM`) — exactly where the T19-T23 session left them.
**`feature/scene-composition`'s T18I work-in-progress was committed as an explicit WIP commit
(`91f57ef`) and pushed at the start of this session**, so it is recoverable, but it is **not**
reviewed, not checkpointed, and not marked done in `tasks.md`. Still unmerged into `dev`.

**Next: genuinely open.** Iteration 5 is a clean stopping point. Candidates, not a recommendation
among them: resuming T18F/T18E's findings, T29 (document upload, RAG), or T34/T35 (Service Bus /
Container Apps — Iteration 5.5, scheduled to run before Iteration 6 per `tasks.md`). Worth a real
conversation with the user.

## What T24-T28 + T36 built

**`web/`** — new Vite + React 19 + TypeScript 5.9 + Tailwind v4 app, `npm install`ed and building
clean. Full architecture in `decisionlog.md` D130-D131; the short version:

```
web/src/
  api/          openapi-fetch client + generated types. The ONLY layer allowed to import them.
  adapters/     job-adapter.ts, stage-adapter.ts, scene-adapter.ts -- DTOs in, domain/ types out.
  domain/       job.ts, stage.ts, scene.ts, tier.ts, intent-label.ts, artifact-links.ts.
  components/   design-system primitives (Button, Card, Pill, TierBadge, Dialog, DropdownMenu, ...)
  features/     jobs/, submission/, dashboard/, progress/, segments/, player/, errors/, achievements/
  routes/       LandingPage, DashboardPage, JobDetailPage, LibraryPage, NotFoundPage
```

**The seam is mechanically enforced**, not a convention: `eslint.config.js`'s `no-restricted-
imports` bans `**/api/*` and `openapi-fetch` from `features/`/`components/`/`routes/`. It caught
its own violations live during the build (`use-jobs.ts`, `use-job.ts`, `use-job-stream.ts`,
`JobDetailPage.tsx` all initially imported `api/` directly) — fixed by pushing api-calling +
mapping composition into `adapters/`.

**`Segment.scene` renders generically** (`adapters/scene-adapter.ts` + `SceneTree.tsx`) — no
per-block-type components, ever. `scene-adapter.test.ts` proves it against an entirely invented
future scene shape. This is the actual, tested answer to "T18 must not force frontend changes."

**Backend additions**, all new, all tested (see `tests/test_api_*.py`, `tests/test_byte_range.py`,
`tests/test_scorm_package.py`):
- `api/main.py` — CORS middleware, `WEB_ORIGINS` env var.
- `api/runner.py` / `api/jobs.py` — a `terminal: bool` field on every SSE status event (D135.2),
  and `VideoJob.error` (`core/models.py`), truncated to 500 chars, cleared on resume.
- `api/byte_range.py` + `api/artifact_response.py` (split out of `api/artifacts.py` to stay under
  the 200-line ceiling) — HTTP Range/206 support. `<video>` seeking now works against local disk.
- `api/segments.py` — `GET /jobs/{id}/segments/{i}/{audio,clip,scene}`.
- `scorm/manifest.py` + `scorm/package.py` + `api/scorm.py` — real SCORM 1.2 packages, `GET
  /jobs/{id}/scorm`.
- `scripts/dump_openapi.py` — offline OpenAPI schema dump (no live server, no Azure creds; D132).
- `scripts/serve_fake.py` — the fast frontend dev loop: real FastAPI app against `tests/fakes/*`
  under uvicorn, a whole job completes through real ffmpeg in seconds. Its
  `DynamicSegmentLLMProvider` (D134) makes every real duration option actually work, not just the
  one the pytest fixtures happen to be tuned for.
- `scripts/hook_asset_quality.py` — fixed a real bug (D135): `format_frontend` ran prettier/eslint
  from the wrong cwd and silently formatted nothing, ever, since the hook was first written.

**40 new backend tests, 26 new frontend tests (Vitest).** Full pytest suite: 724 passed, 1 skipped.
Frontend: `tsc -b --noEmit` clean, `eslint .` clean, `npm run build` succeeds (503 KB JS / 163 KB
gzip — see "Known gaps").

## Two more real bugs, found by `project-reviewer` — neither would have been caught by the
## browser testing below

Full account: decisionlog D138. Both fixed and pinned by new regression tests before this
checkpoint.

1. **(High) A job mid-automatic-retry was indistinguishable from a genuinely dead one to any
   consumer that isn't a live SSE subscriber.** `api/runner.py` persisted `JobStatus.FAILED` for
   *every* failed attempt, including ones about to be auto-requeued — so a fresh page load, a
   poll, or (most seriously) `resume_job`'s own guard all saw a plain "failed" job with a live,
   working Resume button. Clicking it during that window would have enqueued a second, redundant
   run of the same job (`LocalJobQueue`/`FakeJobQueue` don't dedupe by `job_id`). **Fixed:** a
   requeued attempt now persists `QUEUED`, not `FAILED` — mirrors what `resume_job` already sets
   on an explicit resume, and makes every downstream consumer correct with no frontend change.
2. **(High) Stored XSS in the SCORM launch page.** `scorm/package.py::_launch_html` interpolated
   `title` (`job.topic`, free user text) into `<title>{title}</title>` unescaped, while
   `manifest.py` already escaped the identical value correctly. A topic containing
   `</title><script>...</script>` would execute the moment `launch.html` was opened. **Fixed:**
   `html.escape(title)`, same treatment `manifest.py` already gives it.

Neither would have surfaced from driving the app happily through its golden path in a browser —
both needed someone reading the actual state-transition logic and the actual HTML-generation code.
The two bugs below, conversely, needed exactly the opposite: they only surfaced from real browser
navigation, not from reading code or curling endpoints. Both kinds of verification mattered.

## Two real bugs found only by testing in an actual browser — read before assuming curl-level
## verification is enough for this app

Both are recorded in full in decisionlog.md (D133, D134); short version:

1. **The frontend's own `/jobs` route collided with the backend's identical `/jobs` API path**
   through the Vite dev proxy. A full-page navigation to the frontend's `/jobs` page returned raw
   backend JSON instead of the React dashboard — invisible to curl, invisible to client-side
   `<Link>` navigation, only visible on a real page load. Fixed by scoping the dev proxy to `/api`
   (stripped before forwarding), zero backend changes.
2. **`scripts/serve_fake.py`'s original fake LLM was seeded for exactly one duration** (the pytest
   suite's own 100s/4-segment fixture). Every one of T25's real duration chips (3/7/10 min → 6/15/
   21 segments) dead-lettered against it. Fixed by reading the segment count back out of the
   outline prompt's own stated text.

Both were caught by actually driving the app in Python Playwright (already a project dependency;
no browser MCP was connected this session — see "Environment state"), submitting through the real
`PromptComposer` form, and screenshotting the result. **Curl-only verification would have missed
both.**

## Verify at any time

```bash
pytest                                    # offline, no network -- 724 passed, 1 skipped
ruff check . && ruff format --check .     # clean
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # empty (one
                                           # docstring-text hit in node_timing.py, not a real import)
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # empty

cd web
npx tsc -b --noEmit && npx eslint . && npx vitest run && npm run build     # all clean

python -m scripts.dump_openapi && cd web && npx openapi-typescript ./openapi.json -o \
  ./src/api/schema.d.ts && git diff --exit-code openapi.json src/api/schema.d.ts   # drift alarm

python -m scripts.serve_fake                      # fake backend, port 8000, no Azure spend
cd web && npm run dev                              # real frontend, port 5173, proxies /api -> :8000
```

## Uncommitted right now — read before running `git status` and assuming something is wrong

**Nothing from this session is committed yet** (offered to the user at the end, not pushed
automatically, per standing convention). `git status` will show:
- All of `web/` (new, untracked) except `node_modules`/`dist` (gitignored).
- New/modified files under `api/`, `scorm/`, `scripts/`, `core/models.py`, `tests/`.
- `.impeccable/config.json` (shared, should be committed) — `.impeccable/config.local.json` and
  `.impeccable/hook.cache.json` are now gitignored (added this session).
- `.claude/skills/impeccable/` and four `.claude/agents/impeccable-*.md` — installed this session
  via `npx impeccable install`, per the user's own decision.
- Two unrelated screenshot PNGs at the repo root (`Screenshot 2026-08-24 *.png`) — pre-existing,
  left untouched, not part of any task.

## Environment state

| | |
|---|---|
| Models | Session started on Opus (planning), switched to Sonnet for the build per the mandatory self-check CLAUDE.md requires — confirmed by the user running `/model sonnet` before the first Write/Edit. **Opus is still this user's saved default for new sessions** — flagged to the user; worth running `/model sonnet` again as the default if this keeps recurring. |
| Browser automation | **No browser MCP was connected this session** (`playwright` MCP failed with `CONNECT_TIMEOUT`; no `claude-in-chrome` tools registered). All real-browser verification (the two bugs above, every screenshot) used **Python Playwright directly** — already a project dependency (`requirements.txt: playwright>=1.49.0`), its Chromium binary was already installed on this machine. Worth fixing the MCP connection before the next frontend-heavy session; the Python-Playwright workaround is not as convenient as the MCP tool would be. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100), unchanged. |
| `FRAME_BUDGET` / `FPS` | `9500` / `24`, unchanged. |
| `WEB_ORIGINS` | New, `.env.example` — defaults to `http://localhost:5173`. |
| Git | `dev`, fast-forwarded to `origin/dev`'s `5fa267a` at session start, then this session's work built on top, **uncommitted**. `feature/scene-composition` got one new WIP commit (`91f57ef`, pushed) this session before the switch to `dev`. |
| Azure spend | **None this session.** Everything — all five tasks' DoDs, both real bugs — was verified against `tests/fakes/*` via `scripts/serve_fake.py`. No real `RUNTIME_ENV=azure` render was run. Worth doing once before the next `/costs` check, per the original plan's own verification strategy (one real end-to-end run was scoped but not yet executed — see "Known gaps"). |
| Node | v24.16.0 / npm 11.13.0, confirmed working. `web/`'s own `package.json`/lockfile is fully independent of the root's (`hyperframes`-only) `package.json` — no npm workspaces, by design (D-adjacent to D130). |

## Known gaps and open questions

**New, found by this session, not previously scoped anywhere:**
- **No real `RUNTIME_ENV=azure` end-to-end run happened this session.** The original plan scoped
  one (to exercise the SAS-redirect branch of `_serve`, real timezone rendering, real
  `word_marks`) — cut for time. `tests/fakes/*` (memory:// storage) never exercises the `http(s)://`
  redirect branch of `api/artifact_response.py::serve_artifact`. Worth doing before trusting that
  branch in production.
- **`web/`'s production bundle is 503 KB JS / 163 KB gzipped** — over the plan's ~120 KB estimate,
  mostly `motion` + three Radix packages + TanStack Query + Router. Acceptable for an internal
  enterprise tool per the plan's own risk note, but flagged rather than silently accepted; code-
  splitting (`vite build`'s own suggestion: dynamic `import()`) is the lever if it ever matters.
- **Per-segment narration audio is served by reconstructing `SEGMENT_AUDIO_KEY` in `api/
  segments.py` rather than reading a stored field** — there is no `audio_key` on `Segment`, so the
  route relies on the same deterministic key format `core/graph/nodes/synthesize.py` writes to.
  Correct today; would break silently if that key format ever changed without updating both
  places. Worth a shared constant if T18 ever touches it.
- **Playwright MCP is still failing to connect** (see "Environment state") — not investigated this
  session, just worked around.

**Carried forward, unchanged:**
- **T18F and T18E's three findings** — see "Where we are" above.
- **No coverage gate exists (D42).**
- **T10 stays `in-progress`, unclaimed.** Ollama/Kokoro still don't exist.
- **`RENDER_MAX_CONCURRENCY=2`** was picked from one machine's `hyperframes doctor` output, not
  measured under real concurrent load — still open, unchanged since T18A.
- **`hyperframes check` is still non-deterministically flaky at times (D96)** — re-run before
  trusting a single red result.
- **`pipeline-debugging`'s documented artifact layout is stale** (flagged by T18D, not yet fixed).
- **`api/runner.py::WORKING_ROOT` has no cleanup** — unchanged since T19-T23, every job still
  leaves a permanent (gitignored) directory behind.
- **Scope: 37 tasks across 8 iterations, plus T18A-F** (T36 added this session).

## Before the next session

**`project-reviewer` has run** (found and this session fixed two real bugs — D138, both sections
above). Nothing outstanding from the review gate itself.

**Decide what's next** — see "Where we are." No recommendation among T18F/T18E, T29, or T34/T35.

**Consider fixing the Playwright MCP connection** before the next frontend-heavy session — the
Python-Playwright workaround worked but a connected MCP tool would be materially more convenient
for future UI verification.

**`feature/scene-composition` is still unmerged into `dev`**, ahead of it by the T18I WIP commit
from this session's start — still the user's own decision, not automatic as part of any
checkpoint.

## Gotchas worth remembering

**New this session:**
- **A frontend's own client-side routes can collide with its backend's API routes when both are
  proxied from the same dev-server origin.** If `/jobs` (or any other path) exists as both a React
  Router route and a backend REST path, a bare-prefix dev proxy will swallow real browser
  navigations to the frontend route. Namespace API calls under a distinct prefix (`/api`) in the
  proxy, not in the backend's own route paths (see D133) — client-side `<Link>` navigation will
  never reveal this; only a full page load (deep link, refresh, or a real browser test) will.
- **`npm run <script>`'s `cd ..` works fine cross-shell (bash/cmd), but a hook or hand-run command
  that shells out to a project-relative binary (`npx --no-install X`) resolves `node_modules/.bin`
  from **cwd upward, never downward**.** If a script lives at the repo root but the binary is
  installed in a subdirectory's `node_modules` (`web/node_modules`), the caller must `cd` into
  that subdirectory first, or the resolution silently fails with no visible error (D135's
  `hook_asset_quality.py` bug).
- **A pydantic model's prompt-embedded requirement (e.g. `f"Produce exactly {N} segments"`) is a
  legitimate signal a test fixture can read back**, rather than needing the fixture to be told the
  count out-of-band. Used to make `scripts/serve_fake.py` duration-agnostic (D134) without
  touching any shared, reviewed test fixture.
- **Claude Code's PostToolUse hooks appear to inherit the Bash tool's *persisted* working
  directory, not always the project root** — a `cd web && npm install` in one Bash call left the
  next Edit's hook invocation looking for `scripts/hook_boundary.py` inside `web/scripts/` and
  failing. `cd` back to the repo root (or use a subshell `(cd web && ...)`) before any Edit/Write
  call, not just before Bash calls.

**Carried from T19-T23, still true:**
- **`AsyncSqliteSaver.from_conn_string(path)` creates `path` on disk the instant it connects, not
  when a checkpoint is first written.** Ask the checkpointer (`saver.aget_tuple(config)`), never
  check file existence.
- **Every real invocation of this graph must pass `durability="sync"` explicitly** (D68/D126).
- **`Storage.url()`'s scheme is the only safe way to branch redirect-vs-stream at the API layer**
  (D128) — `startswith(("http://", "https://"))`, not `== "file://"`.

**Carried from T18E and earlier, still true:**
- **`FakeLLMProvider`'s strict-FIFO queue breaks under real concurrency with mixed schema types**
  — `PhaseQueueLLMProvider` (matches by type, not position) is the fix pattern.
- **The quality hook strips an import added before its first use** — add the import in the same
  tool call as its first real usage. Confirmed again this session (`api/app.py`'s `segments_router`
  import was silently stripped twice before switching to one complete `Write`).
- **A GRAPH_DIAGRAM node div's CSS center is not its visible marker circle's center.**
- **`[await x() for i in xs]` inside a list comprehension is sequential, not concurrent.**
- **`hyperframes lint`'s severity levels are meaningful** — only `[error]` blocks a render.
- **The hooks fire on `Write|Edit`, not on Bash heredocs.**
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST if a hit looks
  ambiguous.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
