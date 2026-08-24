# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-24 · after T17_

---

## Where we are

**A `Segment` can now become a real, playable silent video clip.** Given a fully measured, tiered,
and scene-authored segment, `rendering/render_segment.py::render_segment` composes its scene from
the matching Jinja template, lints it, and dispatches to whichever of the three tier modules
(`rendering/static.py`/`reveal.py`/`animated.py`) its assigned `Tier` calls for — returning an MP4
clip pinned to the segment's exact measured `duration_ms`. Nothing mixes audio in yet; that's T18.

**Done:** T1-T9, T11-T17 (T10 stays `in-progress`, unclaimed — see below).
**Next:** **T18 — Mux & CLI.** Depends on T17 (done). Per-segment audio mux, then concat, then the
CLI entrypoint. This is the task that produces the first complete, playable video.

## What T17 produced

| File | Holds |
|---|---|
| `rendering/templates/_tokens.html` | The shared design system, as three Jinja macros (`tokens_style`, `background_markup`, `background_script`) every template imports: CSS tokens, one shared animated background layer (two radial glows, a 24-particle field, one accent rule). Visual style is **Data Drift** (D83) — near-black + purple/cyan accents, Montserrat (statement voice) + JetBrains Mono (data/technical voice). Chosen mid-task, redirecting a plan that would otherwise have extended `_reference_tier2.html`'s cyan-on-navy scheme, which is itself a documented lazy AI default. |
| `rendering/templates/{title_card,bullet_list,comparison,diagram_flow,code_walkthrough,stat_callout}.html` | The six real templates (D30), each a single seekable GSAP timeline per `hyperframes-core`. `diagram_flow.html`'s nodes sit on one straight rail in array order — never a free-floating graph — so connectors structurally cannot cross. |
| `rendering/compose.py` | `compose_scene(segment, dest_dir) -> Path`. Validates `segment.slots` via `slot_schema_for` (D29), renders the intent's template, writes `dest_dir/index.html` — always that literal name, alone in its directory (D85, closing D60). |
| `rendering/{static,reveal,animated}.py` | The three tier modules. Tier 0 captures the composition's end state and holds it; Tier 1 captures 4 evenly-spaced states and crossfades them; Tier 2 is a thin wrapper over `RenderBackend.render`. |
| `rendering/render_segment.py` | The orchestrator: compose → `RenderBackend.lint` gate (any finding is fatal, `CompositionInvalid`, applied uniformly before all three tiers — D88) → dispatch by `Tier`. Not wired into `core/graph/` — T18 owns that. |
| `mux/frames_to_clip.py` | **New directory content** — `hold_frame`/`crossfade`, ffmpeg subprocess calls turning Tier 0/1 stills into a clip, duration pinned exactly via `-t`. Started here rather than deferred to T18, per CLAUDE.md's project-wide (not task-scoped) "ffmpeg calls live in `mux/`" rule (D84). T18 only has audio-mux + concat left to add. |
| `scripts/hook_asset_quality.py` | **Fixed, not new.** The T2-era hook tried to `npx hyperframes lint` single `.html` files under `rendering/templates/` — broken twice over (the CLI only lints whole directories, D60; and a Jinja source template isn't valid standalone HTML anyway). Now skips linting any file containing `{{`/`{%`. |
| `tests/test_compose_scene.py`, `tests/test_render_segment.py`, `tests/test_frames_to_clip.py` | Offline, no network. Real ffmpeg is exercised directly (`skipif` if absent) — the same bargain `test_audio_duration.py` makes for ffprobe. |
| `tests/test_render_segment_live.py` | `local_live`. All 6 `VisualIntent` × all 3 `Tier` (18 cases) against the real `PlaywrightHyperFramesRenderBackend` and real ffmpeg — the "render every template at all three tiers explicitly" instruction D79 asked for. Also runs `npx hyperframes check` (not just `lint`) on every composition as a second, stricter gate (contrast, layout, motion) that deliberately stays *outside* `render_segment`'s own gate. |

## What building T17 actually found

**The offline test suite and a careful authoring pass were not enough — five real bugs only
surfaced once the live toolchain (`npx hyperframes check`, real Playwright seeks) ran against real
output.** Full detail in decisionlog.md's D89, but the one worth internalizing before touching a
template again: **ambient/idle motion must be a genuine GSAP property tween
(`fromTo`/`to` on `x`/`y`/`scale`/`opacity`/etc.), never a manual `onUpdate` DOM write.**
HyperFrames seeks with `suppressEvents=true` (this project's own `seek(id, t, true)` convention,
D15) — GSAP explicitly skips `onUpdate` callbacks under that flag while still applying a *tracked
property's* interpolated value, so `sine-wave-loop.md`'s documented "onUpdate form" silently does
nothing under this project's render/check pipeline. Verified empirically, not assumed. Two other
live-toolchain-only findings worth knowing before writing more templates:

- `hyperframes check`'s frozen-sweep guard treats anything below **opacity 0.2** as invisible for
  its own liveness fingerprint, independent of how much it's actually moving.
- SVG `stroke-dasharray`/`stroke-dashoffset` animation never changes an element's own
  `getBoundingClientRect()` — invisible to any bbox-based liveness check, by construction.

**A sixth bug, the same class in a new place, was caught by a `project-reviewer` pass rather than
the live toolchain directly:** `comparison.html`'s idle card bob had a hardcoded `repeat: 1`, so it
froze for the back ~16s of any realistic (~21s) segment. The live test's own short fixture duration
(4000ms, chosen deliberately to keep an 18-case real-render matrix fast) happened to end inside the
bob's original active window, so the test passed for the wrong reason. **A short test duration can
mask a duration-dependent freeze — verify motion-heavy templates at a realistic segment length too,
not just whatever duration the fast test suite uses.** Fixed the same way the particle field
already had been: `repeat` computed from `duration_sec`, not hardcoded.

**Two Windows-specific gotchas, worth remembering generally, not just for this task:**
- `npx` on Windows is `npx.cmd`; `subprocess`/`asyncio.create_subprocess_exec("npx", ...)` without
  `shell=True` fails with `WinError 2` unless resolved through `shutil.which("npx")` first — the
  pattern `adapters/local/hyperframes_cli.py` already used, and that this task's own new test file
  initially missed.
- The standing "add an import and its first use in the same `Edit`, never split across two" rule
  bit again, on `shutil` in `tests/test_render_segment_live.py` — five-plus sessions running now.

## Next task: T18 — Mux & CLI

Per-segment audio mux, then concat, then the CLI entrypoint. **This task produces the first
complete, playable video.** Depends on T17 (done).

**What T18 should know going in:**

- **`render_segment` is not wired into `core/graph/` or `config.py`.** T18 is the first task that
  needs to decide the real artifact-directory convention (a `SEGMENT_COMPOSITION_KEY`-shaped
  constant, the way `synthesize.py` owns `SEGMENT_AUDIO_KEY`) and the first that calls
  `render_segment` per segment, most likely from the CLI runner rather than a new graph node —
  that shape is T18's call to make, not inherited from T17.
- **`render_segment`'s clips are silent.** Audio mux (narration onto each segment's clip) and
  concat (joining segments into one video) are both still unbuilt. `mux/frames_to_clip.py` already
  exists and already demonstrates this project's ffmpeg-subprocess pattern (timeout → kill →
  `RenderFailed`, `-t`-pinned exact duration) — T18's audio-mux/concat functions belong in the same
  directory, following the same shape, not a new pattern.
- **`FakeRenderBackend.render` still writes placeholder bytes, not a real MP4** (unchanged from
  T16's note). Anything in T18 that cares about real output must run against the real local
  backend, same as T17 did.
- **HyperFrames CLI drifted to 0.8.12** (was 0.8.10 as of T16's handoff) — an upstream version
  bump `npx` picked up with no project-level pin (no `package.json` exists at the repo root; the
  CLI resolves purely from npm's own cache). Not investigated further since nothing broke, but
  worth noting if T18 sees behavior that doesn't match an older doc or memory.

**Verify at any time:**

```bash
pytest                                    # offline, no network -- 529 passed, 1 skipped, 53 deselected
pytest -m local_live                      # opt-in, needs the real browser/CLI/ffmpeg installed --
                                           # 25 passed. Run in batches (by Tier -k filter) if a
                                           # single invocation gets killed by the environment; the
                                           # full run took ~4-5 minutes across 4 foreground batches
                                           # this session, and two attempts at a single backgrounded
                                           # run were both killed by something outside this repo's
                                           # control before finishing.
ruff check . && ruff format --check .
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # must be empty
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # must be empty
```

## Environment state

| | |
|---|---|
| Models | Opus plans, Sonnet builds and reviews |
| `RUNTIME_ENV` | **`azure`** in both `.env` and `.env.example` (D25) — unchanged this task |
| `FRAME_BUDGET` | **1400** (D78) — unchanged this task |
| `FPS` | 24, unchanged |
| `.env` | Exists and is filled in. Gitignored. Never commit it. |
| Azure sub | `d4a261bd-760c-41bd-9e22-ef58e2329ce0`, `az login` done |
| Azure OpenAI | `skill-bites` (eastus) · deployment `gpt-5.4-mini` 2026-03-17, DataZoneStandard (D49) · api-version `2024-10-21` |
| Azure Speech | `skill-bites-tts` (eastus), S0 (D48) · voice `en-US-AvaMultilingualNeural` |
| Azure Storage | `sbitesartifacts25817` (eastus) · containers `explainer-artifacts`, `runtime-skills` |
| Python | 3.11.0, venv at `.venv/`. Use `.venv/Scripts/python.exe` explicitly |
| Node | 24.16.0 · npm 11.13.0 · ffmpeg/ffprobe 8.1.1 on PATH |
| `langgraph` | `langgraph==1.2.11`, `langgraph-checkpoint-sqlite==3.1.1`, installed in `.venv` |
| HyperFrames CLI | **0.8.12** (drifted up from 0.8.10 — see above), via `npx hyperframes`. Chrome Headless Shell cached at `~/.cache/hyperframes` |
| Playwright browsers | Installed — both `chromium-1234` *and* `chromium_headless_shell-1234` at `%LOCALAPPDATA%\ms-playwright` |
| Ollama, Kokoro | **Still not installed. Deliberately deferred (D59, reaffirmed D64)**, not forgotten |
| Git | on `master`, **7 commits, `5e0eb9a` latest** (T1-T17 all committed). `origin` → `github.com/JuanTheMan21/s-bites.git` **does exist** — verified via `git remote -v`, not assumed; two prior handoffs in a row had this stale, one claiming T15/T16 uncommitted after they'd already landed in `6b52ec2`, both claiming no remote when one was already configured. `origin/master` matched through `6b52ec2` as of this session; whether this session's two new commits (`2ca6f9d` T17, `5e0eb9a` a RepoWise index-metadata sync) are pushed depends on what the user chose at this checkpoint's push prompt — **check `git status -sb` rather than trusting this line**, given the above |
| Azure spend | Unchanged this task — T17 did no LLM/TTS calls, only local rendering. Still no budget alerts configured; check with `/costs` |

## Before the next session

Nothing blocking. T18 is CLI/mux work against the real local `PlaywrightHyperFramesRenderBackend`
and real ffmpeg, both installed, plus wiring `render_segment` into a runner.

## Known gaps and open questions

**Closed this task:**

- **The composition-directory-layout assumption** (D60, carried since T12) **is settled** (D85):
  always the sole file `dest_dir/index.html`.
- **Whether a new error family was needed for "our own code judged this invalid"** (flagged at
  T16) **is closed** (D86): no new class — `CompositionInvalid` (lint) + pydantic `ValidationError`
  (slot payload) already cover it.
- **`TIER_SUPPORT`'s no-op map** (D36, carried since T5) **is confirmed correct** (D87): every
  intent's single timeline genuinely supports all three tiers; nothing to edit.

**New in T17:**

- **Any future ambient/idle motion added to a template must use tracked GSAP properties, never a
  manual `onUpdate` DOM write** (D89.2) — this is now the load-bearing rule for anyone running
  `/newintent` or otherwise touching `rendering/templates/`.
- **A short test duration can hide a duration-dependent animation bug** (the `comparison.html`
  freeze, D89) — worth a rule of thumb for any future template test: check behavior at a realistic
  segment length (~20-30s), not only whatever duration keeps a live-render matrix fast.
- **No `package.json` pins the HyperFrames CLI version** — it drifted from 0.8.10 to 0.8.12 between
  sessions with nothing this project controls. Not itself a problem, but means "the CLI behaves
  like version X" claims in older docs/memory can go stale silently.

**Carried forward, unchanged:**

- **The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open** (D24/D67) —
  owned by whichever future task builds the runner that calls `JobQueue.fail(..., requeue=True)`.
  T18's CLI runner is a plausible candidate to finally close this, worth checking when T18 is planned.
- **No coverage gate exists (D42).**
- **`Segment.slots` is an untyped dict** (D29). Revisit at T24.
- **Scope: 35 tasks across 8 iterations**, and the local stack's priority is still unsettled (T12's
  rescoping, T13's D64) — worth confirming with your manager before iteration 4.
- **T10 stays `in-progress`, unclaimed.** Ollama/Kokoro still don't exist; no task builds them.
- **D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only** — re-measure
  once T18 moves real rendered MP4 segments through `Storage.put_file`.

## Gotchas worth remembering

**New in T17:**

- **A manual `onUpdate` DOM write is invisible under this renderer's `seek(id, t, true)` seeking
  convention** — GSAP's `suppressEvents` skips the callback entirely while still applying a
  *tracked property's* own value. Use `fromTo`/`to` on a real animatable property for any ambient
  motion; reach for `sine-wave-loop.md`'s "onUpdate form" and it will render fine in a live preview
  and do nothing under this project's actual render/check pipeline.
- **`hyperframes check`'s frozen-sweep guard treats opacity below 0.2 as invisible**, regardless of
  real motion underneath it. Keep decorative ambient elements' resting opacity at 0.2 or above.
- **SVG dash-array/dash-offset draws never move the element's own bounding box** — invisible to any
  bbox-based liveness/motion check, by construction, not a bug in the draw itself.
- **`npx` needs `shutil.which("npx")` resolution on Windows** before
  `subprocess`/`create_subprocess_exec` — the bare string fails with `WinError 2` without
  `shell=True`. `adapters/local/hyperframes_cli.py` already does this; new code that shells out to
  `npx` must too.
- **libx264 refuses odd *and* zero width/height** — round dimensions **up** to the nearest even
  number (`2*ceil(iw/2)`), never down (`trunc` rounds a 1px source to 0, which also fails).

**Carried forward:**

- **A node-level `RetryPolicy` that also matches an error a node isolates locally defeats that
  isolation, silently** (D73). Any node using `structured_retry.py` registers with
  `build_transient_retry_policy()`.
- **The "quality hook autofixes on write" gotcha: adding an import and its first use in separate
  `Edit` calls lets the hook strip the "unused" import in between.** Bit again this session, on
  `shutil` in `tests/test_render_segment_live.py`. **Always add an import in the same edit as its
  first use** — six-plus sessions running; treat it as a hard rule.
- **`project-reviewer` is worth running, and the *second* fresh full pass is the one that finds the
  bug** — D57, D62, D67, D73, D82, now D89's `comparison.html` freeze. Ask for a fresh full read,
  never a check of named fixes.
- **A confident claim about a library's or CLI's exact behavior is a claim until checked against
  the real thing** — true again this task for both GSAP's `suppressEvents` semantics and
  `hyperframes check`'s own visibility floor, neither of which is written down anywhere obvious.
- **Check the *SKU's* quota, not the model's availability** (D49).
- **An SDK that "reports failures as results" can still raise** (D57).
- **Windows path semantics**: a trailing dot is stripped on existence checks but not on directory
  enumeration (D46).
- **A generator raises where it is iterated, not where it is called.**
- **A validation rule tested on one method of six is tested nowhere** (D39).
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
