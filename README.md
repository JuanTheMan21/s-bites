# s_bites

Give it a topic. Get back a narrated explainer video.

```bash
python cli.py "teach me about SQL injection"
```

An LLM writes the outline and script, TTS narrates it, HTML and HyperFrames render the visuals, and
ffmpeg muxes the result into a ~7-minute MP4.

## Why it is built this way

This is a POC that has to become an enterprise product without a rewrite. So every external
dependency — LLM, TTS, storage, queue, rendering — sits behind an interface. Business logic in
`core/` calls the interface; an adapter implements it; `config.py` chooses which adapter at
startup. Swapping a local stack for Azure is a change to one environment variable, not a refactor.

```
RUNTIME_ENV=local   →  Ollama · Kokoro · local disk · asyncio pool · Playwright + HyperFrames
RUNTIME_ENV=azure   →  Azure OpenAI · Azure Speech · Blob Storage · (queue/render stubbed)
```

Both stacks run the same `core/` code, unmodified.

## The tier system

Rendering every scene as full animation is wasteful, and rendering none of it is boring. Each
segment is assigned a render tier under a global frame budget by a pure function in
`core/tier_resolver.py`:

- **Tier 0** — one screenshot, held for the narration duration
- **Tier 1** — 3-5 screenshots at different reveal states, crossfaded
- **Tier 2** — full frame-by-frame HyperFrames animation

Important segments get the expensive treatment; the rest degrade gracefully.

## Setup

Requires Python 3.11+, Node 22+, and ffmpeg on PATH.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements-dev.txt
playwright install chromium
cp .env.example .env            # then fill in credentials
```

For `RUNTIME_ENV=azure`, you need an Azure OpenAI deployment, a Speech resource (F0 tier is free),
and a Storage account. For `RUNTIME_ENV=local`, you need Ollama running.

## Layout

| Path | What lives there |
|---|---|
| `core/` | Business logic. Imports interfaces only — never an SDK |
| `core/graph/` | LangGraph orchestration: state, nodes, fan-out, checkpointing |
| `interfaces/` | The six contracts every adapter implements |
| `adapters/` | `local/` and `azure/` implementations |
| `rendering/` | One module per tier, plus Jinja scene templates |
| `mux/` | ffmpeg subprocess calls |
| `runtime_skills/` | Versioned prompt packs the pipeline loads at runtime |
| `api/`, `web/` | FastAPI backend, React frontend |
| `config.py` | The only module that names concrete adapter classes |

## Development

Work proceeds task by task from `tasks.md`. `handoff.md` holds current state, `decisionlog.md`
holds the reasoning behind past decisions. `CLAUDE.md` holds the rules that do not change.

```bash
pytest                            # runs against in-memory fakes, no network needed
ruff check . && ruff format .
```

Contributor rules worth knowing up front: no `.py` file over 200 lines, no `utils.py`, and nothing
in `core/` may import a vendor SDK. The last one is enforced by a pre-write hook, not by review.
