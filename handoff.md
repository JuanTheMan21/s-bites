# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-26 · after T18A, planning T18B_

---

## Where we are

**T18A fixed the measurable cause of the slideshow problem** (D16's throughput figure was wrong
by ~6-10x) and shipped everything that correction unlocked: word-timed captions, per-job
palettes, a real count-up, both carried-forward bugs fixed and verified against the real
toolchain, and a working terminal entrypoint. Full detail in the previous checkpoint's
decisionlog entries (D99-D103) — not repeated here.

**Then a real viewer reviewed the actual output and found four more real problems**, each traced
to specific code, not vibes: full-duration motion never actually got built past one template
(everything else still ends its real choreography at ~1.5s and just idle-bobs after); captions
accumulate into a growing wall of text instead of clearing between cues; the palette system
doesn't read as varied (near-black background across all six, blue-leaning structure token
stacked onto `diagram_flow` using it for everything); and `diagram_flow` looks identical every
time because there is exactly one template per intent, no variation. **T18B is scoped around
fixing these for real** — see `tasks.md`'s T18B entry and decisionlog D104 for the full
reasoning; this file gives the orientation a fresh session needs to start building it.

**Still on the `dev` branch, pushed to `origin/dev`.** `master` remains untouched at `655b355`.
T18A is committed (`503bf68`) and pushed. Nothing new is committed since then — this checkpoint
is closing out T18A's planning tail (the T18B scoping conversation), not new code.

**Done:** T1-T18, T18A.
**Next: T18B** — see the full scope in `tasks.md`. Read that entry before doing anything else;
it is more specific than a typical "not yet planned" placeholder because the scoping conversation
already happened this session, with the user reviewing real output and picking concrete choices.

## T18B: what's already decided, so the next session doesn't re-litigate it

These were explicit user choices during planning, not defaults I picked:

1. **Captions:** movie-style, 1-2 lines, clearing and replacing — not the current accumulate-
   forever behavior. Reuse `mux/subtitles.py`'s cue grouping (`MAX_WORDS_PER_CUE=8`) for the
   in-frame band too, rather than maintaining two grouping logics that can drift.
2. **Template variety: a per-video motif system**, not just more one-off templates. One motif
   chosen per video (new step, right after outline), threading through palette *and* which
   template variant renders each intent. Three starting directions, already named:
   **Blueprint** (light paper, schematic connectors), **Terminal** (warm dark, zero blue, stepped
   connectors), **Broadcast** (light neutral, one bold accent, lower-third labels). Build as a
   shared token/component layer (`_tokens.html`/`_captions.html`'s own pattern) — not fully
   bespoke templates per motif × intent, or this becomes unbuildable in one pass.
3. **Palette: loosen the semantic split.** `--accent-secondary` (structure) does not have to be
   blue — it should vary per motif instead of being effectively fixed to a blue-ish hue family.
4. **Two new intents**, driven by a real reference video the user shared (a 2:20 binary-search
   explainer): an **array/list visualization** (boxes, narration-synced cross-out/collapse as a
   search space halves) and a **composite code+diagram split** (two panels in one frame). These
   absorb most of what `VisualIntent.NETWORK_DIAGRAM` would have been — a `diagram_flow`
   hub/orbit alternate covers the rest, so NETWORK_DIAGRAM is not a separate intent anymore.
5. **Shared annotation components** (pointing-hand/cursor, success-check), usable by any
   template — port technique from the registry the way T18A's count-up was built (`npx
   hyperframes add <name> --json --no-clipboard`, inspect the written file, hand-adapt into this
   project's Jinja/GSAP conventions; the registry's own `<template>`/`window.__hyperframes` clone
   mechanism assumes a runtime this project's single-composition-per-segment layout doesn't load
   — confirmed directly in T18A, don't re-derive this).
6. **Force segment 0 to `title_card`, structurally.** Currently `runtime_skills/outline/1.0.md`
   only suggests it (`"at most one title_card at the start"`) — nothing enforces it, and the real
   T18A test run had none. This is a small, contained fix; do it early.
7. **Iteration budget: one solid pass.** Build the above, verify with `hyperframes check` per
   composition, run **one** real end-to-end render at full 7-minute length (not a multi-cycle
   render/watch/adjust loop — that was explicitly declined). The full-length render itself is
   also new information: T18A only ran a 90-second/3-segment test, so this is the first real
   measurement of total wall-clock and cost at full length.
8. **Explicitly not T18B:** Mermaid (rejected — the reference video's actual needs aren't
   Mermaid's diagram types, and HyperFrames' seekable-timeline model would need the same
   stroke-draw animation on top regardless of where the SVG came from; see D104 if this gets
   reconsidered later for genuinely arbitrary graph topology). Fully compositional LLM-authored
   scenes (still the larger, research-shaped item T18A's plan already deferred once — the richer
   fixed-template set above is the bet that it isn't needed yet; revisit only if a real
   full-length video under this scope still doesn't feel varied enough). The FastAPI+page local
   entrypoint (`cli.py`'s terminal prompt covers the DoD). The `--variables`/`--batch` refactor.

## What T18A produced (for reference — full file-by-file detail in the previous checkpoint's
version of this section, superseded here; read `decisionlog.md` D99-D103 for the complete list)

Corrected render throughput and `FRAME_BUDGET` (D99); word-level TTS timing
(`interfaces/tts_provider.py::WordMark`/`SynthesisResult`, D101) driving in-frame captions
(currently the accumulate-forever version T18B fixes) and an SRT sidecar; six palettes
(`rendering/palettes.py`, currently the near-black-only version T18B's motif system replaces); a
real count-up for `stat_callout`; GSAP vendored locally; D93 (narration crossfade) and D94
(`diagram_flow` marker opacity) fixed and verified against the real toolchain, not just
redesigned; a `RENDER_ENV` bridge (`config_render.py`, D100) so `cli.py` runs standalone.

**Real end-to-end run this session:** topic "how binary search works," 90s target, 3 segments,
all three Tier 2, 165.9s wall-clock. Also published as an Artifact this session (video + real
stats + an honest cost breakdown, including the two lines that aren't itemized by any tooling in
this repo) — ask the user if they still have that link if a T18B session wants a visual reference
for what the current (pre-T18B) output actually looks like.

## Verify at any time

```bash
pytest                                    # offline, no network -- green as of this checkpoint
pytest -m local_live                      # opt-in, needs the real browser/CLI/ffmpeg installed
ruff check . && ruff format --check .
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # must be empty
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # must be empty
git branch --show-current                                                    # must be: dev

PYTHONPATH=. .venv/Scripts/python.exe cli.py                  # prompts for a topic, runs standalone
```

## Environment state

| | |
|---|---|
| Models | Opus plans, Sonnet builds and reviews. T18A's build ran on Opus throughout — the harness was pinned at session start and could not be switched mid-session; this was flagged to the user, not silently ignored. Confirm before T18B's build starts that the session is actually on Sonnet. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100) — the bridge that lets `cli.py` run standalone. Still temporary; T35 removes the need for it. |
| `FRAME_BUDGET` | `9500` (D99). |
| `RENDER_MAX_CONCURRENCY` | `2` — chosen from this machine's low free RAM (~2.4GB alongside 16 cores), not from a dedicated concurrency benchmark. Worth re-measuring for real once T18B's full-length render happens, if render time looks off from the ~5-10 minute extrapolation. |
| `RENDER_WORKERS` | `auto`. |
| Git | `dev` branch, pushed to `origin/dev`. HEAD is `503bf68` (T18A's commit) — nothing new committed this checkpoint (planning only). `master` untouched at `655b355`. |
| Node | `hyperframes@0.8.15` pinned via `package.json`, `node_modules/` installed (gitignored). |
| GSAP | Vendored locally (`rendering/templates/vendor/gsap.min.js`). Google Fonts is still a live CDN dependency — unchanged, not this task's scope either time. |
| Azure spend | One real run this session (~90s/3 segments). LLM and Storage costs still not itemized by any tooling in this repo; `az consumption usage list` is blocked by the tenant's security-defaults policy (`AADSTS530035`) — `az account show` works (cached, narrower-scope token) but the consumption/cost-management scope needs a fresh interactive login: `az login --tenant 551f939c-8006-4967-8945-7f4b86b77f1a --scope https://management.core.windows.net//.default`. |

## Before the next session

**Nothing code-blocking.** Read this file, then `tasks.md`'s T18B entry, then decisionlog D104,
then plan mode as usual — the scope is already largely negotiated; plan mode's job is turning it
into concrete files/interfaces, not re-deciding what T18B is for.

**If an exact Azure cost figure matters**, run the `az login` command above first (interactive,
needs the user).

## Known gaps and open questions

**Carried into T18B, now with a plan (see above and D104) — not re-listed as open questions here:**
full-duration motion, captions, palette variety, template repetition, missing title card.

**Still genuinely open:**
- **The ~5-10 minute full-length render estimate is extrapolated, not measured.** T18B's own "one
  real end-to-end render at full length" is the first chance to get a real number — do this and
  update `FRAME_BUDGET`/`RENDER_MAX_CONCURRENCY` again if it's meaningfully off.
- **`RENDER_MAX_CONCURRENCY=2` was picked from one machine's `hyperframes doctor` output, not
  measured under real concurrent load.** Same open item as last checkpoint, still open.
- **Only one of six palettes was exercised in a real render.** The other five were only checked
  via `hyperframes check --contrast` against composed-but-not-rendered scenes. Moot once T18B's
  motif system replaces the flat palette system anyway — don't invest in verifying the old one
  further.
- **`mux/subtitles.py::MAX_WORDS_PER_CUE=8` is a guess.** T18B's cue-based in-frame captions will
  make this visible in a way it wasn't before (it only affected an SRT file nobody was looking at
  directly) — worth a real look once captions are on screen.
- **`hyperframes check` is still non-deterministically flaky at 0.8.15** (D96). Re-run before
  trusting a single red result.

**Carried forward, unchanged:**
- **The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open** (D24/D67).
- **No coverage gate exists (D42).**
- **`Segment.slots` is an untyped dict** (D29). Revisit at T24.
- **Scope: 37 tasks across 8 iterations.**
- **T10 stays `in-progress`, unclaimed.** Ollama/Kokoro still don't exist.
- **D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only** — still open.

## Gotchas worth remembering

**Carried from T18A, still true:**
- **The quality hook strips an import added before its first use** — even within the same
  multi-edit session, even moments later. Add the import in the identical edit that adds its
  first real usage. Bit this project in at least six files last task; will bite T18B too if not
  watched for specifically when adding new modules (the motif token layer, the two new intents,
  and the shared annotation components are all new imports across multiple files).
- **A wrong measurement, once written into a constant, propagates unquestioned across sessions
  until someone re-derives it from first principles.** T18A's whole first half was this. Don't
  assume the ~5-10 minute full-length estimate above is right just because it's written down.
- **A registry component's `<template>`/`window.__hyperframes` runtime doesn't fit this project's
  layout — port the technique, not the file.** Directly relevant to T18B's annotation components.
- **`hyperframes lint`'s severity levels are meaningful** — only `[error]` blocks a render as of
  T18A (`rendering/render_segment.py`, D102); `[warning]`/`[info]` do not.
- **Windows path semantics**: a trailing dot is stripped on existence checks but not on directory
  enumeration (D46).
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
