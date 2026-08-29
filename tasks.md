# Task Backlog

36 tasks across 8 iterations. **One task per session.** Descriptions are deliberately high-level —
detail is negotiated in plan mode at the start of each session, not pre-baked here.

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

### T18C — The broadened block library, and the vision critique/revision loop · `todo`
**Scoped during T18B's own planning** (decisionlog D104-D105), deliberately deferred rather than
crammed into T18B so the genuinely novel, highest-craft work gets a full session's attention
instead of being squeezed at the end of an already-large one.

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
scheduled last per the original requirement). A possible **T18D** — pushing LLM compositionality
further than the block-schema model, "testing the limits" of what the render-time budget allows,
per the user's own framing in T18B's planning — is named for continuity but has had no scoping
conversation and is not promised as this task's or any specific session's work.
**Depends:** T18B — met.

---

## Iteration 4 — FastAPI backend

### T19 — API skeleton · `todo`
Job submission and the runner that drives the graph, reusing the pydantic models from T4 as request
and response contracts.
**DoD:** posting a job starts a real run and returns an id.
**Depends:** T18

### T20 — Progress streaming · `todo`
Live per-segment progress to clients, sourced from graph events rather than a bespoke event bus.
**DoD:** a client observes stage transitions for each segment as they happen.
**Depends:** T19

### T21 — Artifact serving · `todo`
Video and intermediate artifacts served through the `Storage` interface — never raw filesystem
paths, so the Blob backend works unchanged.
**DoD:** playback works identically under both `RUNTIME_ENV` values.
**Depends:** T19

### T22 — Job persistence & resume · `todo`
Job listing, history, and an endpoint that resumes a failed run from its checkpoint.
**DoD:** a failed job resumes via the API without recomputing finished segments.
**Depends:** T20

### T23 — API test suite · `todo`
Full backend coverage against the fakes, no network, no Azure.
**DoD:** every endpoint covered offline.
**Depends:** T22

---

## Iteration 5 — React frontend

### T24 — Frontend scaffold · `todo`
Vite + TypeScript + Tailwind, with the API client generated from the backend OpenAPI schema so
contracts cannot silently diverge.
**DoD:** app builds; a type error appears if the backend contract changes.
**Depends:** T23

### T25 — Submission & dashboard · `todo`
Topic entry and a job list showing status and history.
**DoD:** a job can be started and tracked from the browser.
**Depends:** T24

### T26 — Live progress view · `todo`
Per-segment cards with tier badges and a stage timeline, fed by the T20 stream. The tier badges are
what make the tier system legible to a viewer.
**DoD:** progress updates live; tier assignment is visible per segment.
**Depends:** T25

### T27 — Player & artifact browser · `todo`
Final video playback plus per-segment preview and scene inspection for debugging.
**DoD:** any segment's audio, scene HTML, and clip can be inspected individually.
**Depends:** T26

### T28 — Error states & polish · `todo`
Failure surfaces, retry and resume affordances, empty and loading states.
**DoD:** every failure mode from T22 has a UI path.
**Depends:** T27

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
