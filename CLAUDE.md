# s_bites — Prompt-to-Explainer-Video Pipeline

Topic in ("teach me about SQL injection") → narrated ~7-minute explainer MP4 out. LLM writes the
outline and script, TTS narrates, HTML/HyperFrames renders visuals, ffmpeg muxes. FastAPI backend,
React frontend, LangGraph orchestration.

A POC that must become an enterprise product **without a rewrite**.

---

## The one rule

**`core/` knows nothing about the outside world.** No SDK imports, no vendor names, no filesystem
assumptions. Business logic calls an interface; an adapter implements it; `config.py` picks which.

This is enforced mechanically by a `PreToolUse` hook — writes to `core/` that introduce
`adapters.`, `azure`, `openai`, `huggingface`, `ollama`, or `playwright` imports are **blocked**.
If you find yourself fighting the hook, the design is wrong, not the hook.

`langgraph` is the single exception, permitted **only** under `core/graph/`.

Verify at any time:
```bash
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # must be empty
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # must be empty
```

## Layout

| Path | Holds | Rules |
|---|---|---|
| `core/` | Business logic: outline, scripting, scene_author, tier_resolver | Interfaces only |
| `core/graph/` | LangGraph state, nodes, graph wiring | The only place `langgraph` may appear |
| `core/tier_resolver.py` | Pure function: segments → render tiers | stdlib + `core.models` only. No I/O, ever |
| `interfaces/` | Six ABCs — the contracts | No implementations, no vendor types in signatures |
| `adapters/local/` | Ollama, Kokoro, disk, asyncio pool, Playwright+HyperFrames | |
| `adapters/azure/` | Azure OpenAI, Speech, Blob real; Service Bus + Container Apps stubbed | |
| `rendering/` | One module per tier + Jinja templates | |
| `mux/` | ffmpeg subprocess calls | Never moviepy |
| `runtime_skills/` | Versioned prompt packs loaded at **runtime** by the pipeline | Not `.claude/skills/` |
| `.claude/skills/` | **Build-time** skills for Claude Code | Not `runtime_skills/` |
| `api/`, `web/` | FastAPI backend, React frontend | |
| `config.py` | The ONLY module naming concrete adapter classes | |

## Code conventions

- **200-line ceiling on every `.py` file.** Enforced by hook. When you hit it, split by
  responsibility — do not compress.
- **No `utils.py`, `helpers.py`, `common.py`, or `misc.py`.** Ever. Those become the drawer where
  boundary violations hide. Name modules for what they do: `tier_resolver.py`, `ffmpeg_mux.py`.
- Directories are plural nouns for collections (`adapters/`, `nodes/`); modules are singular and
  behavioral.
- No bare `except:`. Catch what you can handle.
- Retry, backoff, and rate limiting live in **adapters**, never in `core/`.
- Type hints on every public function. Pydantic models for anything crossing a boundary.

### Working with the quality hooks, not against them

Every `Write`/`Edit` to a `.py` file triggers a `PostToolUse` hook (`scripts/hook_py_quality.py`)
that runs `ruff check --fix` and `ruff format` immediately, automatically. This is deliberate and
should stay on — it is what keeps the codebase clean without anyone remembering to run it — but it
has two consequences worth knowing before they cost a retry:

- **An import added in one tool call and used only in a later one gets silently stripped before
  that later call ever happens.** Add an import in the *same* `Write`/`Edit` as its first real
  usage, never split across edits.
- **A file the hook just reformatted can make your next `Edit`'s `old_string` stop matching** —
  whitespace/import-order changes you didn't ask for. Treat any file a hook touched as stale:
  re-read it (or trust the `PostToolUse hook additional context` notice you're given) before
  editing that region again, rather than reusing a string you composed before the hook ran. For a
  new file with several imports and their first usages arriving together, prefer one `Write` with
  the complete content over several incremental `Edit`s.

If you find yourself fighting this by shelling out to `sed`/`Bash` to bypass the hook, that is a
sign the edit should have been one larger `Write` instead of several small `Edit`s — not a reason
to route around the hook itself.

## Invariants that break the product if violated

1. **TTS runs before scene authoring.** Scene timing derives from *measured* `duration_ms`, never
   an LLM estimate. Enforced structurally: `scene_author` takes `duration_ms` as a required
   parameter, so calling it early is a type error. This is the #1 source of A/V drift.
2. **The LLM never writes HTML.** It returns a strict-`json_schema`-validated slot payload; Jinja
   templates own all markup and all HyperFrames `data-*` attributes.
3. **Per-segment mux, then concat.** Each segment becomes a self-contained MP4 at exactly its audio
   duration before joining. Drift cannot accumulate.
4. **Adapter parity.** Every interface's local and azure implementations must match in signature
   *and* semantics — return types, error behavior, units.
5. **The frontend (`web/`) is structurally insulated from T18.** T18 is the open-ended, repeatedly
   -revisited iteration on scene-authoring internals — layouts, block types, annotation overlays,
   Jinja templates. None of it can force a `web/` change, by construction, not by discipline:
   - `Segment.scene` is `dict[str, Any]` on the backend (`core/models.py`, D29's pattern) and is
     rendered by a **generic, data-driven JSON tree** on the frontend
     (`web/src/adapters/scene-adapter.ts` + `web/src/features/segments/SceneTree.tsx`) — never
     per-block-type React components. A new block type, a restructured layout, or a field that
     doesn't exist yet all render correctly with zero frontend changes; a decoupling test
     (`scene-adapter.test.ts`) proves this against an entirely invented future scene shape.
   - The frontend's own architectural seam (`web/src/{api,adapters,domain,features}/`) is
     mechanically enforced by an ESLint rule (`web/eslint.config.js`'s `no-restricted-imports`),
     not a convention — `features/`/`components/`/`routes/` cannot import the generated API client
     directly, so a backend contract change surfaces as a `tsc` failure in exactly one file
     (`adapters/job-adapter.ts`'s explicit-destructure mapping), never a silent break elsewhere.
   - **What T18 *can* still affect, deliberately and narrowly:** `VisualIntent` labels
     (`web/src/domain/intent-label.ts`) and tier copy (`web/src/domain/tier.ts`) are presentational
     metadata the frontend owns, with a fallback for any value it doesn't recognize yet — a new
     `VisualIntent` member renders as a title-cased label immediately, no frontend task required,
     though a nicer label is a one-line optional follow-up.
   - **A T18 session can treat this as a standing guarantee**: touching `rendering/`,
     `core/block_types.py`, `core/scene_schemas.py`, or the block-authoring templates never
     requires a corresponding `web/` change, and does not routinely need review from a
     frontend-focused session. Full account: decisionlog.md D130-D131, D144.

## Build loop

Work proceeds task by task from `tasks.md`, one task per session:

1. `/build-task Tn` — loads `handoff.md` + `decisionlog.md` + the task, presents a plan, stops.
2. Agree and exit plan mode; the build runs in auto mode.
3. Run the `project-reviewer` agent.
4. `/checkpoint` — reviewer gate → append `decisionlog.md` → rewrite `handoff.md` → mark done →
   reindex RepoWise → offer to push.

### Which model runs what

**Opus plans. Sonnet builds and reviews.** Configured as a default, but **not self-enforcing** —
this has now shipped a real build on the wrong model twice (T18A entirely, and T18B until the user
caught it and typed `/model sonnet` by hand). Do not trust the mechanism below to switch itself;
treat the check as mandatory instead.

| Where | Setting | Covers |
|---|---|---|
| `.claude/settings.json` | `"model": "sonnet"` | The session default: building, and `/checkpoint` |
| `.claude/commands/build-task.md` | `model: opus` | Planning |
| `.claude/agents/*.md` | `model: sonnet` | `project-reviewer`, `adapter-parity` |

**What is actually true, verified by repeated failure, not assumed:** a command's `model:`
frontmatter is a per-invocation override, but if the session's model was already pinned by an
explicit user `/model` call (at session start, or mid-conversation for a longer planning
back-and-forth) before or during that command, nothing automatically un-pins it afterward. "The
session returns to Sonnet on your next message" is not something to rely on — verify it instead.

**Mandatory self-check, every time, right after a plan is approved and before the first `Write`/
`Edit`/`Bash` of the build phase**: read your own current-model line from this turn's system info.
If it does not say Sonnet, **stop before touching any file** and tell the user plainly which model
you are on and that they need to run `/model sonnet` — do not proceed "just this once," and do not
assume a prior `/model sonnet` earlier in the conversation still holds if anything (a nested
plan-mode re-entry, a resumed session) could have changed it since. This is not optional caution;
it is the only real enforcement that exists, since nothing in the harness blocks a build from
running on the wrong model on its own.

**Read `handoff.md` first in any session.** It holds current state. `decisionlog.md` holds history
and the reasoning behind past choices — consult it before revisiting a settled decision.

| File | Nature |
|---|---|
| `CLAUDE.md` | Durable rules. Rarely changes |
| `tasks.md` | The backlog, T1..T33 by iteration |
| `handoff.md` | Current state only. **Overwritten** each checkpoint |
| `decisionlog.md` | History. **Appended** each checkpoint |

## Commands

`/build-task <Tn>` · `/checkpoint` · `/push <msg>` · `/reindex` · `/tiers <topic>` · `/costs` ·
`/newadapter <iface> <name>` · `/newintent <name>`

## Environment

- Runs **natively on Windows**. Python 3.11 venv, Node 24, ffmpeg on PATH.
- `RUNTIME_ENV=local|azure` in `.env` selects the adapter set. Nothing else switches stacks.
- HyperFrames is a **Node CLI**, not a Python library — `npx hyperframes render|lint|check|doctor`.
  The render adapter shells out to it.
- Azure is Pay-As-You-Go with a $200/30-day credit. ~$0.12 per 7-min video; Speech F0 gives 500k
  chars/month free. **No budget alerts are configured — spend is checked manually via `/costs`.**

## Verification

```bash
pytest                                    # full suite, runs against fakes, no network
ruff check . && ruff format --check .
python cli.py "teach me about SQL injection"     # end to end, honors RUNTIME_ENV
```

Before declaring a task done: tests green, boundary greps empty, no `.py` over 200 lines,
`project-reviewer` passes.
