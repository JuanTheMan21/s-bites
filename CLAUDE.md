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

## Build loop

Work proceeds task by task from `tasks.md`, one task per session:

1. `/build-task Tn` — loads `handoff.md` + `decisionlog.md` + the task, presents a plan, stops.
2. Agree, exit plan mode, switch to Sonnet/Haiku in auto mode, build.
3. Run the `project-reviewer` agent.
4. `/checkpoint` — reviewer gate → append `decisionlog.md` → rewrite `handoff.md` → mark done →
   reindex RepoWise → offer to push.

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
