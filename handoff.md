# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-26 · after T18A_

---

## Where we are

**A real viewer watched T18's two videos and called them a slideshow.** That verdict traced to a
measurable cause: D16's render-throughput figure was wrong by roughly 6-10x (a 3-second sample
dominated by browser cold start), so `FRAME_BUDGET` funded Tier 2 for only 2 of 15 segments and
everything else fell back to a 4-screenshot crossfade. T18A re-measured throughput for real
(`npx hyperframes benchmark`, ~17 frames/sec), corrected `FRAME_BUDGET` (1400 → 9500) and the
tier ladder, and built everything that correction unlocked: word-timed captions, per-job
palettes, a real count-up animation, both carried-forward bugs fixed and verified against the
real toolchain (not just redesigned), and a working local entrypoint.

**All of this happened on a new `dev` branch, cut from `master` at `655b355`.** `master` is
untouched and still the last known-good state. Nothing from this session is committed yet on
either branch.

**Done:** T1-T18, T18A (T10 stays `in-progress`, unclaimed — see below).
**Next: T18B** — `VisualIntent.NETWORK_DIAGRAM`, the originally-planned FastAPI+static-page local
entrypoint (T18A's terminal-only version covers the DoD for now), the storyboard/motif step, and
whichever of T18A's other deferred items still look worthwhile. Not yet planned in detail — see
`tasks.md`'s own T18B entry and decisionlog D99-D103 for the starting context.

## What T18A produced

| File | Holds |
|---|---|
| `package.json`, `package-lock.json` | Pins `hyperframes@0.8.15` locally (`node_modules/`, gitignored) — `adapters/local/hyperframes_process.py` prefers the local bin over `npx`, falling back to `npx` if `npm install` hasn't run. |
| `adapters/local/hyperframes_process.py` | New — shared spawn/timeout/kill-tree plumbing, extracted so `hyperframes_cli.py` (render/lint) and `hyperframes_check.py` (check) don't duplicate it. |
| `adapters/local/hyperframes_check.py` | New — `npx hyperframes check`, the richer motion/layout/contrast gate. Deliberately **not** on the `RenderBackend` ABC (would force Azure's stub to grow a verb it can't implement, breaking Invariant 4); exposed as an extra method on `PlaywrightHyperFramesRenderBackend.check()` instead. |
| `adapters/local/hyperframes_cli.py` | `render` now passes `--workers`, `--browser-timeout`, `--player-ready-timeout`, `--protocol-timeout`. |
| `adapters/local/render_backend.py` | `render_timeout_s(duration_ms)` replaces one flat 60s timeout for renders (captures/lint keep it); `workers` param added. |
| `config_render.py` | New — render-backend resolution split out of `config.py` (200-line ceiling) once `RENDER_ENV` landed. `render_env()`/`resolve()`. Still the only other module naming `PlaywrightHyperFramesRenderBackend`/`ContainerAppsRenderBackend` — see D100 for why this doesn't violate "config.py is the only module naming concrete adapter classes". |
| `.env`, `.env.example` | `FRAME_BUDGET=9500`, `RENDER_MAX_CONCURRENCY=2`, `RENDER_WORKERS=auto`, new `RENDER_ENV=local` (D100 — the bridge that finally closes D92). |
| `core/tier_resolver.py` | `IDEAL_TIER` raised: NORMAL/MINOR now target `Tier.ANIMATED` (only ASIDE settles for REVEAL). Mechanism (`resolve_tiers`, frame costs) unchanged — only its inputs were wrong. |
| `interfaces/tts_provider.py` | Gained `WordMark`/`SynthesisResult` (contract vocabulary, same precedent as `SkillPack`/`QueuedJob` — D101). `TTSProvider.synthesize` now returns `SynthesisResult`, not `tuple[Path, int]`. |
| `core/synthesis.py` | New — re-exports `WordMark`/`SynthesisResult` from `interfaces.tts_provider` for `core/models.py`'s convenience. |
| `core/models.py` | `Segment.word_marks: list[WordMark]` (default empty), `VideoJob.subtitles_key`. |
| `adapters/azure/tts_provider.py` | Connects the Speech SDK's `synthesis_word_boundary` event; `SynthesisResult.words` is real, measured word timing. |
| `tests/fakes/tts_provider.py` | Returns synthetic even-spaced word marks (`even_word_marks`) so offline tests exercise the timed path. |
| `rendering/templates/_captions.html` | New — in-frame word-timed captions, degrades to an even stagger when `word_marks` is empty. Wired into all six intent templates. |
| `mux/subtitles.py` | New — writes `final.srt`. Offsets are trivial: D93's fix leaves the audio track unshrunk, so segment *i* starts at exactly `sum(durations_ms[:i])`. |
| `core/graph/nodes/finalize.py` | Writes/persists the SRT sidecar alongside the final video; `VideoJob.subtitles_key` set. |
| `rendering/palettes.py` | New — six hand-picked, contrast-checked palettes, selected deterministically per `job_id`. |
| `rendering/compose.py` | Threads `job_id` through for palette selection; passes `word_marks`/`palette` to every template; copies vendored `gsap.min.js` alongside `index.html`. |
| `rendering/templates/vendor/gsap.min.js` | New — vendored GSAP 3.14.2. Every template now loads `./gsap.min.js`, no CDN. |
| `core/slot_schemas.py` | `StatCalloutSlots` gained `value_number`/`prefix`/`suffix` — a real count-up when set. |
| `runtime_skills/scene-authoring/1.1.md` | New version (never edit `1.0.md`) — guidance for when to fill the new count-up fields. |
| `rendering/templates/stat_callout.html` | Deterministic frame-row count-up (technique ported from the registry's `count-up` component, hand-adapted — see D103), or the original scale-grow when `value_number` is null. |
| `rendering/templates/diagram_flow.html` | D94 fixed: marker `background` is now `var(--bg)`, opaque, not a stale hardcoded `rgba(...)`. |
| `mux/concat_segments.py` | D93 fixed for real: `tpad` pads video so `xfade` never consumes real narrated frames; audio is a plain unshrunk `concat`, zero blending. Also cycles 5 transition styles instead of always `fade`. |
| `rendering/render_segment.py` | Lint gate now only treats `[error]`-severity findings as fatal (D102) — found live when a real render hit a `[warning] composition_file_too_large`. |
| `cli.py` | `topic` is now optional; prompts on stdin when omitted. Prints `final.srt`'s local path alongside `final.mp4`'s. |
| Tests | `test_tier_resolver.py`, `test_concat_segments.py`, `test_azure_tts.py`, `test_audio_duration.py`, `test_fake_providers.py`, `test_live_azure.py`, `test_compose_scene.py`, `test_render_segment.py`, `test_config.py`, `test_runtime_skills.py`, `test_graph_pipeline.py`, `test_slot_schemas.py` all updated for the above; new regression tests for D93 (unshrunk duration), D102 (warning non-fatal), the `RENDER_ENV` bridge, and the corrected tier ladder. |

## What building T18A actually found

1. **D16's throughput figure was wrong, and this project's own evidence already contradicted
   it** before re-measuring: a flat 60s render timeout, applied to ~600-frame (25s) segments that
   completed inside it, already implied ≥10 frames/sec against D16's claimed 1.7-2.7. Real
   measurement (`npx hyperframes benchmark`) landed at ~17 frames/sec. The whole visual budget had
   been rationed against a number nobody had re-checked since T4.
2. **A real render found a real lint-severity bug the offline suite couldn't**: `hyperframes
   lint`'s `[warning] composition_file_too_large` (315 lines, once captions/palette tokens grew
   every template) blocked every render outright under the old "any finding is fatal" stance.
   Fixed by distinguishing severity (D102) — this is exactly the class of finding "verify against
   the real thing" exists to catch, and it did, on the very first real run after the rewrite.
3. **A sibling file in a composition's directory does not violate `hyperframes lint`'s actual
   constraint** — tested directly before relying on it (D60's real requirement is the entry
   file's name/location, not a literally-empty directory), which is what made vendoring GSAP
   locally safe to do at all.
4. **A registry component's own `<template>`/clone mechanism assumes a runtime
   (`window.__hyperframes`) this project's compositions don't load** — `npx hyperframes add` is
   genuinely useful for *inspecting* a technique (the `count-up` component's deterministic
   frame-row approach was ported this way), but not for literally dropping registry files into a
   per-segment composition directory.
5. **`hyperframes check` caught a real overlapping-GSAP-tween bug** in the count-up template's
   first version (the entrance scale tween ran past the count's own landing time) — the same
   `overlapping_gsap_tweens` finding class D89's comparison.html docstring already warned about,
   now confirmed to actually fire under real conditions.

## Verify at any time

```bash
pytest                                    # offline, no network -- green as of this checkpoint
pytest -m local_live                      # opt-in, needs the real browser/CLI/ffmpeg installed
ruff check . && ruff format --check .
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # must be empty
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # must be empty
git branch --show-current                                                    # must be: dev

# The real thing, end to end (uses real Azure LLM/TTS + real local render, costs a small amount):
PYTHONPATH=. .venv/Scripts/python.exe cli.py "<topic>" --target-duration-ms 90000
```

`cli.py` with **no** topic argument now prompts on stdin — this is T18A's local entrypoint,
requiring no manual adapter-mixing (`RENDER_ENV=local` in `.env` bridges `RUNTIME_ENV=azure`'s
LLM/TTS to the real local render backend, D100).

**Real end-to-end run this session:** topic "how binary search works", 90s target, 3 segments,
**all three landed on Tier 2** (the corrected budget/ladder funding what D78's original 1400
could not), real word-timed `final.srt`, 165.9s wall-clock. Verified visually (diagram_flow
markers solid, no rail bleed-through; captions ink word-by-word; palette applied; transition
variety visible) and D93's fix separately verified by spectral analysis (a real ~40ms clean audio
cut at the join, versus the old ~500ms blend).

## Environment state

| | |
|---|---|
| Models | Opus plans, Sonnet builds and reviews. **This session ran on Opus throughout** — the user asked for Sonnet mid-session but the harness was pinned to Opus at session start and could not be switched from inside the conversation; flagged to the user, not silently ignored. |
| `RUNTIME_ENV` | `azure` in both `.env`/`.env.example`, unchanged. |
| `RENDER_ENV` | **New (D100).** `local` in both `.env`/`.env.example` — the bridge that lets `RUNTIME_ENV=azure`'s LLM/TTS pair with the real local render backend. Defaults to `RUNTIME_ENV` when unset, so nothing that predates it changes behavior. Temporary: T35 removes the need for it. |
| `FRAME_BUDGET` | **9500** (was 1400, D99) — funds Tier 2 on every non-ASIDE segment of a realistic 7-minute video. |
| `FPS` | 24, unchanged. |
| `RENDER_MAX_CONCURRENCY` | **2** (was 4, D99) — this machine reports as little as ~2.4GB free RAM alongside 16 cores; memory, not CPU, is the tighter constraint for concurrent Chrome processes. |
| `RENDER_WORKERS` | **New, `auto`** — passed to `hyperframes render --workers`; left to the CLI's own calibration (accounts for low-memory mode) rather than pinned. |
| `.env` | Exists, filled in, gitignored. Not touched beyond the render-related keys above. |
| Node | `node_modules/` now exists (gitignored), `hyperframes@0.8.15` pinned via `package.json`. `npm install` already run this session. |
| HyperFrames CLI | **Pinned to 0.8.15** for the first time (was drifting: 0.8.10 → 0.8.12 → 0.8.15 across three prior tasks, D96). Local bin preferred over `npx`. |
| GSAP | **Vendored locally** as of this task (`rendering/templates/vendor/gsap.min.js`, 3.14.2) — every render now needs zero network egress for it. Google Fonts is still a live CDN dependency, unchanged, not in this task's scope. |
| Azure spend | One real end-to-end run this session: 3 segments, ~90s of narration, real LLM + TTS calls. Not itemized by any tooling in this repo — run `/costs` for a real figure, and re-run `az login` first if it was stale (unclear this session; not re-checked). |
| Git | on `dev` (new this session, cut from `master` at `655b355`), **nothing committed yet**. `master` unchanged and still the fallback if anything here needs reverting. |

## Before the next session

**Nothing code-blocking.** If continuing straight into T18B, start by reading this file plus
decisionlog D99-D103, then plan mode as usual.

**Not yet committed.** This entire task's work is uncommitted on `dev`. Review the diff and commit
(or ask for a commit) before doing anything that could lose it — no destructive git operations
were run this session, but nothing is safe until it's in a commit either.

## Known gaps and open questions

**New this task:**

- **T18B's full scope is not yet planned in detail** — `tasks.md`'s T18B entry lists what's
  deferred but deliberately doesn't draft a DoD; that's for T18B's own plan-mode session.
- **`RENDER_MAX_CONCURRENCY=2`/`RENDER_WORKERS=auto` were chosen from a memory-constrained
  machine's `hyperframes doctor` output, not from a dedicated concurrency benchmark** — D47's
  disk-I/O-under-concurrency question (D69) is still about `Storage`, not this; this is a new,
  separate open question about render-worker memory headroom that a future task running many
  concurrent full jobs should re-measure for real rather than trust this session's single-job
  observation.
- **Only one real end-to-end run happened this session** (3 segments, 90s target) — the ~15-minute
  wall-clock target for a full 7-minute/15-segment video is extrapolated from that plus the
  `hyperframes benchmark` throughput number, not measured directly at full length. Worth a real
  full-length run before trusting the 15-minute figure at that scale.
- **Six palettes exist; only one was exercised in the real end-to-end run** (whichever `job_id`'s
  hash selected). The other five were verified via `hyperframes check --contrast` against
  composed-but-not-rendered scenes, not against a full real video.
- **Captions/subtitle line-grouping (`mux/subtitles.py::MAX_WORDS_PER_CUE = 8`) is a guess, not
  tuned against a real transcript for readability** — worth a real look once more full videos
  exist.
- **`hyperframes check` is still non-deterministically flaky at 0.8.15** (D96, unresolved by
  pinning — pinning fixes drift across sessions, not the tool's own run-to-run variance within one
  version). Re-run before trusting a single red result from it.

**Carried forward, unchanged:**

- **The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open** (D24/D67) —
  belongs to whichever future task builds a real queue-driven runner (T34).
- **No coverage gate exists (D42).**
- **`Segment.slots` is an untyped dict** (D29). Revisit at T24.
- **Scope: 37 tasks across 8 iterations** (36 plus T18B, following T18A's own precedent for a
  lettered insertion) — local stack priority still unsettled.
- **T10 stays `in-progress`, unclaimed.** Ollama/Kokoro still don't exist. T18A's `WordMark`
  fallback path (empty `words`, even-stagger degrade) is exactly what a future Kokoro adapter
  will exercise for real, or `npx hyperframes transcribe` as the documented fallback if Kokoro
  itself never reports boundaries.
- **D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only** — still open.

## Gotchas worth remembering

**New this task:**

- **The quality hook strips an import added before its first use, every time, even within the
  same multi-edit session** — bit this task more than any prior one (at least six separate files:
  `hyperframes_cli.py`'s local-bin import, `render_backend.py`'s `hyperframes_check` import twice
  over two different methods, `tests/fakes/tts_provider.py` and `tests/test_azure_tts.py`'s
  `WordMark`/`SynthesisResult` imports, `finalize.py`'s `write_srt` import, `rendering/compose.py`'s
  `shutil` import, `config.py`'s `config_render` import). The fix is always the same: add the
  import in the identical `Edit` call that adds its first real usage, not a call before or after.
  This is not a new rule (it's in every prior handoff's gotchas), but it is worth restating that
  it bites even when the usage is added moments later in the same session.
- **A wrong measurement, once written into a `.env` comment and a constant, propagates and stays
  unquestioned across sessions until someone re-derives it from first principles** (D16 → D78 →
  D99). The tell that it was worth re-checking was already sitting in the codebase: a 60-second
  timeout on renders the "true" throughput figure said should take 6-10x that.
- **A registry's own component is a reference for the technique, not a drop-in file** — its
  `<template>`/`window.__hyperframes` runtime assumes a project scaffold this codebase's
  single-composition-per-segment architecture doesn't have.
- **`hyperframes lint`'s severity levels are meaningful, not decorative** — treating every finding
  as equally fatal (reasonable when the only findings anyone had ever seen were real bugs) breaks
  the first time a stylistic warning shows up, and the fix is to read what `--strict`/
  `--strict-all` already encode about the distinction, not to invent a new one.

**Carried forward:**

- **`project-reviewer` is worth running, and the *second* fresh full pass is the one that finds the
  bug** — the user explicitly asked this task not run it repeatedly, so it ran once, at the end.
- **A confident claim about a library's or CLI's exact behavior is a claim until checked against
  the real thing** — this task's central finding (D16/D99) is the largest instance of this rule
  yet in this project's history.
- **Windows path semantics**: a trailing dot is stripped on existence checks but not on directory
  enumeration (D46).
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
