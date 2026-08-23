# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-23 · after T13_

---

## Where we are

**The interface/adapter boundary is complete and wired.** All six interfaces exist; `Storage`,
`SkillRegistry`, `JobQueue` and `RenderBackend` each have a real local and a real Azure
implementation (the latter two Azure-side stubbed until T34/T35, signature-matched); `LLMProvider`
and `TTSProvider` are Azure-only for now. `config.py` is the resolver: `build_adapters()` reads
`RUNTIME_ENV` and returns a full six-adapter `Adapters` bundle on `azure`, and `close_adapters()`
owns their lifetimes on shutdown.

**Done:** T1-T9 (iterations 0-2 partial), T11 (storage adapters + Blob skill registry), T12 (local
render backend + job queue, Azure stubs — rescoped, see decisionlog D59), **T13** (config resolver).
**In progress, unclaimed:** **T10** — Azure TTS is done and tested; Ollama/Kokoro (local
`LLMProvider`/`TTSProvider`) still don't exist and no task currently builds them.
**Next:** **T14** — LangGraph skeleton. Its dependencies (T6, T13) are both `done`.

## What T13 produced

`config.py` (199 lines, repo root) — the one module CLAUDE.md permits to name a concrete adapter
class:

| Symbol | Does |
|---|---|
| `Adapters` | Frozen dataclass, six fields (`llm`, `tts`, `storage`, `skills`, `queue`, `render`), one per interface ABC |
| `build_adapters(env=None)` | Reads `RUNTIME_ENV` (`os.environ` by default, injectable for tests), returns a full `Adapters` on `azure`; **raises on `local`** — see below |
| `close_adapters(adapters)` | Awaits `.aclose()` on whichever of the six resolved instances define one (`getattr` guard), best-effort via `asyncio.gather(..., return_exceptions=True)` |
| `_storage` / `_skill_registry` / `_job_queue` / `_render_backend` | Real local **and** real Azure branches — both work today |
| `_llm_provider` / `_tts_provider` | Real Azure branch; local branch raises `RuntimeError` naming Ollama/Kokoro |

**`RUNTIME_ENV=local` is deliberately incomplete (D64, user decision).** `build_adapters()` raises
immediately under `RUNTIME_ENV=local` — before calling any of the four working local builders —
naming that Ollama and Kokoro don't exist and pointing at decisionlog D58/D59. This was one of
three options on the table (the others: signature-matched stub adapters à la T12, or narrowing
`config.py`'s scope to skip `LLMProvider`/`TTSProvider` entirely); the user chose not to write any
Ollama/Kokoro code, even raise-only, until a task actually claims T10. The four other builders are
proven correct directly (`tests/test_config.py::test_each_local_builder_returns_the_local_adapter`)
even though `build_adapters()` can't expose them under `local` yet. **Whichever future task builds
Ollama/Kokoro only needs to fill in `_llm_provider`/`_tts_provider`'s local branch and delete
`build_adapters()`'s upfront raise** — nothing else in `config.py` changes.

**D55's `aclose()` question is closed (D65).** `config.py` owns the four adapters' off-contract
`aclose()` (`AzureOpenAILLMProvider`, `BlobStorage`, `BlobSkillRegistry`,
`PlaywrightHyperFramesRenderBackend`) via `close_adapters()`, generic over which four via `getattr`
so a real `ServiceBusJobQueue`/`ContainerAppsRenderBackend` growing one at T34/T35 needs no edit
here. It is best-effort — one adapter's `aclose()` raising does not stop the rest from closing —
after `project-reviewer` caught a first version that stopped at the first failure, which would leak
every later adapter once T19's FastAPI lifespan is the real caller.

**`.env.example` grew two placeholder groups** the stub constructors need real args for:
`AZURE_SERVICE_BUS_CONNECTION_STRING`/`AZURE_SERVICE_BUS_QUEUE` (unused until T34) and
`AZURE_RESOURCE_GROUP`/`AZURE_CONTAINER_APPS_ENVIRONMENT` (unused until T35). Both read with
`default=""` rather than `required=True` in `config.py`, since the stubs never dial out.

**Verify at any time:**

```bash
pytest                        # full suite, offline, no network — includes tests/test_config.py
ruff check . && ruff format --check .
```

## Next task: T14 — LangGraph skeleton

Graph state, checkpointing, per-segment fan-out, and resume-after-failure, scoped strictly to
`core/graph/` (the only place `langgraph` may be imported). Depends on T6 (done) and T13 (done) —
**ready to plan with no blockers.**

**What T14 should know going in:**

- **`config.py` exists now, but nothing calls it yet.** T14's nodes call interfaces, the same as
  every other piece of `core/` — whatever wires an `Adapters` bundle into the graph's runnable
  config is T14's own design decision, not something already decided for it.
- **`build_adapters()` will raise if anything in T14's local test path tries `RUNTIME_ENV=local`.**
  Tests should keep exercising the graph against `tests/fakes`, not `config.py`'s local branch,
  until T10 lands — this is the same reasoning D25/D59 already established for staying
  Azure-focused on the live path.
- **D47's disk-I/O-under-concurrency question is still unmeasured, now for the third time flagged
  as "next task's job."** `DiskStorage`/`DiskSkillRegistry` do synchronous I/O inside their
  `async def`s. T14 is explicitly named in D47 and T12's carry-forward as the first task that runs
  real concurrent jobs (per-segment fan-out) against local storage. **Measure this during T14,** or
  say explicitly why it was skipped again.
- `QueuedJob.attempt` is what `StructuredOutputError`'s "retry, but bounded" needs (D24's open
  item) — T14 is named as the owner of that cap.

## Environment state

| | |
|---|---|
| Models | Opus plans, Sonnet builds and reviews |
| `RUNTIME_ENV` | **`azure`** in both `.env` and `.env.example` (D25) — now genuinely wired: `config.build_adapters()` reads it for real |
| `.env` | **Exists and is filled in.** Gitignored. Never commit it. **Not yet updated with the two new placeholder groups** `.env.example` gained this session (`AZURE_SERVICE_BUS_*`, `AZURE_RESOURCE_GROUP`/`AZURE_CONTAINER_APPS_ENVIRONMENT`) — harmless gap today since nothing reads `.env` directly except `config.py` via `build_adapters()`, which defaults them to `""` |
| Azure sub | `d4a261bd-760c-41bd-9e22-ef58e2329ce0`, `az login` done |
| Azure OpenAI | `skill-bites` (eastus) · deployment `gpt-5.4-mini` 2026-03-17, DataZoneStandard (D49) · api-version `2024-10-21` |
| Azure Speech | `skill-bites-tts` (eastus), S0 (D48) · voice `en-US-AvaMultilingualNeural` |
| Azure Storage | `sbitesartifacts25817` (eastus) · containers `explainer-artifacts`, `runtime-skills` |
| Python | 3.11.0, venv at `.venv/`. Use `.venv/Scripts/python.exe` explicitly |
| Node | 24.16.0 · npm 11.13.0 · ffmpeg/ffprobe 8.1.1 on PATH |
| HyperFrames CLI | Installed — 0.8.10, via `npx hyperframes`. Chrome Headless Shell cached at `~/.cache/hyperframes` |
| Playwright browsers | Installed — both `chromium-1234` *and* `chromium_headless_shell-1234` at `%LOCALAPPDATA%\ms-playwright` |
| Ollama, Kokoro | **Still not installed. Deliberately deferred (D59, reaffirmed D64)**, not forgotten |
| Git | on `master`. **Nothing from T1 onward pushed or committed yet** — every task since T1/T2's two commits is still working-tree state |

## Before the next session

Nothing blocking. T14 is `core/graph/` design work against the already-`done` T6 fakes; it does not
need `.env`, Azure credentials, or any new install. If T14's planning session decides to add the two
new `.env.example` placeholder groups to the real `.env`, that's a one-minute copy — not required
for anything to work, since `config.py` defaults them to `""`.

## Known gaps and open questions

**New in T13:**

- **`RUNTIME_ENV=local` cannot build a full adapter set** — `build_adapters()` raises by design
  (D64) until a future task builds Ollama/Kokoro. Not a bug; see "What T13 produced" above for the
  exact seam a future task fills in.
- **`.env` itself was not updated with the two new placeholder var groups** — see Environment state
  above. Low priority; `config.py` tolerates their absence.

**Carried forward, unchanged:**

- **D47's disk-I/O-under-concurrency question is still unmeasured**, now flagged a third time as
  T14's job specifically (see "Next task" above) — T12's asyncio `JobQueue` made it measurable and
  T14's per-segment fan-out is what will actually stress it.
- **The composition-directory-layout assumption is unverified** (`hyperframes_cli.py` assumes one
  composition per directory, named `index.html`). T17 is the first task that generates composition
  files and picks a real layout — check this assumption then.
- **`FRAME_BUDGET` is mistuned and cannot be fixed yet** (D32). Owned by T16, once real measured
  durations exist.
- **The `outline` pack may need a `1.1`.** T8's live call rated all three segments importance 5.
  T15 owns this.
- **`core/tier_resolver.py` is at 198 of 200 lines.** The seventh intent forces a split.
- **No coverage gate exists (D42).**
- **`FakeRenderBackend.render` writes placeholder bytes, not a real MP4.** T18's mux work must run
  against the real local adapter, which exists (`PlaywrightHyperFramesRenderBackend`).
- **`Segment.slots` is an untyped dict** (D29). Revisit at T24.
- **No family for "our own code judged this invalid" errors** beyond `CompositionInvalid` itself
  (D23). Decide at T17.
- **`StructuredOutputError` cannot say "retry, but bounded."** T14 owns this, via `QueuedJob.attempt`.
- **Scope: 35 tasks across 8 iterations**, and the local stack's priority is now unsettled a second
  time over (T12's rescoping, and now T13's D64) — worth confirming with your manager before
  iteration 4.

## Gotchas worth remembering

**New in T13:**

- **A `PostToolUse` formatting hook can silently strip an import that isn't used *yet*.** Adding an
  import in one edit and its first use in a later edit risks the hook's autofix (`ruff --fix`-style)
  removing the "unused" import in between. Add an import in the same edit as its first use — this
  is the same lesson as the existing "quality hook autofixes on write" gotcha below, hit again in a
  new shape this session (`asyncio`/`logging` added before their uses, silently stripped, caught by
  the next `pytest` run rather than by review).
- **`getattr(instance, "method_name", None)` is the right shape for "does this adapter have an
  optional lifecycle hook," and it composes cleanly with `asyncio.gather(..., return_exceptions=True)`
  for "close everything, best-effort."** Worth reusing verbatim if a future interface ever grows a
  second off-contract hook.

**Carried forward:**

- **Check the *SKU's* quota, not the model's availability** (D49).
- **An SDK that "reports failures as results" can still raise** (D57).
- **The quality hook autofixes on write** — add an import in the same edit as its first use.
- **Windows path semantics**: a trailing dot is stripped on existence checks but not on directory
  enumeration (D46).
- **A generator raises where it is iterated, not where it is called** — wrap both the call and the
  iteration in one `try`.
- **A validation rule tested on one method of six is tested nowhere** (D39).
- **`project-reviewer` is worth running and worth checking in both directions** — catches real bugs
  across this project's history (T12's three, T13's `close_adapters` best-effort gap plus two minor
  validation holes). **When re-running review after fixes, ask for a fresh full read, not just
  verification of the named fixes.**
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
