# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-26 · after T18_

---

## Where we are

**Two real, playable ~6-minute videos exist now**, both "how neural networks learn," produced end
to end through the pipeline: outline → narration → tiering → scene authoring → render → mux →
concat. The second exists specifically because a real person watched and listened to the first one
and found problems no test caught. `core/graph/pipeline.py` now has a third `Send` fan-out
(`render_scene`, after `author_scene` via a join node `collect_scenes`) → `finalize`, which concats
every segment's clip and persists the final video (`VideoJob.video_key`).

**Done:** T1-T18 (T10 stays `in-progress`, unclaimed — see below).
**Next: T18A — bug fixes, a real local entrypoint, and a network-diagram visual intent.** Inserted
between T18 and T19 as a lettered task, not a renumber — see D98 if you're wondering why the
sequence isn't T19. **Depends:** T18 (done).

## What T18 produced

| File | Holds |
|---|---|
| `cli.py` | The CLI entrypoint. **Cannot currently run a full job standalone under either `RUNTIME_ENV` value** — see the Environment section below, this is the single most important thing to know before touching it. |
| `core/graph/nodes/render_scene.py` | New graph node: compose → lint → render (T17) → mux narration onto it → persist. `SEGMENT_CLIP_KEY`, `local_clip_path()`. |
| `core/graph/nodes/finalize.py` | Extended: concats every segment's clip (in order), persists the final video, still marks the job `SUCCEEDED`. `FINAL_VIDEO_KEY`. |
| `core/graph/nodes/synthesize.py` | Gained `local_narration_path()`, factored out so `render_scene` can reuse the exact same local-disk convention rather than round-tripping through `Storage`. |
| `mux/ffmpeg_run.py` | New — the shared spawn/timeout/kill ffmpeg-subprocess helper, extracted out of `frames_to_clip.py` once `audio_mux.py`/`concat_segments.py` needed the identical behavior. |
| `mux/audio_mux.py` | New — muxes a segment's narration WAV onto its silent rendered clip. |
| `mux/concat_segments.py` | New — joins every segment's clip with a real crossfade (`xfade`/`acrossfade`), not a hard cut. **The audio half of this is a known, accepted-for-now defect (D93) — read that before touching this file.** |
| `rendering/reveal.py` | Fixed: Tier 1's first capture no longer lands at the pre-animation blank instant (D95's sibling fix, technically part of the visual-quality pass but shipped alongside T18). |
| `rendering/templates/*.html`, `_tokens.html` | Redesigned visual identity — flat amber/blue, no glow/gradient, a breathing hairline frame as the one ambient device, IBM Plex Sans (D95). |
| `core/models.py` | `Segment.clip_key`, `VideoJob.video_key` — both nullable, fill in at the same stage their producing node runs. |
| Tests | `tests/test_audio_mux.py`, `test_concat_segments.py`, `test_render_scene.py`, `test_graph_pipeline_live.py` (new); `test_graph_pipeline.py`/`test_graph_resume.py`/`test_render_segment.py`/`graph_pipeline_fixtures.py` updated for the new fan-out and the redesigned templates. |

## What building T18 actually found

This task is the reason the phrase "verified against the real thing" appears so often in this
project's own history — it happened four more times here:

1. **`RUNTIME_ENV=azure` cannot drive a render at all** (D92) — `ContainerAppsRenderBackend` is
   still T35's stub. T18's own DoD ("plays on both stacks") was met by hand-mixing real Azure
   LLM/TTS with the real local render backend, not by `cli.py` alone. This is exactly what T18A's
   local entrypoint needs to make real and permanent.
2. **Crossfading narration audio was a design mistake** (D93) — two segments' speech audibly
   overlapping reads as the narrator interrupting themselves. The fix is designed (pad video only
   via `tpad`, keep audio a plain unshrunk concat) but not built; `mux/concat_segments.py` still
   ships with the mistake in it.
3. **A rendering bug in `diagram_flow`** (D94) — the rail line visibly cuts through node markers
   because the marker fill is only 10% opacity. Not fixed; the likely fix (an opaque marker
   background) is one line, in `rendering/templates/diagram_flow.html`.
4. **`hyperframes check` is flaky at the currently-resolved CLI version** (D96, 0.8.15) — the same
   unchanged composition alternated `ok: true`/`ok: false` across repeated runs. Not something this
   codebase can fix; expect it and re-run before trusting one red result.

Also found, and fixed same-session: no template ever actually linked a Google Fonts stylesheet, so
"Montserrat" had been silently falling back to system fonts since T17 (D95) — and the breathing
frame that replaced T17's particle field initially shipped with an opacity range too close to
`hyperframes check`'s documented 0.2 liveness floor, caught by `project-reviewer`'s checkpoint pass
and fixed to 0.22-0.32 before this checkpoint closed.

## Next task: T18A — bug fixes, a local entrypoint, a network-diagram intent

Full detail in `tasks.md`'s own T18A entry and in decisionlog D93/D94/D95's open items. Short
version:

1. **Fix the two known bugs** (D93's audio-overlap design, D94's marker opacity) — both root-caused
   already, neither fixed yet.
2. **A small local-only entrypoint** — one FastAPI route reusing `cli.py::_run()`, one static page
   with a text box and a video player. This is explicitly *not* the planned T19-T28 FastAPI+React
   product — a minimal dev tool, so a topic can be typed and a video played back without a manual
   script. Needs to resolve D92's adapter-mixing gap as real, labeled code (not a scratchpad script).
3. **`VisualIntent.NETWORK_DIAGRAM` via `/newintent`** — layered nodes with real weighted
   connections, aimed at the class of topic (neural networks, org charts, state machines) the
   existing six intents currently render as an abstract, topic-blind process.
4. **If time allows:** a storyboard step ahead of `plan_segments` letting one visual motif carry
   across several segments. Explicitly **not** in scope: fully bespoke per-topic animation (an LLM
   composing scenes from primitives instead of picking a template) — discussed and deliberately
   scoped out as a much larger, research-shaped undertaking.

## Verify at any time

```bash
pytest                                    # offline, no network -- green as of this checkpoint
pytest -m local_live                      # opt-in, needs the real browser/CLI/ffmpeg installed --
                                           # expect occasional false failures from hyperframes
                                           # check's own flakiness (D96), re-run before trusting red
ruff check . && ruff format --check .
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # must be empty
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # must be empty
```

No committed way yet to run a full job through `cli.py` alone (see D92) — for a real end-to-end
render, resolve adapters by hand the way this session did (`config._llm_provider`/`_tts_provider`
against an `azure`-flavored env, `config._render_backend` against a `local`-flavored one), or wait
for T18A's entrypoint.

## Environment state

| | |
|---|---|
| Models | Opus plans, Sonnet builds and reviews |
| `RUNTIME_ENV` | **`azure`** in both `.env` and `.env.example` (D25) — unchanged this task, and still cannot drive a full render alone (D92) |
| `FRAME_BUDGET` | **1400** (D78) — unchanged this task |
| `FPS` | 24, unchanged |
| `.env` | Exists and is filled in. Gitignored. Never commit it. |
| Azure sub | `d4a261bd-760c-41bd-9e22-ef58e2329ce0`. **`az login`'s cached auth had expired as of this session** — `az` CLI calls failed with an AADSTS530035 security-defaults error, and the Azure MCP connector returned zero subscriptions. Re-authenticate before relying on either for the real `/costs` figure. |
| Azure OpenAI | `skill-bites` (eastus) · deployment `gpt-5.4-mini` 2026-03-17, DataZoneStandard (D49) · api-version `2024-10-21` |
| Azure Speech | `skill-bites-tts` (eastus), S0 (D48) · voice `en-US-AvaMultilingualNeural` |
| Azure Storage | `sbitesartifacts25817` (eastus) · containers `explainer-artifacts`, `runtime-skills` — both real videos this session are there under their `job_id`s |
| Python | 3.11.0, venv at `.venv/`. Use `.venv/Scripts/python.exe` explicitly |
| Node | 24.16.0 · npm 11.13.0 · ffmpeg/ffprobe 8.1.1 on PATH |
| `langgraph` | `langgraph==1.2.11`, `langgraph-checkpoint-sqlite==3.1.1`, installed in `.venv` |
| HyperFrames CLI | **Drifted again, now 0.8.15** (was 0.8.12 as of T17's handoff, 0.8.10 before that) — still no `package.json` pin. **This version is measurably flaky under `check`** (D96) — worth investigating a pin if it keeps causing false-red results. |
| Playwright browsers | Installed — both `chromium-1234` *and* `chromium_headless_shell-1234` at `%LOCALAPPDATA%\ms-playwright` |
| Ollama, Kokoro | **Still not installed. Deliberately deferred (D59, reaffirmed D64)** |
| Git | on `master`, HEAD `b3dcf83`, **3 commits ahead of `origin/master`**, all from before this session — nothing from this session is committed yet. `origin` → `github.com/JuanTheMan21/s-bites.git`. **This line is fresh as of this checkpoint** (`git log`/`git status -sb`/`git remote -v` re-run just now), per D90's rule — do not carry it forward uncritically next time either. |
| Azure spend | Two real end-to-end videos produced this session (real LLM + TTS calls each). Estimated from narration length alone (TTS-only): ~$0.09/video. LLM token cost not itemized by any tooling in this repo. **Could not pull the real total** — see the `az login`/Azure MCP note above. |

## Before the next session

**Nothing code-blocking**, but two things worth doing if you want an exact cost figure or want
`hyperframes check` to stop giving false reds: re-run `az login` (or otherwise reconnect the Azure
MCP connector) before `/costs`, and consider whether to pin the HyperFrames CLI version.

## Known gaps and open questions

**New this task, not yet fixed (all detailed in decisionlog D92-D97):**

- **`RUNTIME_ENV=azure` alone cannot render a video** until T35 lands (D92). T18A's local
  entrypoint is the first thing that needs to work around this for real.
- **`mux/concat_segments.py` crossfades narration audio, audibly** (D93) — the fix is designed
  (video-only padding via `tpad`, audio stays a plain unshrunk concat) but not built.
- **`diagram_flow`'s rail line renders through its node markers** (D94) — an opacity fix, not built.
- **`hyperframes check` is non-deterministically flaky at CLI 0.8.15** (D96) — re-run before
  trusting a single red result; not fixable from this codebase.
- **Resume durability across `render_scene`/`finalize` is unverified** (D97) — both nodes
  reconstruct local-disk paths from earlier supersteps with no `Storage` fallback if the file is
  gone. Unlikely to bite the CLI's own single-machine use, but untested, and a real question once
  `working_dir` might not survive between processes (T35's eventual cloud render backend).
- **This video's color palette still reads "blue-dominant"** to a real viewer (D95's closing note)
  — the redesign is real (no more glow/gradient) but this topic's content mix (8/15 segments were
  `diagram_flow`) made the blue token dominate regardless. Worth a real side-by-side once T18A's
  richer diagram intent exists to compare against, not a color-value guess in isolation.

**Carried forward, unchanged:**

- **The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open** (D24/D67) —
  T18's CLI does not touch `JobQueue` at all (single one-shot run, never calls
  `JobQueue.fail(..., requeue=True)`), so it was never the right candidate to close this; still
  belongs to whichever future task builds a real queue-driven runner (T34).
- **No coverage gate exists (D42).**
- **`Segment.slots` is an untyped dict** (D29). Revisit at T24.
- **Scope: 36 tasks across 8 iterations** (35 plus T18A) — local stack priority still unsettled.
- **T10 stays `in-progress`, unclaimed.** Ollama/Kokoro still don't exist.
- **D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only** — T18 moved real
  MP4s through `Storage.put_file` for the first time but did not re-measure concurrency under that
  load; still open.

## Gotchas worth remembering

**New this task:**

- **Crossfading video is not the same move as crossfading audio.** A visual dissolve reads as
  polish; the same treatment on two different speakers' narration reads as interruption. Verify by
  listening, not just by checking durations — this project's tests only ever checked timing here,
  and timing was never the problem (D93).
- **A translucent fill doesn't hide what's behind it — it reveals it, dimly.** An element meant to
  occlude something (a node marker over a connecting line) needs real opacity, not a decorative
  low-alpha wash (D94).
- **`hyperframes check`'s pass/fail is not fully trustworthy at the currently-resolved CLI
  version** — re-run before treating one result as ground truth (D96).
- **A missing `<link>` tag fails silently.** A `font-family` naming a webface that was never loaded
  doesn't error, it just quietly falls back — the same class of bug as an unsized root or a manual
  `onUpdate` (D89), one more way "looks fine in a quick glance" and "is actually what you asked for"
  diverge without a real render/inspection to catch it (D95).
- **Renumbering a task sequence touches more than the task list.** Test assertions can contain
  literal task-number strings (`tests/test_adapter_stubs.py` matched exception messages against
  `"T34"`/`"T35"`); several source docstrings/comments do too. A lettered insertion (`T18A`) has
  zero blast radius; a renumber has to touch every one of those or go stale immediately (D98).

**Carried forward:**

- **A node-level `RetryPolicy` that also matches an error a node isolates locally defeats that
  isolation, silently** (D73).
- **Always add an import in the same edit as its first use** — bit again this session, twice, in
  `mux/frames_to_clip.py` and `core/graph/pipeline.py` (the quality hook strips an import that looks
  unused between two edits). Seven-plus sessions running now; treat it as a hard rule.
- **`project-reviewer` is worth running, and the *second* fresh full pass is the one that finds the
  bug** — held again this session (the opacity-floor finding, on a checkpoint-triggered pass after
  the task's own build was already believed done).
- **A confident claim about a library's or CLI's exact behavior is a claim until checked against
  the real thing.**
- **Check the *SKU's* quota, not the model's availability** (D49).
- **Windows path semantics**: a trailing dot is stripped on existence checks but not on directory
  enumeration (D46).
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
