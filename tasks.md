# Task Backlog

38 tasks across 8 iterations (T36 and T37 both added 2026-09-04, mid-Iteration-5 — T36 at explicit
user request during the T24-T28 session, D136; T37 scoped as a follow-up once that session's real
end-to-end use surfaced both a real backend bug and a visual-design rejection, D144). **One task
per session** (though iterations have twice now been built as one combined session by explicit
user choice — T19-T23 and T24-T28+T36, both recorded in decisionlog.md). Descriptions are
deliberately high-level — detail is negotiated in plan mode at the start of each session, not
pre-baked here.

Status: `todo` · `in-progress` · `done` · `blocked`

Loop: `/build-task Tn` → agree → build (Sonnet/Haiku) → `project-reviewer` → `/checkpoint`

---

## Iteration 0 — Scaffolding & operating system

### T1 — Repo scaffold · `done`
Git repo, venv layout, dependency manifests, ruff/pytest config, the full directory skeleton, and
the three documents that outlive any single session: `README.md`, `CLAUDE.md`, `.env.example`.
**DoD:** directory tree matches `CLAUDE.md`; `ruff check .` runs clean.

### T2 — Operating system · `done`
Everything that makes later sessions cheap and consistent: the task/decision/handoff documents, the
eight custom commands, the hook set that mechanically enforces the architectural rules, the two
review agents, build-time skills, and MCP wiring.
**DoD:** `/build-task` and `/checkpoint` run; boundary hook demonstrably blocks a bad write.
**Depends:** T1

---

## Iteration 1 — Contracts & pure core *(no network in this entire iteration)*

### T3 — The six interfaces · `done`
Abstract contracts for `LLMProvider`, `TTSProvider`, `Storage`, `SkillRegistry`, `JobQueue`,
`RenderBackend`. Signatures must be expressible by both a local and an Azure implementation without
either leaking vendor types. `LLMProvider.generate` takes a pydantic model class so strict schema
enforcement is available to adapters that support it.
**DoD:** all six ABCs typed and importable; nothing else in the repo imports them yet.
**Depends:** T1

### T4 — Domain models · `done`
`Segment`, `VisualIntent` (closed enum), `Tier`, `VideoJob`, plus the per-intent pydantic slot
schemas the LLM fills. These same models serve LLM structured output, internal state, and later the
API contract — one definition, three uses.
**DoD:** models cover every visual intent; schemas satisfy Azure strict-mode constraints.
**Depends:** T3
**Flagged in T3 planning — target length must be a parameter.** `VideoJob` carries
`target_duration_ms`; nothing may hardcode 7 minutes or 15 segments. Segment count is *derived*
(~28s of narration each), so a 10-minute request yields ~21 segments on its own.

### T5 — Tier resolver · `done`
The pure function at the heart of the render budget: importance-ranked segments in, tier
assignments out, under a global frame budget. No I/O, no LLM, no clock. The one piece of this
system with no excuse for external dependencies.
**DoD:** `core/tier_resolver.py` imports nothing but stdlib and `core.models`.
**Depends:** T4
**Flagged in T3 planning — the frame budget is an argument, not a constant.** The caller scales it
with `target_duration_ms` under a hard ceiling. `FRAME_BUDGET` is really a *render-time* budget
(D16: 1.7-2.7 frames/sec), so linear scaling with no cap turns a 20-minute video into a 20-minute
render, and no scaling at all spreads 600 frames so thin that everything lands on Tier 0.

### T6 — Test foundation · `done`
Thorough unit tests for the tier resolver — budget exhaustion, ties, degenerate inputs, and a
realistic 7-minute case asserting all three tiers appear — plus in-memory fakes for all six
interfaces so every later task can be tested without network.
**DoD:** `pytest` green; tier resolver at full branch coverage.
**Depends:** T5
**T5 already shipped part of this.** `tests/test_tier_resolver.py` covers the realistic 7-minute
case, the unmeasured-segment raise, empty input, zero budget, determinism under shuffle, and
intent-registration completeness. T6 is the *remaining* branches — the argument-validation
raises, `tier_for`'s `KeyError`, `scale_frame_budget`'s guards, `ideal_tier`'s unreachable branch
(monkeypatch `TIER_SUPPORT`; do not weaken the real map), and a budget that binds mid-pass-1,
which no fixture currently exercises. `--cov-branch` is not in `pyproject.toml` and must be
passed or added. **The fakes are the larger half** — 21 async methods across six interfaces, and
every task from T14 on is tested against them.

### T7 — Runtime skill registry · `done`
Versioned prompt packs the *pipeline* loads at runtime, so the system starts from accumulated
knowledge rather than a cold prompt. Registry behind an interface; packs on disk locally, in Blob
on Azure, updatable without redeploying code.
**DoD:** four packs load through the interface; pack content is data, not code.
**Depends:** T3
**T6 wrote the reference semantics.** `tests/fakes/skill_registry.py` already encodes the
asymmetry the contract requires — `load` raises `SkillPackNotFound` for an unknown pack *or*
version, while `versions` returns an empty list and never raises. It also defines `version_key`,
a numeric-aware "newest first" rule, because a string sort puts `2.10` below `2.9`. **T7 must
adopt that rule or replace both** (D41): the two only diverge once a pack has a second version,
which is late and quiet. Which four packs is not specified anywhere — decide it in plan mode,
since it determines what T15 and T16 can ask for.

---

## Iteration 2 — Azure provisioning & adapters

### T8 — Azure groundwork · `done`
Resource group, model deployment, Speech resource on the free tier, storage account, credentials
into `.env`. **Verify non-zero TPM quota before writing any adapter code** — this is the step that
fails silently on a mis-provisioned subscription.
**DoD:** a raw completion and a raw TTS call both succeed from the command line.
**Depends:** T1

### T9 — Azure LLM adapter · `done`
Azure OpenAI behind `LLMProvider`, with strict JSON-schema structured output, retry/backoff on rate
limits, and a concurrency bound matched to deployment throughput. All resilience lives here, never
in `core/`.
**DoD:** returns validated model instances; survives an induced rate-limit response.
**Depends:** T3, T8

### T10 — TTS adapters · `in-progress`
Azure Speech (primary) and Kokoro (offline), both returning audio plus **measured** duration. That
measured duration is what every downstream timing decision depends on.
**DoD:** both satisfy `TTSProvider`; durations match `ffprobe` within tolerance.
**Depends:** T3, T8
**The Azure half is done.** `AzureSpeechTTS` ships with retry, both failure surfaces translated,
and a live test asserting agreement with `ffprobe` within 50ms — observed delta is 0ms.
**Kokoro does NOT close this via T12 after all (D59 reopens D58's plan a second time).** T12
shipped Azure-focused by user decision — Ollama and Kokoro are both cut, pushed to a future,
not-yet-numbered task. **This task stays `in-progress` with no task currently claiming it.** Pick
the next local-stack task up when that priority returns; nothing about the Azure half needs
revisiting then.
**Duration is measured from the file, never reported by the SDK (D54).** Both adapters call
`adapters/audio_duration.wav_duration_ms`, which needs a **RIFF PCM WAV** — Kokoro emits float
arrays, so whatever writes them must produce PCM. If it cannot, widen `audio_duration.py`; do not
add a second measurement path.

### T11 — Storage adapters · `done`
Blob and local disk behind `Storage`, plus the Blob-backed skill registry from T7.
**DoD:** identical behavior for put/get/url across both; skill packs load from Blob.
**Depends:** T3, T7, T8
**T6's `FakeStorage` already set the spec** (D39). Keys are relative POSIX strings, and it rejects
absolute paths, backslashes, `..` and empty keys with `ValueError` on **all six** methods — an
absolute key escapes the disk adapter's root once there is a real filesystem behind it. Match
that, or if a real backend legitimately accepts something the fake rejects, change the fake and
record why. Note it applies to `exists` too, which is not a contradiction of "never raises for a
missing key": malformed is not the same as absent.
**T7 added two more rules the Blob registry must match, and reusable code to match them with.**
`adapters/skill_pack_format.py` is backend-agnostic — the Blob registry parses the identical bytes
with `parse_pack` and validates names with the same `check_pack_name`/`check_version`, so this is
a fill-in rather than a reimplementation. The rules: a malformed name raises `ValueError` even
from `versions()`, which the contract otherwise says never raises (D45); and a name may not end
in `.` (D46) — that one is Windows-specific in origin but the aliasing it caused would be a blob
naming bug too. Add the new registry to `REGISTRIES` in `tests/test_skill_registry_parity.py`;
the assertions there already exist and should pass unchanged.

### T12 — Local render backend & job queue; Azure stubs · `done`
Playwright + the HyperFrames CLI behind `RenderBackend` (one persistent browser drives Tier 0/1
stills, the CLI drives full renders and the lint gate), plus an in-process asyncio `JobQueue`.
Service Bus and Container Apps get signature-matched stubs that raise clearly — stubs are what
make the interface boundary reviewable rather than aspirational.
**DoD:** `RenderBackend` and `JobQueue` local adapters complete; stubs match signatures exactly.
**Depends:** T3 — met.
**Rescoped during planning, by user decision (D59): Ollama and Kokoro are cut from this task**,
pushed to a future, not-yet-numbered task — staying Azure-focused for now rather than reopening
Kokoro's Windows risk (D6, D58) a second time. Only two local adapters shipped here, not four.
**`RenderBackend`'s design is genuinely two implementations in one class (D60):** `capture`
(Tier 0/1) drives Playwright directly, one browser kept alive across calls; `render`/`lint`
(Tier 2, and the validation gate) shell to `npx hyperframes`. Not a local-vs-Azure split — the
same code is what T35's Container Apps job runs inside a container later.
**A real, load-bearing assumption for T17 to confirm (also D60):** the HyperFrames CLI's `lint`
has no way to target one file — it always validates a whole project directory and hardcodes
`index.html` as the entry point. This adapter assumes each composition lives alone in its own
directory named `index.html`, and raises loudly rather than silently misbehaving if that's not
true. Check this the moment T17 picks a real directory layout for generated compositions.
**D47's open item did NOT get measured this task, despite being live now.** The asyncio `JobQueue`
built here is the first thing capable of running jobs concurrently on one loop — but the actual
measurement of whether `DiskStorage`/`DiskSkillRegistry`'s synchronous I/O stalls concurrent jobs
never happened. **Still open, carried forward** — do it before or during whichever task first runs
real concurrent jobs against local storage (likely T14 or T16, not necessarily T13).
**Three bugs found by review and fixed before checkpoint (D61, D62)** — worth reading before
touching `adapters/local/playwright_capture.py` or `hyperframes_cli.py` again: GSAP's `.seek()`
must have its return value discarded in `page.evaluate` (implicit return hangs the whole call), a
timed-out `hyperframes` subprocess must have its whole process tree killed on Windows or it leaks
node/chrome-headless-shell children, and `page = await browser.new_page()` must be *inside* the
try block that translates exceptions to `RenderFailed`, not before it.

### T13 — Config resolver & parity · `done`
`config.py` — the single module permitted to name concrete classes — plus parity tests proving both
implementations of each interface agree on signature and semantics.
**DoD:** flipping `RUNTIME_ENV` swaps every adapter with no change in `core/` — met for `azure`.
**Depends:** T9, T11, T12 — met. **T10 is listed as a dependency and is still not `done`** (see its
entry): Ollama and Kokoro don't exist yet, and there's no task currently building them. **Decided
in T13's own planning (D64), by user choice:** `RUNTIME_ENV=local` resolves `Storage`,
`SkillRegistry`, `JobQueue` and `RenderBackend` for real, and `build_adapters()` raises a clear,
named `RuntimeError` for `LLMProvider`/`TTSProvider` under `local` rather than adding stub adapter
classes or narrowing this task's scope. Whichever future task closes T10 only has to fill in
`config._llm_provider`/`_tts_provider`'s local branch and drop `build_adapters()`'s upfront raise.

---

## Iteration 3 — Pipeline & rendering

### T14 — LangGraph skeleton · `done`
Graph state, checkpointing, per-segment fan-out, and resume-after-failure. Scoped strictly to
`core/graph/`; nodes call interfaces like everything else.
**DoD:** a killed run resumes without repeating completed segments — met, pinned by
`tests/test_graph_pipeline.py::test_a_killed_run_resumes_without_repeating_completed_segments`
against a real file-backed `AsyncSqliteSaver` (D68).
**Depends:** T6, T13 — met.
**`plan_segments` is a deliberate placeholder** (D70) — deterministic segments, no LLM call. T15
replaces its *body*, not the graph shape in `core/graph/pipeline.py`.
**D24's `StructuredOutputError` cap is only half-closed (D67).** `core/graph/retry_policy.py`
gives it its own node-level bounded `RetryPolicy`, but the cross-*requeue* half D24 asked for
(via `QueuedJob.attempt`) is structurally impossible from inside `core/graph/` — `GraphContext`
deliberately excludes `JobQueue` (D66). Whichever future task builds the runner that calls
`JobQueue.fail(..., requeue=True)` owns closing this for real.
**D47's disk-concurrency question is measured, not carried forward again** — see D69.
`scripts/measure_segment_concurrency.py` is the reusable script; re-run once T18 moves real
rendered artifacts (not small WAVs) through `Storage`.

### T15 — Outline & scripting nodes · `done`
Topic to segments to narration, driven by the runtime skill packs. Produces roughly 15 segments for
a 7-minute target.
**DoD:** structured output validates on every segment; skill packs demonstrably change behavior —
met. `core/graph/nodes/outline.py::generate_outline` and `.../scripting.py::write_narration` make
the real calls; both are exercised live in `tests/test_live_plan_segments.py` against the real
Azure deployment and the real disk-loaded packs.
**Depends:** T14 — met.
**T7 shipped the packs this node loads.** Four exist, all at `1.0`: `outline` and `scripting` are
this task's, `scene-authoring` is T16's, and `house-style` is interpolated **alongside** each of
the other three rather than used alone (via `core/graph/nodes/skill_prompt.py::load_step_prompt`,
reusable by T16). **They worked at `1.0` against a real model — no `1.1` was needed** (D75).
**T4 built the schemas this node fills.** `core.outline_schema.Outline` and the new
`core.scripting_schema.Narration`; segment count comes from `VideoJob.segment_count`, never a
literal, per the T4 flag. The outline call does not enforce the model returned exactly that many
segments (D74) — nothing downstream needs an exact count.
**A real retry-policy bug shipped in this task's first version and was caught by review (D73):**
a node making several sequential `LLMProvider` calls (this one makes up to `1 + segment_count`)
needs its own local `StructuredOutputError` isolation (`core/graph/nodes/structured_retry.py`)
*and* must register with the new `core/graph/retry_policy.py::build_transient_retry_policy()`
rather than `build_retry_policies()` — attaching both silently defeats the isolation by letting
an exhausted local retry re-trigger a whole-node redo. **T16's scene-authoring node will hit the
same trap if it copies `synthesize_segment`'s registration pattern instead of this one's.**

### T16 — TTS, tiering & scene authoring · `done`
The ordering-critical stretch: assign tiers against real measured durations, then fill scene slots.
**DoD:** timing attributes derive only from measured audio — **met**; tier spread covers all three
tiers — **met for Tier 1 and Tier 2 only, and the item is recorded as over-specified (D79).**
**Depends:** T15 — met.
**Graph shape, decided (D76):** `synthesize_segment` → `assign_tiers` (join, needs every duration)
→ a *second* `Send` fan-out → `author_scene` → `finalize`. Rejected folding scene authoring into
`synthesize_segment` (it would put slots before tiers, and make a scene retry re-synthesise billed
audio) and a sequential join node (~15 serial calls, and a retry redoes every authored scene).
`core/graph/nodes/tiering.py` and `.../scene_author.py` hold the two new nodes; `GraphContext`
gained `frame_budget` and `fps` (D77).
**Invariant 1 is structural here:** `fill_slots` takes `duration_ms` as a required parameter, so a
caller who has not measured cannot satisfy the signature, and `author_scene` raises before any LLM
call on an unmeasured segment.
**`FRAME_BUDGET` is now 1400, and D32 understated the problem (D78).** At real measured durations
600 bought **zero** Tier-2 scenes — real narration runs a uniform 19-29s per segment, so there are
no short segments for Tier 2 to land on, not even title cards. Measured curve: 900→1 animated,
1400→2, 2000→3. Tuned with `scripts/tier_dry_run.py` against a live run, never a fixture.
**An `outline` `1.1` was written, measured, and deleted (D80)** — it did not change the outcome.
The finding it chased is carried forward: the outline model rates importance on merit rather than
ranking, so most segments ask for a tier the budget cannot afford.
**`/tiers` is now executable** — `scripts/tier_dry_run.py`, and the command file's stale "estimated
duration" / "one LLM call" claims were corrected (D81).

### T17 — The three renderers · `done`
Static screenshot, multi-state reveal with crossfade, and full HyperFrames animation — one module
per tier, with composition linting before render.
**DoD:** each tier produces a valid clip — met, verified against the real backend for all 6
`VisualIntent` × 3 `Tier` combinations (`tests/test_render_segment_live.py`); invalid compositions
are caught before rendering — met, `render_segment.py`'s lint gate.
**Depends:** T16 — met.
**Six Jinja templates shipped, one per visual intent** (D30), sharing one design system
(`rendering/templates/_tokens.html`, "Data Drift" style, D83) rather than each inventing its own.
**The composition-directory-layout question is closed** (D85): always the sole file
`dest_dir/index.html`. **`mux/frames_to_clip.py` also shipped here**, ahead of T18, since ffmpeg
calls belong in `mux/` project-wide per CLAUDE.md regardless of task number (D84) — T18 only needs
to add audio mux + concat alongside it.
**Real bugs found only by the live toolchain** (`npx hyperframes check`, real Playwright seeks),
none catchable offline — full detail in decisionlog.md D89. The one every future template author
needs to know: **ambient/idle motion must be a genuine GSAP property tween, never a manual
`onUpdate` DOM write** — HyperFrames' `seek(id, t, true)` convention (D15) skips `onUpdate`
callbacks entirely.

### T18 — Mux & CLI · `done`
Per-segment audio mux, then concat, then the CLI entrypoint. **This task produced the first
complete video.**
**DoD:** `python cli.py "<topic>"` yields a playable ~7-min MP4 on both stacks; no drift — met for
`RUNTIME_ENV=azure`'s LLM/TTS paired with the real local render backend by hand (see decisionlog);
`cli.py` itself cannot yet run either stack fully standalone, since `RUNTIME_ENV=azure`'s
`RenderBackend` is still T35's stub. Two real bugs found only by watching/listening to the actual
output (a rendered rail line showing through its own node markers; crossfaded narration audio
reading as the narrator interrupting themselves) are carried forward into T18A, not fixed here.
**Depends:** T17 — met.

---

Task numbers are identity, not order: **T18A runs here**, right after T18 and before iteration 4,
so nothing already numbered T19 onward has to shift.

### T18A — Kill the slideshow: corrected render throughput, full-duration motion, word-timed captions, the two carried-forward bugs, a real local entrypoint · `done`
**Rescoped during planning, by user decision (see decisionlog D99-D103).** A real viewer's verdict
on T18's two videos ("looks like a slideshow") traced to a measurable cause, not a template
quality problem: D16's frame-throughput figure was wrong by roughly 6-10x (a 3-second sample
dominated by cold-start overhead), so `FRAME_BUDGET` funded Tier 2 for only 2 of 15 segments. Real
throughput measured with `npx hyperframes benchmark` (~17 frames/sec), `FRAME_BUDGET` raised
1400 → 9500, and `core/tier_resolver.py::IDEAL_TIER` raised so every non-ASIDE segment targets
`Tier.ANIMATED`. This is the task's actual center of mass; everything below builds on it.

Also shipped: word-level TTS timing (`WordMark`/`SynthesisResult`, `interfaces/tts_provider.py`,
D101) driving in-frame captions (`rendering/templates/_captions.html`) and an SRT sidecar
(`mux/subtitles.py`); per-job color palettes (`rendering/palettes.py`, six contrast-checked
options); a real count-up for `stat_callout` (`value_number`/`prefix`/`suffix`, ported from the
registry's `count-up` component's technique); GSAP vendored locally instead of CDN-loaded; both
carried-forward bugs fixed for real and verified against the real toolchain, not just redesigned
(D93's narration crossfade — confirmed via spectral analysis, not only duration assertions; D94's
`diagram_flow` marker opacity); and a `RENDER_ENV` bridge (`config_render.py`, D100) that finally
closes D92 — `cli.py` with no arguments now runs a full job standalone, real Azure LLM/TTS paired
with the real local render backend, with no hand-mixing outside committed code.

**Explicitly NOT this task, deferred to T18B:** `VisualIntent.NETWORK_DIAGRAM`, the storyboard/
motif step, the FastAPI+React local page (replaced this session by a bare stdin prompt in `cli.py`
instead — sufficient for the DoD's "no manual script" bar, and the user's own call in planning),
LLM-composed-from-primitives scene authoring (still out of scope — see the original T18A entry's
reasoning, preserved via decisionlog rather than repeated here), background music/SFX, and the
`hyperframes render --variables`/`--batch` composition refactor.

**DoD:** both bugs verified fixed by a real render and a real listen — met (D103). A topic given
to `cli.py` (typed as an argument, or at the prompt when omitted) produces a playable video with
no manual script involved — met, verified end to end with a real Azure-backed run. The new intent
— deferred to T18B, not met here.
**Depends:** T18 — met.

### T18B — Compositional scenes, whole-video visual planning, narration-anchored motion · `done`
**Rescoped a second time before this task's own build**, on the user's explicit instruction after
reviewing T18A's real output again: reopen decisionlog D104's "richer fixed template set, not
fully compositional" boundary outright, forget prior architecture/cost assumptions while
planning, keep only the ~15-20 minute render ceiling. Supersedes the version of this entry the
previous checkpoint wrote. Full reasoning: decisionlog D105-D109.

**What actually shipped:** the one-`VisualIntent`-picks-one-whole-template dispatch is gone,
replaced by a `SceneLayout` (`SINGLE`/`SPLIT_HORIZONTAL`) composing `BlockType` partials (6:
`title`, `text_panel`, `stat_callout`, `code_panel`, `diagram_chain`, and `array_grid` — the one
genuinely new block, no pre-T18B equivalent, built for exactly the array/list-halving pattern the
original scoping's reference video called for). A new join node, `plan_visuals`
(`core/graph/nodes/visual_plan.py`), sees every segment at once and plans the whole video's
layouts/blocks/motif in one call — the structural fix for the repetition the original scoping
blamed on template variety, when it was actually the per-segment fan-out's isolation (D105).
Content is filled one block at a time (`author_scene`'s `fill_block`), routing around Azure strict
mode's real inability to express a discriminated union (D29) rather than asking for a whole scene
in one call. Cue-based captions, motif-keyed palettes (Blueprint/Terminal/Broadcast, replacing six
job-id-hashed ones), narration-anchored block/item timing (`rendering/anchors.py`, spending
`word_marks` on visuals for the first time, not just captions), a scene-level camera drift on
every layout, and a structural (code, not prompt) forced title card on segment 0 are all in.

**DoD, as actually met:** `pytest` green (562 passed), `ruff` clean, boundary/line-count checks
clean. `hyperframes check` green for every layout × block combination shipped, via a real 18-combo
live sweep (`test_render_segment_live.py`, 6 block types × 3 tiers) — four real bugs found only by
running the real toolchain, all fixed and verified (D106). One real end-to-end render, watched via
extracted frames, not just duration-asserted (D109) — 90s/3-segment "how binary search works",
`Tier.ANIMATED` throughout, a genuinely distinct Blueprint motif, working `diagram_chain` and
`SPLIT_HORIZONTAL` output. Full 7-minute length **not required this task, by design** — see T18C.

**Explicitly not this task** (still true, now for updated reasons — see T18C below for where each
lands): the broadened primitive set beyond this task's 6 block types (arbitrary graph topology +
traversal, sequence/lane diagrams, timelines, code diff, generalised annotation/warning
components); a vision critique/revision loop (needs a real `LLMProvider` image-input interface
change, its own adapter-parity work); a full 7-minute validation render across varied topic types.
Mermaid-rendered diagrams remain rejected for the reasons D104 already gave. The originally-listed
"two new intents" framing is superseded — `array_grid` shipped as a `BlockType`, not a
`VisualIntent`, and the composite code+diagram split is just `SPLIT_HORIZONTAL` with any two
blocks, not a dedicated intent either.

**Two pre-existing gaps found during this task's own verification, carried forward, not fixed
here** (D107): the Blob skill registry had drifted from local disk since T18A (fixed as a one-off
manual sync this session; no automated sync exists); `tests/test_graph_pipeline_live.py`'s
mixed-tier test is mathematically unsatisfiable under the post-D99 tier ladder (a T18A-era gap,
not a T18B regression — worked out by hand in D107, needs a real redesign of that test's segment
shape, not a constant tweak).

**Depends:** T18A — met.

### T18C — The broadened block library · `done`
**Scoped during T18B's own planning** (decisionlog D104-D105), deliberately deferred rather than
crammed into T18B so the genuinely novel, highest-craft work gets a full session's attention
instead of being squeezed at the end of an already-large one.

**Rescoped during this task's own planning, by the user's agreement:** the entry below originally
bundled the block library with the vision critique/revision loop and a full 7-minute validation
render. Too much for one session — each new block type has historically needed its own
real-toolchain verification pass (D106: four real bugs found only by the actual toolchain, across
just one new block last time). **What actually shipped is the block library only, plus two related
pre-existing gaps this task's own research surfaced** (the caption/content-overlap check the
original entry below already named, and D107's mixed-tier live test fix). The vision loop and the
validation render are deferred to a new, not-yet-scoped **T18D** — see that entry below, which also
absorbs the "make video generation faster" request raised mid-planning and the previously-vague
"push LLM compositionality further" placeholder this section used to point at. Full reasoning:
decisionlog D113-D118.

**What actually shipped, DoD as met:** `GRAPH_DIAGRAM` (retiring `DIAGRAM_CHAIN`, both CHAIN and
GRAPH layout modes, D113), `ARRAY_GRID` generalized to four step ops plus orientation (D114),
`CODE_DIFF`, `SEQUENCE_DIAGRAM`, `TIMELINE`, and a new cross-cutting annotation overlay system
(cursor/check/warning — not a `BlockType`, D115). The caption/content-overlap check is real and
closed (D116): a genuine pre-existing 24px gap between `#stage`'s padding and the caption band was
found and fixed, and `hyperframes check --caption-zone` is now wired into the real toolchain test
— its findings fold into the existing `layout` category, no new assertion needed. D107's mixed-tier
live test is fixed (D117), retargeted to a genuinely reachable tier pair rather than the
mathematically-unreachable one it asked for before. `pytest` green (640+, up from 622), `ruff`
clean, boundary/line-count checks clean, and every new block type (plus both `GRAPH_DIAGRAM`
modes, all four `ArrayStep` ops, and annotations in both layouts) verified against the real
`hyperframes check` toolchain — two real bugs found this way in the annotation positioning
mechanism, both fixed and re-verified (D115), plus a third found by `project-reviewer`'s own final
pass in this task's *own new test coverage*, also fixed (D114).

**Not done, explicitly deferred to T18D, not silently dropped:** the vision critique/revision loop
and the full 7-minute validation render (both described below, unchanged from the original scoping
— still real, still not started). **Not done, flagged as trust-blocking in `handoff.md`, not
silently skipped:** no `pytest -m local_live` run and no real `cli.py` render of any new block type
— this task's own real-toolchain verification used standalone `hyperframes check` probes against
hand-composed scenes, never the actual render/capture path.

**Scope, reasoned past the user's own three named examples per their explicit instruction not to
limit the block library to those** — what a general "prompt-to-explainer-video" platform actually
gets asked for, each new block earning its place the way D30 required of the original six:
- **`GRAPH_DIAGRAM`** — arbitrary node/edge topology plus a traversal-highlight mode (an
  `offset-path-traveler`-derived technique, per this session's HyperFrames registry research).
  Covers graphs, trees, DP state-transition diagrams, and linked lists as a degenerate case,
  without a block type per structure. `diagram_chain`'s existing linear-rail mode absorbs into
  this as one of its layouts, not a separate block.
- **`ARRAY_GRID`, generalized** — an orientation + end-operation field so the same block covers
  stacks, queues, and sliding windows, not only binary-search-style halving.
- **`SEQUENCE_DIAGRAM`** (new) — actors/lanes with arrows over time, for protocol/handshake/
  request-response topics (TCP, OAuth, HTTP) a node-graph represents badly, since they're
  lane-and-time shaped rather than topology-shaped. A common "how does X work" question class this
  project currently has no good answer for.
- **`TIMELINE`** (new) — a horizontal run of labelled events for historical/evolutionary topics.
  Cheap once `GRAPH_DIAGRAM`'s traveler technique exists.
- **`CODE_DIFF`** — before/after, red-collapse/green-expand. Direct registry port
  (`code-diff`).
- **Annotation components** — `ANNOTATION_CURSOR`, `ANNOTATION_CHECK`, and a generalised
  `ANNOTATION_WARNING` (past "malicious intent" specifically, to any "here is the dangerous part /
  the common mistake" beat — a frequent explainer moment, not just a security-topic one).
  Malicious/glitch *treatment* is a style override on `CODE_PANEL`/`CODE_DIFF`, not a block type,
  keeping motif orthogonal to content.
- **The vision critique/revision loop**, the third of T18B's own three-part answer on tightening
  the agentic harness (decisionlog D105 §7): capture stills from a composed scene
  (`adapters/local/playwright_capture.py` already does this for Tier 0/1), show them to a
  vision-capable model, critique, revise the scene plan, re-render only what failed. Requires a
  real `interfaces/llm_provider.py` change (image input) — `LLMProvider.generate` is text-only
  today — and the adapter-parity work that follows from it (both Azure and local, D40's
  `inspect.signature` equality across every implementation including the fake).
- **Validation:** a full 7-minute render across 2-3 genuinely different topic types (algorithmic,
  systems/protocol, security) — where D104's original "one real full-length render" promise
  properly lands, against content that will actually show the payoff T18B's foundation bought.
- **Caption/content overlap is currently unchecked, not just unlikely.** `_captions.html`'s band
  sits inside `hyperframes check --caption-zone`'s guard by construction (a fixed bottom inset),
  but that guard only ever verified the band's *own* position — nothing checks whether a block's
  *content* grows down into that same zone. `SINGLE`/`SPLIT_HORIZONTAL`'s `#stage` padding leaves
  the same rough margin captions already occupy, so this hasn't bitten yet, but T18C's own new
  blocks are denser (`SEQUENCE_DIAGRAM`'s lanes, `TIMELINE`'s event row, `CODE_DIFF` against a
  long file) and more likely to reach the bottom of the frame than T18B's six. Actively check this
  — `npx hyperframes check --caption-zone` against every new block, not just trust the fixed
  inset — before shipping any of them, and prefer a block design that reserves its own bottom
  margin over one that merely hasn't overflowed yet in the fixtures anyone happened to try.

**Also in scope, cheap given T18B's foundation:** fixing `tests/test_graph_pipeline_live.py`'s
mixed-tier test (D107) — needs a real segment-shape redesign, a natural fit alongside other live-
test work this task already does.

**Explicitly not this task:** the document-upload/cursor-navigated-UI-walkthrough direction —
confirmed the best-supported thing in this session's own HyperFrames research
(`browser-device-stage`/`simulated-cursor`/`ui-focus-zoom` already take data-driven coordinates),
but waiting on a document-ingestion path that doesn't exist yet (T29's scope, iteration 6,
scheduled last per the original requirement).
**Depends:** T18B — met.

### T18D — Systematic real-render bug catalog for the block library · `done`
**Scoped during a post-T18C-checkpoint verification render, by the user's own direct critique of
the real output** (decisionlog D120). The checkpoint's own single verification render (D119) found
and fixed one real bug, but watching the actual video turned up several more the toolchain-only
checks never could — the same lesson D89/D106/D109/D119 already recorded, recurring again. Rather
than fix piecemeal in an already-large session, this task **only catalogs** — render, watch,
document, categorize by root cause where one can be traced. **No fixing in this task**; T18E does
that, once the catalog is complete. Video generation itself is deliberately deferred to this task's
own fresh session, not squeezed into whichever session scopes it (context-budget discipline, per
the same session that wrote this entry).

**Seed the catalog with the findings already in hand, not summarized away** (D120 has the full
detail):
- **Static/low-motion segments can run far longer than their narration justifies, with nothing new
  appearing on screen** — a title card sat still for ~25s while narration moved well past it. The
  "slideshow" problem T18A/T18B already fought once, recurring somewhere neither task's fixes
  covered. Two options the user raised worth testing: more/shorter segments, or narration-timed
  supporting content appearing even on an otherwise-static card.
- **`SEQUENCE_DIAGRAM` annotation coverage**: the user expected all three messages in a handshake
  (SYN, SYN-ACK, ACK) to get their own annotation, one by one as each was spoken; only one or two
  did. Check whether `visual-plan`'s "use annotations sparingly, one or two per scene" guidance is
  actively wrong for a case where per-step marking is exactly the right call, or whether this is a
  planning-choice issue instead.
- **`GRAPH_DIAGRAM` GRAPH-mode layout**, already confirmed broken two ways (D119): node overlap in
  a compact/split canvas (root cause traced — the circular auto-layout fallback assumes a square
  canvas), and one node's entrance timing landing outside its own segment's window entirely, while
  the other four appeared together rather than individually. **The user's own proposed
  alternative, worth carrying into T18E's design directly**: stop anchoring every node's entrance
  to its own narration mention (fragile — short/generic labels can mismatch, the same class of bug
  D119 already fixed once for a different block type) and instead reveal the whole graph up front,
  letting the traversal dot alone carry the "explained in order" storytelling — or, if per-node
  reveal is kept, make it reveal correctly one-by-one or not at all, never a mix.

**Render a deliberate topic matrix, not random topics** — chosen to individually stress block
types/situations this session's one video never touched: `ARRAY_GRID` with a real `shift`/`push`/
`pop` sequence (not just `narrow`), `CODE_DIFF`, `TIMELINE`, `GRAPH_DIAGRAM` in `SINGLE` layout
(isolating whether the overlap bug is specific to the compact/split canvas or broader), a
`SEQUENCE_DIAGRAM`-heavy topic with more actors/messages, and a scene with multiple annotations in
one segment. Prefer topics where a specific block type is the *obvious* choice over topics that
merely might invite it.

**Watch every render properly** — full playback or dense frame extraction, not just `hyperframes
check` (which caught none of D120's real problems: wrong timing, wrong pacing, and layout overlap
are all things the checker's structural/contrast/lint passes don't evaluate).

**What actually shipped:** exactly the six-topic matrix D120 specified, plus a pre-flight Blob
skill-registry sync (the same drift D107 fixed once before had recurred). All six real renders
watched via targeted frame extraction cross-referenced against each segment's own authored timing
arrays — not just eyeballing frames. Findings written up in `t18d_catalog.md`, not summarized into
this file — see decisionlog D121 for the short version. The catalog's headline finding is new,
not one of D120's three seeded items: `rendering/block_timing.py`'s per-item anchor fallback
(`_ITEM_FIELDS`: `graph_diagram.nodes`, `text_panel.items`, `code_diff.lines`) is index-only and
ignores sibling timing, producing collapsed/scrambled/duplicate reveals in 9 of ~20 timing arrays
sampled — likely the closer-to-the-surface shared root cause this entry's own T18E note already
speculated about. All three of D120's seeded findings were confirmed and refined (not just
re-confirmed): title-card staleness has a second, distinct cause; `GRAPH_DIAGRAM` overlap is
confirmed `SPLIT_HORIZONTAL`-specific and clean in `SINGLE` (a real isolation result, not a
guess); annotation coverage is capped at one-per-scene by design (`visual-plan` guidance), not
accident. Two new text-collision bugs found. No code changed — this task's own DoD explicitly
forbade fixing anything found (D120).

**Immediately after this checkpoint, in the same session:** the user watched all six videos
directly and gave further critique the catalog didn't cover (repetitive/generic visuals across
topics, `GRAPH_DIAGRAM` reading as structurally meaningless, annotations feeling random, and a
render-speed regression vs. T18A). An independent Opus-model analysis (fresh context, no access
to this catalog's conclusions) traced each to a specific cause — see D121. That analysis plus the
user's own scope choice produced T18E's real scope below, replacing this entry's old placeholder.

**Depends:** T18C — met.

### T18E — Fix pass: annotations, GRAPH_DIAGRAM edges, timing/retry visibility, block-choice
forcing, edge labels, annotation placement, targeted parallelization · `done`
**Scoped in the session that closed T18D** (decisionlog D121), from `t18d_catalog.md` plus an
independent Opus-model analysis of the user's own fresh critique of all six T18D videos plus a
follow-up request to parallelize the pipeline. Full reasoning and evidence: D121. Seven sub-parts,
all in scope for one session by the user's own choice (two larger redesigns the analysis also
surfaced were explicitly deferred — see below).

- **E1 — Annotations authored after block content exists, not before.** The real bug: `plan_
  visuals` asks for `target_item_index`/`anchor_phrase` before any block has content, so it
  answers `null` every time (15/15 across the T18D matrix) and every annotation lands on the
  block's centroid, not a real item. Move annotation authoring into `author_scene`, after blocks
  are filled; make both fields required; `rendering/annotations.py` drops an annotation whose
  phrase doesn't resolve instead of falling back to a guessed time.
- **E2 — GRAPH_DIAGRAM edge anchoring/gating + arrowheads (also SEQUENCE_DIAGRAM).** Edge
  endpoints are computed from the node div's center, not the visible marker circle (lines run
  through label text); every edge draws at node-0's start regardless of which nodes it actually
  connects; no arrowheads anywhere. All three are template-only fixes in `_block_graph_diagram.
  html`, reusing `_annotations.html`'s existing viewport-normalization technique rather than
  inventing new math.
- **E3 — GraphEdge labels/weights.** `GraphEdge` has no way to carry a distance/cost/condition,
  so `GRAPH_DIAGRAM` can't honestly depict Dijkstra, DP transitions, or state machines — the
  topics it was broadened for.
- **E4 — Deterministic block-choice forcing.** 3 of 6 T18D topics never got the block type they
  were chosen to stress (`TIMELINE` rendered zero times across the whole matrix). A small trigger-
  vocabulary scan plus one bounded re-ask (capped per video) when narration clearly calls for a
  block the plan didn't choose.
- **E5 — Per-stage timing + retry visibility.** A ~216s silent gap between two LLM calls in one
  T18D render, almost certainly retry/backoff stacking, with nothing logging it. Per-node timing
  wrapped at `core/graph/pipeline.py`'s `add_node` calls; a `before_sleep` retry-logging callback
  on the Azure LLM adapter's existing `AsyncRetrying`. Plain logging, not new `GraphState` fields.
- **E6 — Container-aware annotation placement.** Two real text-collision bugs (a CHECK caption
  over a block's headline; the caption band over a dense block's last line) both come from each
  annotation partial computing its own offset with no awareness of the container. One shared
  `hfAnnotationPlace` helper, sides-then-clamp, replacing three ad hoc offset calculations.
- **E7 — Parallelize two needlessly-sequential LLM call sites.** `author_scene`'s per-block
  `fill_block` calls run in a plain list comprehension (sequential despite being fully
  independent) — switch to `asyncio.gather`, safe because the Azure adapter's own semaphore
  already bounds real concurrency regardless of caller pattern. `scripting.py::write_narration`'s
  per-segment loop is sequential *by a documented prior decision* (D47: "no measured reason yet")
  — reopened here explicitly, on the user's own instruction, for the same safety reason. This
  task does **not** retune `AZURE_OPENAI_MAX_CONCURRENCY`, `RENDER_MAX_CONCURRENCY`, or
  `FRAME_BUDGET` — those need a real measured run first (D16/D47/D69/D99's repeated lesson),
  which E5 exists to make possible for a future task, not this one.

**Explicitly deferred, not silently dropped** (the analysis's items 7-8, after E1-E6 land, not
before): replacing `GRAPH_DIAGRAM`'s layout with a real layered/rank-based algorithm instead of
authored coordinates + a circular fallback; payload-driven block *variants* as the structural
answer to "every video looks the same" rather than a tenth fixed template.

**DoD, per sub-part:** see D121 and the full plan for each part's specific verification (schema
tests, `hyperframes check` fixtures, concurrency-timing tests) — in short, real re-renders of at
least `array-grid`, `timeline`, and `graph-single`'s topics, watched frame-by-frame the same way
T18D was, confirming each fix against the exact frames that showed it broken, plus `pytest`/
`ruff`/boundary checks clean as always.

**What shipped:** all seven sub-parts (E1-E7), plus a bounded slice of the analysis's item 7 the
user asked to pull forward at plan time — an aspect-ratio-aware fallback layout for
`GRAPH_DIAGRAM`'s compact `SPLIT_HORIZONTAL` canvas (E2.4), scoped narrowly since T18D's own
isolation result said the confirmed node-overlap bug was wrong-shape-canvas, not general layout
quality. One real bug (`_block_graph_diagram.html`'s edge-label id lookup) was found by this
session's own `project-reviewer` review before any render and fixed pre-render. Verified against
three real `RUNTIME_ENV=azure` renders (`t18e-array-grid`, `t18e-timeline`, `t18e-graph-single`,
T18D's own topics for direct comparison) — full detail and evidence: decisionlog D122.

**Three real findings from those renders are recorded, not fixed — the user's own explicit
choice, offered directly rather than assumed.** Whoever scopes the next task on this block
library should read D122's full account before assuming any of these three are already covered:
1. **Inter-annotation collision** — two `CHECK` annotations targeting adjacent lines in the same
   block can still land with overlapping rings/captions. E6's `hfAnnotationPlace` keeps one
   annotation clear of the block's headline and the caption band; it has no idea a second
   annotation exists.
2. **E4's trigger vocabulary has a real blind spot** — a narration that signals chronology
   entirely through domain-specific version numbers ("HTTP 1.0... HTTP 1.1... HTTP/2...
   HTTP/3...") rather than generic timeline vocabulary never trips `missed_block_opportunities`,
   so `TIMELINE` still went unused on exactly the topic chosen to force it.
3. **E2.4's fallback layout, E3's edge labels, and E1's annotations were each verified in
   isolation, not together** — a dense compact-canvas `GRAPH_DIAGRAM` (5 nodes, no authored
   positions, two edge labels, one annotation) keeps its nodes separated (E2.4 holds) but lets
   edge labels, node captions, and the annotation's own caption collide with each other.

**Depends:** T18D — met.

### T18F — Vision critique/revision loop, full validation render, and rendering/pipeline speed · `todo`
**Renamed from T18D** (this checkpoint's own T18D/T18E now cover the bug-catalog/fix-pass split
above instead). Same content, same "not yet scoped as a real plan" status, just moved to make room.
Absorbs three things, per D118: two carried forward unbuilt from T18C's original (too large)
scoping, one raised fresh during T18C's own planning. Previously also carried a vaguer placeholder
framing ("push LLM compositionality further, testing the limits of what the render-time budget
allows," from T18B's planning) — folded into this same task rather than kept as a separate
untracked idea; whoever scopes this next should treat that framing as one possible angle on the
validation-render item below, not a separate obligation.

- **The vision critique/revision loop** — capture stills from a composed scene
  (`adapters/local/playwright_capture.py` already does this for Tier 0/1), show them to a
  vision-capable model, critique, revise the scene plan, re-render only what failed. Requires a
  real `interfaces/llm_provider.py` change (image input) — `LLMProvider.generate` is text-only
  today — and the adapter-parity work that follows from it (both Azure and local, D40's
  `inspect.signature` equality across every implementation including the fake).
- **A full 7-minute validation render** across 2-3 genuinely different topic types (algorithmic,
  systems/protocol, security) — where D104's original "one real full-length render" promise
  properly lands, against content that will actually exercise T18C's broadened block library, not
  just T18B's original six. Should land after T18E, against a block library that's had its known
  bugs fixed, not before.
- **Rendering/pipeline speed** — raised mid-planning during T18C, not yet scoped to a specific
  target. Candidates named but not chosen: render throughput (`FRAME_BUDGET`/tier assignment),
  LLM/TTS call latency, or overall end-to-end wall-clock. Needs its own measurement pass before any
  code changes — the same discipline D16/D99's history argues for (a wrong measurement, once
  written into a constant, propagates unquestioned across sessions until someone re-derives it).

**Depends:** T18C — met. (Not on T18D/T18E structurally, but scoping it before T18E's fixes land
would be premature — the validation render item above exists to show off a working block library.)
**Note added by T18G's own checkpoint:** T18G's own F9 ran one real ~7-minute validation render
(not the 2-3-topic sweep this task still calls for) — it informs this task's own validation-render
item but does not close it. Read D123 before scoping this task's remaining three items.
**Note added by T18H's own checkpoint:** T18H attempted a third real render (a code/list-heavy
topic, deliberately not another graph-heavy one) specifically to prove the new `validate_geometry`
gate runs clean end-to-end — it did not complete: the gate itself worked exactly as intended,
catching four distinct real geometry bugs across four attempts (D124), but a fifth, different-in-
kind capacity bug (`SceneLayout.SINGLE` stacking multiple large blocks) was found and deferred to
T18I rather than fixed live. This task's own validation-render item is therefore still open, now
also blocking on T18I's own closing render rather than T18G's.

---

### T18G — Item-anchored timing, real GRAPH_DIAGRAM layout, duration-aware title, annotation collision avoidance, ICON_PANEL · `done`
**Scoped fresh in its own planning session**, from the user's own direct list of complaints against
T18E's shipped output ("5th iteration on just video generation"): opening segment too long,
diagrams overlapping/open-ended, no per-topic visual freshness, animation/annotations appearing at
random times or in random places, cursor/dot movement through a graph not timed to narration,
captions interacting with video content, and a genuine full 7-minute render. Research (two parallel
Explore agents plus direct reading of the timing/annotation/layout code) traced these to real, cited
causes — mostly D121's own headline finding (the item-anchor "index-only" fallback, explicitly left
out of T18E's scope) and D121's two explicitly-deferred analysis items (7: a real `GRAPH_DIAGRAM`
layout algorithm; 8: payload-driven block variety) — plus D122's three findings E1-E7 recorded but
did not fix, plus the still-open "structural title card" finding (D120) and a still-open
caption/content-overlap gap flagged since T18C. Full reasoning and the two explicit scope
decisions (both big deferred items included, at the user's own choice after being warned of the
cost; the new block scoped to abstract/generated graphics rather than real photo/logo sourcing,
also the user's own choice after being warned that the latter needs a whole new interfaces/adapter
pair): D123.

**What shipped, seven sub-parts plus a real validation render, all in one session:**
- **F1** — the headline fix. `graph_diagram.nodes`, `text_panel.items`, `code_diff.lines` each
  gained an authored `anchor_phrase` (`core/block_schemas_graph.py`, the new `TextPanelItem` in
  `core/block_schemas.py`, `core/block_schemas_diff.py`), and `rendering/block_timing.py
  ::resolve_item_starts` now resolves it exactly the way `resolve_step_starts` always has (unified
  into one shared `_resolve_anchor_phrases` helper) — the same fix D119 already proved for
  `sequence_diagram`/`timeline`, finally extended to the three block types T18E's E1 left out.
  `rendering/anchors.py::derive_item_anchors` (the old display-text-matching path) is gone.
- **F2** — the full build of D121's analysis item 7. `_block_graph_diagram.html`'s circular/
  row-packed fallback is replaced by a real layered/rank-based layout (`computeLayeredLayout`: a
  DFS cycle-breaking pass, longest-path ranking over the resulting DAG, two-pass barycenter
  cross-axis ordering) — pure, deterministic, seek-safe client-side JS, verified live against a
  diamond and a cyclic topology in both layouts (no pytest path exists to JS embedded in a
  template).
- **F3** — the title card (D120's "structural title card" finding, still open after T18E).
  `TitleSlots` gained `key_terms` (0-4, each its own `anchor_phrase`); `_block_title.html` stages
  them across the segment's real duration and adds one continuous ambient tween (D89's rule: a
  genuine tracked property, never a manual DOM write) so a segment with none still isn't visually
  dead for 20+ seconds.
- **F4** — closes D122 finding 1. `_annotations.html::hfAnnotationPlace` gained a shared
  per-container collision registry (`window.__hfPlacedRects`) and a vertical nudge-search before
  falling back to "in-bounds only" — `_block_graph_diagram.html` also registers its own edge-label
  boxes into the same registry, so an annotation on a dense canvas avoids them too.
- **F5** — closes D122 finding 2. `core/block_triggers.py` gained `_looks_chronological`, a
  regex-based version-number detector, as a second signal for `BlockType.TIMELINE` independent of
  the phrase-vocabulary scan (which the exact "HTTP 1.0... HTTP/3..." blind spot never hit).
- **F6** — `runtime_skills/annotation-authoring/1.1.md`: concrete CURSOR/CHECK/WARNING
  right/wrong examples, the only real lever available for symbol-choice appropriateness since
  nothing structural can enforce it.
- **F7** — `_block_sequence_diagram.html` and vertical `_block_array_grid.html` now shrink their
  own row/cell height to fit a computed max canvas height (with a floor, added at review) instead
  of growing unbounded into the caption band — the caption/content-overlap gap T18C's own scope
  notes flagged and left unchecked.
- **New block: `ICON_PANEL`** — a labelled set of icon+label chips (16 hand-authored inline-SVG
  icons, `core/block_types.py::IconName`), the user's own choice of "abstract/generated graphics"
  over real photo/logo sourcing, built end to end via `/newblock`'s own checklist
  (`core/block_schemas_icon.py`, `rendering/templates/_block_icon_panel.html`,
  `runtime_skills/visual-plan/1.3.md`'s new block-choice row).

**One real full ~7-minute `RUNTIME_ENV=azure` render** ("how HTTPS keeps your connection private"),
watched frame by frame — and that watching caught three more bugs no synthetic test had, all fixed
and re-verified against reproductions of the exact scenes that showed them broken: bottom-rank
`GRAPH_DIAGRAM` node captions reaching the caption band (the layered layout's coordinate mapping
now reserves real bottom margin); `marker-end` arrowheads rendering at their destination before the
line/node itself had appeared (an SVG marker is not hidden by `stroke-dashoffset` — both CHAIN and
GRAPH mode lines now gate opacity too); and single-candidate annotation placements (CURSOR's own
`["tip"]`) never actually benefiting from collision avoidance, since the old fallback accepted the
first in-bounds candidate regardless of overlap. `project-reviewer`'s own close-out pass found one
more, fixed the same session: the new shrink-to-fit height formulas had no floor against a
badly-oversized LLM output.

**Known residual, recorded not fixed, the user's own implicit acceptance (not offered as a choice
this time — flagged here for whoever next touches annotation placement):** CURSOR's `"tip"` targets
a `GRAPH_DIAGRAM` node's whole div (marker+label+caption stack), so on a captioned node it can land
on the label text rather than the marker circle — a narrower, pre-existing target-precision issue,
not a collision-avoidance regression.

**Explicitly not this task, both per the user's own scope choice at planning time:** a real
photo/logo image-sourcing pipeline (would need a new `interfaces/`+adapter pair, iteration-5.5
scale); the general payload-driven block-*variants* system (D121's analysis item 8 proper, beyond
adding one new block type — `ICON_PANEL` helps variety but doesn't build the general mechanism).

**Depends:** T18E — met.

### T18H — Geometric correctness as a hard, automatic gate on every real render · `done`
**Scoped fresh in its own planning session**, from the user's own direct reaction to watching
`t18g-showcase-git`: "three sessions worth of trying to fix it, and this is what I get, I need a
solid fix that I am sure will work... a validator agent?" Diagnosed, not assumed: the tool that
would catch this deterministically (`hyperframes check`) already existed in this project's own
toolchain since T18A, proven directly by running it against the exact broken composition from the
prior night's render (5 `layout` errors, `content_overlap`, pinpointing the exact overlapping
text) — but `render_segment.py` never called it, only the cheap static `lint`. Full reasoning,
the two review findings, and the layout-algorithm fix's own iteration history: D124.

**What shipped:**
- `interfaces/render_backend.py::RenderBackend.validate_geometry` — a second, equally-fatal gate,
  same string contract as `lint`, implemented in `adapters/local/render_backend.py` (wraps
  `hyperframes_check.check`, folds `layout` + `runtime` finding categories, shares the class's own
  concurrency semaphore) and stubbed in `adapters/azure/render_backend.py` (T35). Wired into
  `rendering/render_segment.py` right after `lint`, before tier dispatch.
- `--at-transitions`/`--frame-check`/`--contrast` all measured off by default for this call (~15s
  vs. ~56s per real segment for the same result on the one composition measured) — a decision, not
  a guess.
- Two bugs fixed as the gate's own opening proof (already root-caused from T18G's prior render):
  `_block_graph_diagram.html::computeLayeredLayout`'s same-rank node crowding in a compact canvas;
  CURSOR annotations on `GRAPH_DIAGRAM` nodes now target the marker's own id, not the whole node
  div, via `rendering/annotations.py::_ANNOTATION_TARGET_SUFFIX_OVERRIDE`.
- `project-reviewer` found two real gaps in the gate itself before the first checkpoint attempt,
  both fixed: `validate_geometry` was reading only `layout` findings (a browser-check crash reports
  under `runtime` instead, and would have silently passed as "no findings"); `validate_geometry`
  was not sharing the adapter's own concurrency semaphore.
- **Four more real bugs, found by the gate's own closing render, not by the plan** — every one of
  them a genuine pre-existing or newly-introduced geometry defect the gate was specifically built
  to catch, each independently reproduced and fixed: `CODE_PANEL`/`CODE_DIFF`'s trailing caption
  now drops rather than overflows the caption band (`_annotations.html::hfDropIfPastCaptionBand`);
  an unsafe LLM-authored `GRAPH_DIAGRAM` position now discards the whole authored set for that
  diagram in favor of the algorithm's own (already-proven-safe) fallback, not a per-node clamp (a
  clamp was tried first and confirmed live to trade one collision for a different one);
  `Y_MIN_FRAC` widened further (0.08) plus a node-vs-node caption collision check
  (`hfRectsOverlap`) for the adjacent-rank case the widening alone didn't fully close; `TEXT_PANEL`
  shrinks its own item `gap` by the real measured overflow when its list would reach the band.
  Full account, including the exact iteration order and what didn't work the first time: D124.

**Explicitly not this task:** T18F's vision critique/revision loop (semantic judgment — "is this
the right symbol for this narration moment" — a different, harder problem pixels alone can't
answer); contrast-check enforcement in the render path (stays test-sweep-only, a separate
concern); any content-authoring feature beyond the bug fixes above.

**Honest limits, stated plainly:** this closes a real, growing slice of the *geometric* correctness
gap (overlap, positioning, caption-band collision) for every future render, automatically — the
actual mechanism behind "a solid fix I'm sure will work." It does not validate semantic or temporal
correctness (right symbol, right narrative moment) — that is `hyperframes check` never seeing
narration intent, a different problem. It also does not close every geometric case: the closing
render surfaced a fifth, different-in-kind bug (`SceneLayout.SINGLE` composing multiple large
blocks stacked with no combined-height constraint, 42 `canvas_overflow` findings) that the user
explicitly asked to defer rather than have this session chase a fifth live fix-and-reproduce cycle
in one night — carried into T18I below, along with an annotation-placement gap (parallel-to-a-line
positioning) the user named directly. **No closing real render completed this session — the
showcase video was not produced.**

**Depends:** T18G — met.

### T18I — Close the remaining geometry gaps T18H's gate found but did not fix, give the pipeline a
real failure story, land a genuine full 7-minute render · `in progress`

**Status update (this session, D151/D152):** started from a curated merge of
`feature/scene-composition`, which turned out to already contain most of this task's original
scope, built but never checkpointed/reviewed. Verified rather than rebuilt, then extended with new
scope the user added mid-session from watching real output again:

- **SINGLE-stacking and edge-parallel annotations (both bullets below): done, verified live.**
  `core/scene_normalize.py::normalize_layout` and `_annotations.html`'s `"parallel"` candidate
  were both already built on the branch; this session confirmed both are correctly wired and
  produce clean output on a real render.
- **The resilience three bullets (retry/fallback/signal): done, verified live, and one real bug
  found and fixed in the process.** `core/graph/nodes/scene_reauthor.py`/`scene_fallback.py` plus
  `render_scene.py`'s rewrite were reviewed (not trusted blindly) and found complete and correct.
  The closing render found `rendering/geometry_findings.py` was missing `text_occluded` from its
  retryable set — fixed, D151, re-confirmed on a second render.
- **New scope folded in from fresh user complaints, all done and code-enforced:**
  `core/scene_variety.py` (block-type variety, wired into `plan_visuals`'s existing re-ask),
  `core/scene_content_normalize.py` (sequence-diagram messages hard-capped at 3),
  `core/annotation_normalize.py` (per-scene density cap + CURSOR walk-order coherence, whole-video
  annotation budget via the now-real `core/graph/nodes/collect_scenes.py`). `project-reviewer`
  found and this session fixed three real bugs in this new code (a rounding false-negative on the
  sequence_diagram cap, an ITEM/LINK index-space conflation in CURSOR coherence, and a
  non-adjacent-segments-compared-as-adjacent gap) — see the git log for the fix commit.
- **Genuinely still open:** the `sequence_diagram` FREQUENCY cap (how often it's chosen, as
  opposed to how long it is) is a soft one-shot nudge, same as `missed_block_opportunities`
  already was — confirmed live it can still miss. A hard guarantee here needs the same
  deterministic-downgrade treatment the message-length cap got, not a second re-ask. New
  `SceneLayout` members (`STACKED`, an asymmetric split) were scoped but not built this session —
  deprioritized in favor of the correctness/enforcement work above. Latency: this session's
  closing render ran 18.1 min against the ~15 min target for a 10-min-equivalent video, because
  both degraded segments needed a full retry-then-fallback cycle — expected to improve as Phase
  2/3's remaining geometry work reduces how often that cycle triggers at all, not by weakening it.

Original task text follows, kept for the parts still open above:
**Scoped by the user directly at T18H's own checkpoint**, after watching four consecutive
find-fix-reproduce cycles in one session (D124) and asking to stop chasing a fifth live rather than
keep going. Two distinct halves, both explicit user asks at the same checkpoint, folded into one
task rather than split — read both before starting, since the closing render (last bullet) is
meant to exercise both:

- **`SceneLayout.SINGLE` stacking multiple large blocks with no combined-height constraint.**
  Confirmed live: a full `GRAPH_DIAGRAM` (headline + 620px canvas) stacked above a `TEXT_PANEL` in
  one SINGLE-layout scene produced 42 `canvas_overflow` findings — a capacity problem (too much
  content for the available height), not a positioning one, so none of T18H's four fixes touch it.
  Needs its own real design: whether `_layout_single.html` should reserve/measure a shared height
  budget across however many blocks a scene stacks (an F7-style shrink, generalized across blocks
  rather than within one), whether `plan_visuals`/`author_scene` should be constrained from
  stacking two large blocks together at all, or both.
- **The user's own explicit requirement, verbatim:** annotation placement "must appear parallel to
  a line if that's required, not above or below or on top of it," when the target it marks is
  itself a line/edge (a `GRAPH_DIAGRAM` edge, a `SEQUENCE_DIAGRAM` message arrow) rather than a
  point. `_annotations.html::hfAnnotationPlace`'s candidate set today is `tip`/`center`/`above`/
  `below` only — no parallel-to-a-line option exists, so an annotation on a line-shaped target is
  currently placed the same way as one on a point-shaped target regardless of whether that reads
  correctly. Needs a new candidate geometry (offset perpendicular to the line's own angle, not a
  fixed above/below), and a way for a caller to signal "my target is a line" vs. "my target is a
  point."
- **Re-verify (not re-litigate) that annotations appear at the correct time, not "randomly"** — the
  user's own words at T18H's own checkpoint conversation. `resolve_annotations`
  (`rendering/annotations.py`) already resolves every annotation's `entrance_start` from a real
  `anchor_phrase` match against measured word timing (D121/D122, T18E), so "random timing" may be a
  symptom of the placement bug above (a badly-placed annotation reads as "wrong," which can look
  like "random," even when its timing is correct) rather than a separate timing defect — confirm
  which it actually is before assuming new timing work is needed.

**Second half: what happens when `validate_geometry` (or `lint`) catches something in production**,
folded in at the user's own explicit request after they asked directly what T18H's gate actually
does when it fires on a real job, and were told plainly it currently has no answer beyond a crash.
Three concrete gaps, all real today, none touched by T18H:
- **No retry.** A geometry failure never gets a second attempt with adjusted content, even though
  every one of T18H's own four real-render bugs (D124) turned out to be a one-shot content problem
  (a bad authored position, a caption that happened to be too long) that a re-author with feedback
  about what failed could plausibly fix. Needs a real design: what triggers a retry (which finding
  codes are worth retrying vs. not), how many attempts, whether the retry re-calls
  `author_scene`/`plan_visuals` with the specific failure as feedback or just re-rolls the same
  prompt, and where this sits relative to D2's "no repair loop" stance (D2 was about schema/logic
  errors lint catches instantly and deterministically; a geometry finding tied to specific
  LLM-authored content is a different kind of failure, and this task should say explicitly whether
  that distinction justifies reopening D2 for this one path, not silently override it).
- **No per-segment isolation.** One bad segment currently kills the entire `VideoJob` run
  (`core/graph/nodes/render_scene.py`'s own exception propagates through the graph), rather than
  falling back to something safe (a simpler tier, a swapped block type, or a plain title-card
  substitute) so the other 14 segments still ship. Needs a real fallback strategy per segment, not
  just "catch and skip" (a silently missing segment is its own kind of broken video).
- **No user-facing signal beyond a crash.** Nothing today surfaces which segment failed, on which
  finding, to whoever is waiting on the job. At minimum this needs the failure to reach
  `VideoJob`'s own status/error surface (however T19's API skeleton ends up exposing job state) with
  enough detail to be actionable (segment index, finding code, not just "the job failed").
- **A genuine full ~7-minute `RUNTIME_ENV=azure` render, completed, as this task's own closing
  proof** — the same bar D104 originally set, approximated but not landed exactly by T18F's/T18G's
  own renders, and not landed at all by T18H (no closing render completed this session). Should land
  only after every fix above, on a topic chosen to exercise all of them: a graph-diagram-heavy
  segment reachable via an edge-parallel annotation, at least one multi-block SINGLE scene, and
  (deliberately, to prove the resilience half works) content likely enough to trip `validate_geometry`
  at least once so the retry/fallback/signal path is exercised for real, not just unit-tested.

**Depends:** T18H — met.

### T19 — API skeleton · `done`
Job submission and the runner that drives the graph, reusing the pydantic models from T4 as request
and response contracts.
**DoD:** posting a job starts a real run and returns an id — met, `api/jobs.py::submit_job` +
`api/runner.py::JobRunner`.
**Depends:** T18 — met.
**Built together with T20-T23 in one combined session** (D125), by the user's own choice — see
`handoff.md` for the full shape and `decisionlog.md` D123-D129 for every non-obvious call made
building it, including two real bugs (`api/runner.py`'s resume-detection logic, a missing
`durability="sync"`) found by `project-reviewer` and fixed before this checkpoint.

### T20 — Progress streaming · `done`
Live per-segment progress to clients, sourced from graph events rather than a bespoke event bus.
**DoD:** a client observes stage transitions for each segment as they happen — met,
`api/events.py::JobEventBus`/`summarize_node_event` sourced from `graph.astream_events`, SSE via
`api/jobs.py::stream_job_events`.
**Depends:** T19 — met.

### T21 — Artifact serving · `done`
Video and intermediate artifacts served through the `Storage` interface — never raw filesystem
paths, so the Blob backend works unchanged.
**DoD:** playback works identically under both `RUNTIME_ENV` values — met, `api/artifacts.py`
scheme-sniffs `Storage.url()` (D128) rather than branching on `RUNTIME_ENV` or a concrete adapter
type. **Known gap, not blocking this DoD:** no HTTP Range/206 support on the byte-streaming branch
— see `handoff.md`'s "Known gaps."
**Depends:** T19 — met.

### T22 — Job persistence & resume · `done`
Job listing, history, and an endpoint that resumes a failed run from its checkpoint.
**DoD:** a failed job resumes via the API without recomputing finished segments — met,
`api/job_store.py` (D127) + `api/jobs.py::resume_job`, pinned by
`tests/test_api_resume.py::test_resume_recovers_a_dead_lettered_job_without_re_synthesizing`.
**Depends:** T20 — met.

### T23 — API test suite · `done`
Full backend coverage against the fakes, no network, no Azure.
**DoD:** every endpoint covered offline — met, 14 tests across `tests/test_api_*.py`, all
exercising the real `langgraph` library end to end against `tests/fakes/*` (never a mocked graph).
**Depends:** T22 — met.

---

## Iteration 5 — React frontend

**Built together, T24-T28 in one combined session** (user's own choice — see decisionlog.md
D130-D137), the same pattern T19-T23 used. T36 (SCORM export) was added mid-session, also done.

### T24 — Frontend scaffold · `done`
Vite + TypeScript + Tailwind, with the API client generated from the backend OpenAPI schema so
contracts cannot silently diverge.
**DoD:** app builds; a type error appears if the backend contract changes. Both proven empirically
(D132) — a real backend field rename was made, re-dumped, re-generated, and `tsc` failed in exactly
`web/src/adapters/job-adapter.ts`, then reverted.
**Depends:** T23 — met.

### T25 — Submission & dashboard · `done`
Topic entry and a job list showing status and history.
**DoD:** a job can be started and tracked from the browser. Verified end to end through the real
`PromptComposer` form (not just curl) for all three duration options — see D134.
**Depends:** T24 — met.

### T26 — Live progress view · `done`
Per-segment cards with tier badges and a stage timeline, fed by the T20 stream. The tier badges are
what make the tier system legible to a viewer.
**DoD:** progress updates live; tier assignment is visible per segment. Tier badges "earn" a flip
animation on assignment (`components/TierBadge.tsx`).
**Depends:** T25 — met.

### T27 — Player & artifact browser · `done`
Final video playback plus per-segment preview and scene inspection for debugging.
**DoD:** any segment's audio, clip, and composed scene can be inspected individually — three new
routes in `api/segments.py`. One honest scope note: rendered scene *HTML* is never persisted
through `Storage` (it only exists in the run's `working_dir`); `Segment.scene` (the authoring
source of truth) is served and rendered generically instead (D131), so as not to reach into T18's
`core/graph/nodes/render_scene.py` — exactly the territory this frontend is meant to be insulated
from.
**Depends:** T26 — met.

### T28 — Error states & polish · `done`
Failure surfaces, retry and resume affordances, empty and loading states.
**DoD:** every failure mode from T22 has a UI path — 404, 409, retryable-vs-terminal failure
(D135.2), dead-lettered-with-resume, SSE disconnect, null artifacts.
**Depends:** T27 — met.

### T36 — SCORM 1.2 export · `done` *(new task, added mid-session at the user's explicit request;
not originally in this backlog)*
A real `scorm/` package — manifest, zip assembly, and a launch page with genuine SCORM 1.2 API
calls — not a stubbed button. Full reasoning: decisionlog D136.
**DoD:** `GET /jobs/{id}/scorm` returns a zip an LMS can import directly; verified by unzipping a
real downloaded package and confirming `imsmanifest.xml` + `launch.html` + `video.mp4` (+
`subtitles.srt` when present).
**Depends:** T27 (needs a finished video) — met.

### T37 — Frontend visual redesign · `done` *(new task, added after T24-T28/T36's first real
end-to-end use surfaced that the visual design doesn't match what the user actually wants)*
The functional frontend (T24-T28, T36) works end to end against a real backend — verified via two
real Azure renders — but the user rejected its current visual design after using it for real.
Full context, in order of how much you need: `handoff.md` (read first, self-contained), then
decisionlog.md D130-D144 (D144 specifically explains why this is its own gated task).

**Requirements gathered directly from the user, verbatim intent preserved:**
- **No forced dark theme.** The app must not switch to a dark palette off the system/browser's
  `prefers-color-scheme` — light only, regardless of the visitor's OS setting.
- **Restore and amplify real hover/motion — do not remove it.** An earlier reading of "no fun
  elements" as a request to strip interactivity was **backwards** and the user corrected it
  directly: they want *more* glow/lift/pop on interactive elements, not less. (The screen that
  prompted the original complaint was a job stuck mid-render with almost nothing on it yet — not
  representative of the app as a whole.)
- **`skill-bites` branding** — already done (header wordmark, browser tab title); verify it stayed
  that way, don't revert it.
- **A wireframe first, before any real styling code changes** — this is the gate this task exists
  to enforce. Use **both**: Claude's `design` skill for a clickable layout/IA mockup published as
  an Artifact the user reacts to, **then** Impeccable's actual `craft`/`shape`/`critique` workflow
  (already installed this repo — `.claude/skills/impeccable/`, `.impeccable/config.json`) to build
  the real, approved visual system. The first attempt at this frontend (T24-T28) installed
  Impeccable but never ran its real design workflow, and only ever read a prose summary of
  https://nomu.store/ instead of actually looking at it — both contributed to the result reading
  as generic. Do neither shortcut again: fetch nomu.store directly, and actually invoke
  Impeccable's commands rather than reasoning about design tokens in isolation.
- **Do not touch the structural work** T24-T28 + this session's Parts 1-3 already did: the one-page
  Studio (`/` and `/jobs/:jobId` both render `StudioPage`, no navigation on submit), the live
  progress SSE wiring, incremental segment persistence, submission error toasts. This task is the
  visual layer on top of that, not a rebuild of it.
- **Must not weaken CLAUDE.md's "frontend is structurally insulated from T18" invariant** (the
  fifth invariant in "Invariants that break the product if violated") — the generic scene-tree
  renderer and the `no-restricted-imports` seam are load-bearing; a visual redesign has no reason
  to touch either, and must not.
**DoD:** wireframe published and reviewed by the user, with explicit sign-off, before any
component's real visual code changes; the approved direction then implemented for real; `pytest`,
`web`'s `tsc -b --noEmit`/`eslint .`/`vitest run`/`npm run build` all still green; no regression in
Parts 1-3's structural behaviour or the T18/frontend seam (CLAUDE.md invariant 5).
**Depends:** T24-T28, T36 — met.
**Done, with one disclosed substitution:** Claude's `design` skill turned out not to be installed
in this repo, so the wireframe gate was met via Impeccable's real direction-roll workflow
(disclosed as it happened, not after) instead — full story in decisionlog D145-D148. All DoD
checks green; two `project-reviewer` passes plus a two-round `impeccable-finish-reviewer` loop, no
open findings in `web/` at close. One pre-existing (not T37-introduced) accessibility gap in
`Pill`/`StatusPill`'s status-tone colors was found but not fixed — see `handoff.md`.

---

## Iteration 5.5 — Cloud execution *(added during T3 planning; runs before iteration 6)*

Task numbers are identity, not order: **T34 and T35 run here**, between T28 and T29.

D5 stubbed the Azure `JobQueue` and `RenderBackend` deliberately, to keep POC debugging on the
local machine. With Azure-native as the primary stack that call is now revisited: both stubs become
real implementations, and the signature-matched stubs from T12 are what make that a fill-in rather
than a redesign.

### T34 — Service Bus job queue · `todo`
The `JobQueue` stub becomes a real Service Bus implementation: lease/renew semantics, dead-lettering
on `fail`, and `attempt` surviving a requeue. Worker and API become separate processes.
**DoD:** a job submitted through the API is claimed and run by a separate worker process; the
parity tests from T13 pass unchanged against both the asyncio pool and Service Bus.
**Depends:** T23, T28

### T35 — Container Apps render backend · `todo`
The `RenderBackend` stub becomes a real Container Apps implementation. **Moves the Dockerfile out of
T33**, which currently owns it — cloud rendering needs the image, and T33 now runs after this. The
image carries both browsers (Playwright's Chromium *and* HyperFrames' Chrome Headless Shell, per
D15) plus vendored GSAP, since the scaffold's CDN pull will not survive a locked-down container.
Expect fewer parallel workers than local: Container Apps caps at 4 vCPU against this machine's 16.
**DoD:** a Tier-2 segment renders in the cloud and its duration matches the local render of the
same composition within tolerance; `RUNTIME_ENV=azure` runs a job end to end with nothing executing
on the developer machine. **Closes the gap T18/T18A worked around by hand** — once this exists,
`cli.py` runs a full job on `RUNTIME_ENV=azure` alone, no manual adapter-mixing needed.
**Depends:** T34

---

## Iteration 6 — RAG *(scheduled last, per requirement)*

### T29 — Document upload · `todo`
Users upload a source document; it is stored through the `Storage` interface like any other artifact.
**DoD:** upload works on both stacks.
**Depends:** T21

### T30 — Chunking, embeddings & vector store · `todo`
A new `VectorStore` interface with a local and an Azure implementation — the same pattern as every
other dependency, which is the real test of whether the abstraction generalizes.
**DoD:** retrieval returns relevant chunks on both backends.
**Depends:** T29

### T31 — Grounded generation · `todo`
A retrieval node inserted into the existing graph; outline and script generated from the document
rather than from model knowledge.
**DoD:** the script demonstrably reflects uploaded content; graph shape is otherwise unchanged.
**Depends:** T30

### T32 — Citations · `todo`
Source attribution surfaced in scenes and narration.
**DoD:** claims trace back to document chunks.
**Depends:** T31

### T33 — RAG UI · `todo`
Upload interface with grounding display. *(The Dockerfile moved to T35 — cloud rendering needs the
image earlier than this.)*
**DoD:** document-to-video works end to end in the browser.
**Depends:** T32, T28
