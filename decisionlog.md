# Decision Log

Append-only. Newest at the bottom. Written by `/checkpoint`.

Consult this before revisiting a settled decision — the reasoning matters more than the conclusion,
and a decision made for reasons that no longer hold *should* be reopened.

Format: date · task · decision · alternatives rejected · reasoning.

---

## 2026-08-22 · Planning (pre-T1)

Seeded from the planning session. These predate T1 and set the shape of everything after.

### D1 — LangGraph for orchestration, confined to `core/graph/`
**Rejected:** plain `asyncio.gather` with a hand-rolled resume file (the original brief's position).
**Reasoning:** the brief deferred LangGraph until "checkpointing/retry logic gets unwieldy." Moving
to ~7-minute videos meets that bar — ~15 segments per run, where a failure at segment 13 must not
redo 12 TTS calls. Three concrete wins: checkpointed resume, the `Send` API for per-segment fan-out,
and `astream_events` making the frontend progress feed nearly free instead of a bespoke event bus.
The RAG iteration then adds a retrieval node rather than restructuring the pipeline.
**Constraint attached:** LangGraph may not appear in `interfaces/`, `adapters/`, or
`core/tier_resolver.py`. Enforced by hook.

### D2 — LLM fills slots; Jinja templates own all HTML
**Rejected:** LLM writes HyperFrames compositions directly, validated by `hyperframes lint` with a
repair loop.
**Reasoning:** three-way win on the stated criteria. Output tokens are the expensive side
(~$4.50/M): a slot payload is ~100 tokens against ~1500 for a full composition, roughly 10× cheaper
per scene. Render success approaches 100% because invalid HTML is structurally impossible. And it is
one code path for all three tiers instead of separate authoring strategies. Animation richness lives
in hand-authored templates where it is version-controlled and debuggable, rather than being
re-rolled by the model every run.

### D3 — Per-segment mux, then concat
**Rejected:** render all segments, concat, then mux one audio track over the whole timeline.
**Reasoning:** each segment becomes a self-contained MP4 at exactly its measured audio duration, so
drift cannot accumulate across segments — every segment is independently correct by construction
rather than correct by discipline.

### D4 — Runtime skills as a first-class interface (`SkillRegistry`)
**Rejected:** prompts as string constants in the source.
**Reasoning:** requirement was reusable knowledge at runtime so the agent doesn't start cold. Making
it an interface means packs load from disk locally and from Blob on Azure, so prompt improvements
ship without a code deploy — which is the actual point. Kept strictly separate from `.claude/skills/`
(build-time, for Claude Code); different audience, different directory.

### D5 — Azure adapters real for LLM/TTS/Storage; Queue and Render stubbed
**Rejected:** all Azure adapters stubbed (the original brief's position).
**Reasoning:** a live PAYG subscription exists, and two working implementations behind an interface
prove the boundary far harder than matching signatures do. Queue and Render stay stubbed
deliberately: implementing them moves debugging into the cloud, which is where POC velocity dies.

### D6 — Windows-native primary loop; Docker deferred to T33
**Rejected:** WSL2 or Docker from day one (the original brief's position).
**Reasoning:** the brief's two reasons for Docker were Kokoro's espeak-ng dependency and Linux
Chromium. Azure Speech as primary TTS removes the first for the main path, and Node 24 + ffmpeg are
already on the host. HyperFrames' cross-platform determinism guarantee matters for CI regression,
not for a demo. The Dockerfile still gets built in T33 as the escape hatch and the
Container-Apps-shaped artifact.
**Watch:** if renders behave inconsistently on Windows, move to the container early rather than
debugging platform differences.

### D7 — Azure Speech F0 as primary TTS, Kokoro second
**Rejected:** Kokoro only (the original brief's position).
**Reasoning:** F0 gives 500k neural characters/month free and permanently — about 85 seven-minute
videos — with no espeak-ng, no model download, and word-boundary timings that feed the
measured-duration rule directly. It is also the enterprise-target implementation. Kokoro remains as
the offline adapter, which is where it earns its keep as proof the interface is real.

### D8 — FastAPI + React added to scope
**Rejected:** CLI only (the original brief's position).
**Reasoning:** product requirement. FastAPI chosen because its async model matches LangGraph
natively and its pydantic models are the same ones the LLM structured-output calls use — one type
definition serving validation, API contract, and schema enforcement. The CLI is *not* dropped; it
stays the fastest inner loop and the thing T18 is verified against.

### D9 — Frame budget ~2000, not the brief's 4000
**Rejected:** 4000, as originally specified.
**Reasoning:** at 30fps with ~15 segments, 4000 frames promotes nearly everything to Tier 2 and
collapses the visual contrast between tiers — which is the entire reason the tier system is in the
POC. ~2000 yields 2-3 Tier-2 scenes. Tune the budget, keep the resolver honest and budget-greedy.

### D10 — No budget alerts
**Rejected:** alerts at $50/$100/$150.
**Reasoning:** explicit user preference to monitor manually. `/costs` exists for that.
**Risk accepted:** PAYG bills past $200 or day 30 with no automated warning.

---

## 2026-08-22 · T4 — Toolchain spike

The one-hour spike against hand-written inputs, before any pipeline code depended on HyperFrames or
ffmpeg. It paid for itself: the render-throughput number below invalidates a parameter that was set
on assumption.

### D15 — HyperFrames works, and its animation contract is `window.__timelines`
**Verified:** `hyperframes@0.8.8` renders a hand-written composition to a valid 1920x1080 H.264 MP4.
`check` runs lint, runtime, layout, motion, and WCAG AA contrast passes — richer validation than
expected, and worth running as a gate before every render.

The seekable-animation mechanism is concrete: a **paused GSAP timeline** registered as
`window.__timelines["<composition-id>"]`. Scene templates must follow that shape. Root element needs
`data-composition-id` / `data-start` / `data-duration` / `data-width` / `data-height`; clips need
`class="clip"` plus `data-start` / `data-duration` / `data-track-index`.

**Two environment facts:** HyperFrames downloads its own Chrome Headless Shell (114 MB, cached at
`~/.cache/hyperframes`) — separate from Playwright's Chromium, so the container needs both. And the
scaffold pulls **GSAP from a CDN**, which must be vendored locally before containerizing rather than
depending on egress at render time.

**Telemetry was on by default** and has been disabled (`hyperframes telemetry disable`) — this is
work code and composition usage should not leave the machine.

### D16 — FRAME_BUDGET drops from 2000 to ~600. Render throughput is the binding constraint.
**Measured:** 90 frames (3s @ 30fps) took **34s** and **52.5s** across two runs on a 16-core i5 with
3 render workers — roughly **1.7-2.7 frames/second**, with wide run-to-run variance.

**Rejected:** the previously planned `FRAME_BUDGET = 2000`. At the measured rate that is **12-20
minutes of Tier-2 rendering alone**, before LLM, TTS, or Tier 0/1 work. It would have been
discovered on Day 2 with the deadline already spent.

**Reasoning:** ~600 frames lands Tier-2 rendering at roughly 4-6 minutes locally, which the SSE
progress view makes tolerable. Cloud is expected to be worse — Container Apps caps at 4 vCPU against
this machine's 16, so fewer parallel workers.

**Also lowering `FPS` 30 -> 24**, cutting frames 20% for negligible quality loss on text and motion
graphics. Together these put a demo-length video in a watchable render window.

### D17 — Resolution is not a performance lever
**Rejected:** rendering Tier 2 at 720p to buy animation budget.
**Reasoning:** measured *slower* than 1080p (52.5s vs 34s for identical frame counts). Cost is
dominated by per-frame browser screenshot overhead, not pixel count. Stay at 1920x1080 — better
output for the same price. Frame count is the only lever that matters.

### D18 — The mux/concat chain is verified, and AAC padding is understood
**Verified:** per-segment mux pins video duration to measured audio **exactly** (2.400s audio ->
2.400s video; 1.700 -> 1.700). Concat with `-c copy` produced 4.143s against a 4.100s theoretical
sum.

That ~43ms is AAC frame padding, and it accumulates across segments — perhaps ~300ms over a 15
segment video. **It does not desync anything**: each segment stays internally exact, so audio and
visuals never drift apart. Only total runtime is marginally long. Accepted; this is precisely the
failure mode D3's per-segment mux was designed to contain.

**Avoid ffmpeg `drawtext` on Windows** — it segfaults on missing fontconfig. Irrelevant to the
pipeline (frames come from Playwright), but it will waste time in any future ffmpeg debugging.

---

## 2026-08-22 · T3 — The six interfaces

Iteration 1 opens. Nothing here is implementation; all of it constrains every adapter written
after it, which is why the reasoning is worth keeping.

### D19 — Interface methods are `async def`
**Rejected:** synchronous signatures, as illustrated in `.claude/skills/adapter-contract/SKILL.md`.
**Reasoning:** LangGraph nodes and FastAPI handlers are async natively (D1, D8), the local
`JobQueue` is an asyncio pool, and Playwright and httpx both expose async APIs. Sync signatures
would need thread pools for the per-segment fan-out and would block the event loop on every LLM and
TTS call. The one sync-only SDK is Azure Speech; it gets wrapped in `asyncio.to_thread` inside its
own adapter in T10, which is where vendor accommodation belongs. The skill file's sync snippets were
illustrating the *return type*, not prescribing the calling convention.

### D20 — `RenderBackend` is `capture` / `render` / `lint`, not one method per tier
**Rejected:** `render_tier0` / `render_tier1` / `render_tier2`.
**Reasoning:** the tier taxonomy is a budgeting decision owned by `core/tier_resolver.py` and the
modules in `rendering/`. Baking it into the backend contract means adding or removing a tier later
changes the interface and every implementation of it. Tier 0 and Tier 1 differ only in how many
timestamps they screenshot, so they are one method with a `Sequence[float]`, which D15's finding
that HyperFrames timelines are seekable is what makes possible. Frame dimensions are deliberately
absent: the composition root already carries `data-width` / `data-height`, and a second source of
truth can disagree with the file being rendered.

### D21 — `TTSProvider.synthesize` takes a `dest: Path`
**Rejected:** `synthesize(text) -> tuple[Path, int]` with an adapter-chosen temp path, as the
`adapter-contract` skill illustrates.
**Reasoning:** the artifact layout (`artifacts/<job>/segments/<n>/narration.wav`) is the caller's
business, and an adapter-chosen path forces a copy on every segment of every job. The measured
`duration_ms` in the return — the part the skill was actually making a point about — is unchanged.

### D22 — Contract-support types live in `interfaces/`, not `core/models`
**Rejected:** `SkillPack` and `QueuedJob` in `core/models` alongside the domain models.
**Reasoning:** T4 depends on T3, so the dependency cannot run in the other direction without a
cycle. These two are the contracts' own vocabulary rather than domain concepts — `Segment`,
`VisualIntent`, `Tier` and `VideoJob` remain T4's and appear in no T3 signature.

### D23 — `CompositionInvalid` is deliberately outside the `AdapterError` family
**Rejected:** parenting it to `AdapterError` with everything else in `errors.py`.
**Reasoning:** `RenderBackend.lint` returns findings rather than raising, so this is raised by our
own code deciding a finding is fatal — the same code on both stacks, with no backend involved. The
distinction is what a retry classifier needs: `AdapterError` means the outside world misbehaved,
while a malformed composition reproduces exactly on requeue and would burn attempts arriving at the
message the first one already had. Pinned by a test, because the instinct when adding an error is to
parent it to the nearest base, and doing that here silently reintroduces the bug.

### D24 — `ProviderMisconfigured` split out of `ProviderUnavailable`
**Rejected:** one `ProviderUnavailable` covering unreachable endpoints, refused credentials, and
missing models — and separately, leaving retry classification entirely to T14.
**Reasoning:** the principle is that **an interface must preserve distinctions only the adapter can
observe; what to do about them is the caller's policy.** A revoked key and a dead endpoint both
arrive as a failed call, and once the exception crosses the boundary the difference is gone
forever — so a contract that collapses them makes correct retry classification impossible
downstream no matter how well T14 is written. Each error class now states its own `Retry:` answer,
because family membership cannot: `ProviderMisconfigured` will never succeed on retry, `RateLimited`
will.
**Known limit, accepted:** a wrong endpoint URL is indistinguishable from an outage at this layer —
both are a failed connection — so a `.env` typo arrives as `ProviderUnavailable` looking retryable.
T8's DoD (a raw command-line call before any adapter exists) is what catches it; an attempt cap
bounds it otherwise. Documented in the class rather than left implicit.
**Open, deliberately not settled:** `StructuredOutputError` is genuinely a third state — retry helps,
but bounded, since sampling is stochastic while a schema the model cannot satisfy is a prompt bug.
The two-way `Retry:` vocabulary cannot express it. Named in the docstring and left to T14 rather
than redesigned during a contracts-only task.

### D25 — Azure-native is the primary stack; two stubs get their own iteration
**Rejected:** keeping local as the default path, and separately, leaving Service Bus and Container
Apps stubbed indefinitely per D5.
**Reasoning:** user decision. `RUNTIME_ENV=azure` becomes the default at T8. D5's reasoning — that
implementing the queue and render backend moves debugging into the cloud, where POC velocity dies —
still holds for the POC phase, so those two stay stubbed through iteration 3, but they are no longer
permanently deferred: new iteration 5.5 (T34, T35) makes them real before RAG. This surfaced a
dependency error: T35 needs a container image, and the Dockerfile was scheduled in T33 at the very
end of RAG. It moves to T35.

---

## 2026-08-22 · T4 — Domain models

*Naming note for anyone reading upward: the D15-D18 block above is headed "T4 — Toolchain spike"
and refers to the pre-iteration spike, not to this task. It predates a renumbering — its "T10" and
"T14" are now T17 and T35. `tasks.md` is the authority on what a task number means.*

### D26 — Strict-mode conformance is enforced by a test over a marker base class
**Rejected:** reviewing each schema by eye, and separately, a hand-maintained list of LLM-facing
models for the test to iterate.
**Reasoning:** Azure rejects a non-conforming schema with a 400 *at call time*, so the failure
lands mid-run in T15 or T16, minutes in, looking like an adapter bug. `core/strict_schema.py`
exists so that inheriting `StrictSchema` both supplies `additionalProperties: false` and *marks*
the model as LLM-facing; the test in `tests/test_slot_schemas.py` enumerates subclasses
recursively and checks every one. A schema added in a later task is therefore covered by virtue of
existing. A registry someone has to remember to update is a registry that goes stale, and the
staleness would be invisible — the parametrised tests would simply run over a smaller set and pass.
**Known limit:** the unsupported-keyword list is the conservative set. Azure may have relaxed some
since; a test stricter than the backend is safe, but if T15 wants a schema this test rejects, check
live behaviour at T8 before loosening it rather than after.

### D27 — `Importance` is an enum, not an int with `ge=1, le=5`
**Rejected:** `importance: int = Field(ge=1, le=5)`, which is the obvious spelling.
**Reasoning:** strict mode drops range keywords. `ge`/`le` would be *silently absent* from the
schema Azure enforces — the constraint would exist in pydantic, validating a response that already
arrived, rather than in the generation constraint that shapes it. `enum` is on the supported list,
so an enum moves the bound to where it actually binds. This generalises: **in an LLM-facing schema,
express a bounded value as an enum, never as a range.**
**Discovered in passing:** pydantic copies a class docstring into the JSON Schema, so a verbose
enum docstring is shipped to the model as prompt tokens on every call. `VisualIntent` and
`Importance` therefore keep one-line docstrings with the rationale in comments above them. Do not
"improve" those docstrings back into paragraphs.

### D28 — `SegmentPlan` and `Segment` are separate classes
**Rejected:** one `Segment` model used for both the LLM's outline response and pipeline state,
with the timing fields simply left unset by the prompt.
**Reasoning:** Invariant 1 made structural instead of procedural. A combined model puts a
`duration_ms` field in the schema the LLM is shown and is forbidden to fill, leaving the project's
single most expensive invariant — measured audio, never an estimate — enforced by prompt wording.
Two classes mean the model never sees the field. `SegmentPlan.to_segment(index)` is the one-way
bridge, and it lives on the *plan* rather than as `Segment.from_plan` so that
`core/outline_schema.py` imports `core/models.py` and never the reverse.
**Also why there are two modules:** `core/models.py` reached 196 of its 200 lines, and the next
`/newintent` would have breached the ceiling. Split by responsibility per CLAUDE.md — pipeline
state and enums here, what the LLM returns one module over.

### D29 — `Segment.slots` is `dict[str, Any] | None`, not a discriminated union
**Rejected:** a `Literal` discriminator field on each slot schema, with `slots` typed as a
discriminated union.
**Reasoning:** the union is the better-typed design and was preferred on the merits, but it
requires a redundant `intent` field inside every LLM-facing schema, and pydantic emits a
single-value `Literal` as `const` — a keyword not on strict mode's supported list. Betting T15 on
that before T8 has made a single live call is the wrong order. `slot_schema_for(intent)` in
`core/slot_schemas.py` is the typed accessor instead: it turns "this segment wants a comparison"
into the class to validate against.
**Cost accepted:** the API contract at T19 and the generated client at T24 see an untyped object
for this one field. **Revisit at T24** if it bites — by then strict mode's real behaviour is known.

### D30 — Six visual intents, chosen against T17's workload rather than expressiveness
**Rejected:** eight (adding `TIMELINE` and `DEFINITION`), and four.
**Reasoning:** every member costs a hand-authored Jinja template with seekable animation at T17,
and each must also degrade to a single sensible static frame because the resolver can put any
segment on Tier 0. Six covers the demo topic end to end — code walkthrough for the vulnerable
query, comparison for safe against unsafe, flow diagram for the attack chain — without making T17
a template-writing marathon. `/newintent` is the cheap path to more once the pipeline is proven,
and it touches all seven registration points at once.

### D31 — Pipeline state forbids extra fields too, without inheriting `StrictSchema`
**Rejected:** leaving `Segment` and `VideoJob` on pydantic's default, which *ignores* unknown keys.
**Reasoning:** found by a test that failed on the assumption. The default means a `durationMs` in a
T19 request body is dropped in silence, producing a segment that looks fine and is unmeasured —
precisely Invariant 1's failure mode, arrived at from the opposite direction. So both set
`extra="forbid"` directly. They deliberately do **not** inherit `StrictSchema`: they carry defaults
freely, and inheriting it would enrol them in D26's conformance test, which they would rightly
fail. The base class is a marker for "the LLM fills this", not a general-purpose strict model.

---

## 2026-08-22 · T5 — Tier resolver

The first behaviour in the repo, and the first code to compute a frame cost — which is how D32
below got found. Everything here is pure: no I/O, no clock, no config.

### D32 — At the configured budget, Tier 2 buys *shortness*, not importance
**Discovered, not decided.** `FRAME_BUDGET=600` at `FPS=24` buys **25 seconds** of Tier-2
animation. `SECONDS_PER_SEGMENT=28`. An average segment therefore cannot be Tier 2 at all.

D9 set the budget at ~2000 and asked for "2-3 Tier-2 scenes". D16 then cut it to 600 on measured
render throughput (1.7-2.7 frames/sec) and, in doing so, made that arithmetically impossible.
Both decisions were right on their own terms; nothing had yet multiplied a duration by a frame
rate, so the conflict was invisible.

**Rejected:** capping Tier-2 animation at N seconds with a static hold for the remainder, which
would let 600 frames buy three short animations. That redefines what Tier 2 *is* and obliges
every template to honour it — T17's decision, not T5's. Also rejected: quietly raising the
constants until the demo looks good.

**Reasoning:** the resolver stays truthful to the cost model in the `scene-templates` skill and
lets the number be wrong where the number lives. On a realistic 412-second, 15-segment outline it
produces `STATIC=2 REVEAL=11 ANIMATED=2` at 594/600 frames — all three tiers, so the system is
not decorative — but **both `CRITICAL` segments are demoted to Tier 1** because they are 34s and
38s, while the winners are a 9s title card and a 12s stat callout. That is a frame budget
behaving correctly. Pinned by `test_the_budget_buys_shortness_not_importance` so a future reader
does not file it as a bug.
**Open:** whether to raise `FRAME_BUDGET`, shorten segments, or accept short-segment Tier 2 as
the product. Cannot be settled until T16 produces real measured durations. Do not tune it against
the fixture.

### D33 — Importance sets an *ideal* tier; the budget demotes from it
**Rejected:** a single greedy pass promoting segments by importance until the budget runs out.
**Reasoning:** one pass lets a single long, important segment consume the entire budget before
anything else gets even a reveal — precisely the single-tier outcome D9 calls decorative. So
`IDEAL_TIER` maps importance to the tier a segment *wants* (CRITICAL/MAJOR to Tier 2,
NORMAL/MINOR to Tier 1, ASIDE to Tier 0), reveals are seeded in a first pass at ~7 frames each,
and animations compete for what is left in a second. The spread becomes a property of the
algorithm rather than an accident of the input.
Keeping `ideal` alongside `assigned` on the result is what lets `/tiers` report "demoted from
Tier 2" — a bare `dict[int, Tier]` throws that away, and the command's output spec already
presupposed it. Two importances aim at Tier 2 rather than one so the budget genuinely binds:
with a single candidate there is nothing to choose between and demotion never happens.

### D34 — An unmeasured segment raises; there is no `MeasuredSegment` type
**Rejected:** a narrower input type carrying `duration_ms: int`, so that passing an unmeasured
segment would be a *type* error — the structural enforcement D28 used for `SegmentPlan` and that
`scene_author` gets from a required parameter.
**Reasoning:** the project runs ruff, not mypy. A type error nothing checks is a comment. The
runtime `ValueError` names the offending indexes and says *why* — Tier 2 costs duration x fps, so
an unmeasured segment would look free and spend the budget on nothing. That is the ordering bug
wearing a different hat, and it fires in every environment rather than in the one that runs a
type checker. **Revisit if mypy is ever added**; the structural version is genuinely better then.

### D35 — `scale_frame_budget` lives in `core/frame_budget.py`, with no import edge back
**Rejected:** keeping it in `core/tier_resolver.py`, which hit **220 lines** with it.
**Reasoning:** the 200-line ceiling forced the question, but the split is by responsibility per
CLAUDE.md rather than by line count: the resolver *spends* a budget, this decides *how large* one
is, and nothing in the budget module knows what a tier is. The resolver deliberately does **not**
import it — the caller calls both and passes one answer into the other — which keeps T5's DoD
("imports nothing but stdlib and `core.models`") literally true rather than true-in-spirit.

### D36 — `TIER_SUPPORT` ships as a no-op registration point
**Rejected:** dropping it until an intent with no Tier 1 form actually appears.
**Reasoning:** it maps all six intents to all three tiers, so it changes no behaviour today and
looks like dead weight — which is exactly why it needs a decision entry, because the instinct on
reading it is to delete it. `/newintent` step 5 already promises the resolver holds per-intent
characteristics, and T17 is the first code in a position to *know* whether, say, a `STAT_CALLOUT`
has anything to reveal in stages. Declaring that now would be a guess the template author then
has to honour. The map is the place T17 records what it finds, and
`test_every_visual_intent_declares_its_tier_support` fails if a future intent is added to the
enum and not to it.

---

## 2026-08-22 · T6 — Test foundation

The resolver reaches full branch coverage, and the six fakes every task from T14 on is tested
against get written. The fakes are the consequential half: they are the only implementation of
each contract that exists until T9, so whatever they teach the pipeline is what it learns.

### D37 — A fake is an adapter, and every fake can be made to fail on demand
**Rejected:** fakes that only ever succeed, and separately, per-fake ad-hoc failure hooks.
**Reasoning:** an in-memory fake succeeds at everything, which is the problem with it. `JobQueue`
documents `ProviderUnavailable` and `RateLimited` on the *class* rather than per method precisely
because the in-process implementation never raises either -- so T14's retry classifier, written
and tested against the local pool alone, will never have executed its own error paths, and T34
is where that bill arrives. `tests/fakes/failure_injection.py` gives all six one shared
`fail_next(method, exc)`, so a test arms a failure and the next call raises it.

One mechanism rather than six, because a fake that fails differently from its siblings is a fake
nobody trusts. `fail_next` rejects a method name that does not exist on the fake: a typo would
otherwise arm a failure that never fires, and the test would pass for the wrong reason.

The wider rule this follows from: **a fake is held to the standard `adapter-parity` applies to
the real adapters at T13.** It may not import a vendor SDK, it raises only from
`interfaces/errors.py`, and it matches its contract in semantics -- not merely in signature.

### D38 — `FakeTTSProvider` writes a real WAV and measures the file it wrote
**Rejected:** returning a plausible constant, and returning a words-per-minute estimate directly.
**Reasoning:** this is the fake whose shortcut would have been most expensive. `duration_ms` is
what every downstream timing decision rests on (Invariant 1), and a constant is indistinguishable
from a real measurement to every caller -- so every timing assertion from T16 on would be checking
a number nobody produced, and the rot would first appear as A/V drift in a rendered video at T18.

So the ordering is inverted: a frame count is chosen first, the audio is written, and the returned
duration is computed back out of the frame count. The two cannot disagree. `estimate_ms` still
uses a speaking rate, which is legitimate *there* because it decides how much audio to generate --
the synthesiser's job -- rather than reporting an estimate as a measurement.

**Verified against the real tool, not just against the library that wrote the file:** `ffprobe`
reads a 9000ms synthesis as `duration=9.000000`. T10's definition of done ("durations match
`ffprobe` within tolerance") is therefore already satisfiable offline, and exactly rather than
within tolerance -- 8000 Hz is an exact multiple of 1000, so the arithmetic never rounds.

### D39 — Fakes enforce the two preconditions an in-process implementation would hide
**Rejected:** permissive fakes that model the happy path and only the errors the interfaces
declare.
**Reasoning:** two contract terms are stated in the interface docstrings and are *invisible* to an
in-memory implementation. `JobQueue.enqueue` requires a JSON-serialisable payload because Service
Bus crosses a wire -- but an in-process queue hands the very same object back, so a `Path` or a
model instance works perfectly and fails at T34. And `Storage` keys are relative POSIX strings,
while a dict accepts an absolute path or a `..` without complaint, either of which escapes the
disk adapter's root once T11 gives it a real filesystem. One `json.dumps` and one `check_key`
close both, and in doing so **set the spec T11 and T34 must match** rather than inheriting one.

The risk accepted is a fake stricter than the real Azure adapters turn out to be. That is the
cheap direction to be wrong in: a false failure at T11 is visible immediately, where a false pass
is not.

**Caught by `project-reviewer`:** `FakeStorage.exists` was the one method that skipped
`check_key`, because the test only parametrised `put_bytes`. A malformed key returned `False`
there instead of raising -- the single place a `..` would have quietly answered for a file
outside the root. Fixed, and the test now covers all six methods. The general lesson is that a
validation rule tested on one method of six is a rule tested nowhere.

### D40 — Conformance is mechanical, and the contract list is discovered rather than written down
**Rejected:** reviewing the fakes against the interfaces by eye, and a hand-maintained list of
contracts for the tests to iterate.
**Reasoning:** the same argument as D26, applied to adapters instead of schemas. `tests/test_fakes.py`
asserts `inspect.signature` equality for all 21 methods, `iscoroutinefunction` on every one of
them (D19 -- a sync fake type-checks fine and dies at the first `await`), and walks each fake
module's **AST** for banned import roots and for invented exception types. AST rather than text,
per the standing gotcha that the boundary greps are plain-text searches and a docstring mentioning
a vendor is not an import.

`contracts()` discovers the ABCs by walking `interfaces` for classes with a non-empty
`__abstractmethods__`, so **T30's `VectorStore` will demand a fake the day it is written** rather
than the day someone remembers to update a list here. A registry someone has to maintain goes
stale invisibly -- the parametrised tests simply run over a smaller set and pass.

Signature equality compares annotation *objects*, which imposes two constraints worth knowing
before they cause a confusing failure: no fake may use `from __future__ import annotations`, and
`FakeLLMProvider` must import the same `T` TypeVar the contract uses rather than declaring its own.

### D41 — The skill-pack version ordering is defined in the fake, and T7 must adopt it
**Rejected:** promoting `version_key` to production code now, and leaving the fake's ordering
unspecified.
**Reasoning:** `SkillRegistry.versions` promises "newest first", which is not a property a string
sort delivers -- `2.10` sorts below `2.9`. The fake needs an answer today and T7 writes the real
registry next session, so the rule lives in `tests/fakes/skill_registry.py` with the constraint
stated in its docstring. Promoting it to a shared module now would be pulling T7's scope forward
to serve a test.
**Open:** the two implementations must agree. They only diverge once a pack has a second version,
which is late and quiet. **T7 owns closing this** -- adopt `version_key` or replace both.

### D42 — Full branch coverage is verified by a documented command, not by a gate
**Rejected:** `--cov-fail-under=100` inside the `hook_py_quality.py` block that already runs the
resolver's tests on every edit, and a self-referential test that measures the suite from inside it.
**Reasoning:** user decision. The hook version slows every write to `core/tier_resolver.py` and
makes an unrelated edit fail for a reason that is not about the edit; the test version is awkward
to debug for the same reason it is clever. `branch = true` now sits in `[tool.coverage.run]`, so
a coverage run is a *branch* coverage run without a flag anyone has to remember, and the command
is recorded in `handoff.md`.
**Risk accepted:** coverage can decay between checkpoints without anything failing. `/checkpoint`
re-runs the command.

## 2026-08-23 · T7 — Runtime skill registry

The last task before Azure. The contract and the reference semantics already existed, so this task
was the real implementation, the four packs, and one inherited debt (D41) to close.

### D43 — `version_key` is promoted to `interfaces/skill_registry.py`, closing D41
**Rejected:** leaving it in the fake, and a shared module under `adapters/`.
**Reasoning:** the second option is not merely worse, it is *impossible*. `tests/test_fakes.py`
bans `adapters` as an import root inside fakes, so `FakeSkillRegistry` could never have imported
it and the two implementations would have stayed divergent — which is the exact bug D41 opened.
`interfaces/` is the one home both can reach, and it is the right one on merits too:
`SkillRegistry.versions` *promises* "newest first", so defining what that phrase means belongs
next to the promise rather than inside one of the things keeping it. D22's precedent, applied to
a function instead of a model.

Verified that a bare function in `interfaces/` breaks neither discovery mechanism:
`test_interfaces.py` iterates a hand-written `CONTRACTS` map and `test_fakes.py`'s `contracts()`
filters on `inspect.isclass` plus a non-empty `__abstractmethods__`. `tests/test_skill_registry_parity.py`
now runs one set of assertions over both implementations, and T11's Blob registry joins by adding
a line to `REGISTRIES`.

### D44 — A pack is markdown with flat `key: value` frontmatter, not YAML
**Rejected:** a JSON sidecar per version, and no metadata at all.
**Reasoning:** `SkillPack.metadata` is `dict[str, str]`, and a parser that can produce *only* that
is a stronger guarantee than a convention not to nest. YAML would have meant a new dependency
whose whole selling point — nesting, tags, object construction — is the thing T7's definition of
done says packs must not have. "Content is data, not code" is enforced by the format's inability
to express code, rather than by everyone remembering.

The sidecar was the close call: it needs no bespoke parser. It lost on two files per version and
on separating metadata from the prose it describes. The parser it avoids is fifteen lines and is
pinned by `tests/test_skill_pack_format.py`.

Identity comes from the path — the directory is the name, the file stem is the version — so a
pack cannot rename or re-version itself by editing its own frontmatter.

### D45 — A malformed pack name raises `ValueError`, even from `versions()`
**Rejected:** returning an empty list for anything that is not found, malformed or not.
**Reasoning:** the contract says `versions` never raises for an *unknown* pack, and that stays
true. Malformed is a different question (D39, exactly as `FakeStorage` distinguishes a bad key
from an absent one): answering `../../secrets` with `[]` reports a traversal attempt as an
ordinary miss, and the caller cannot tell the two apart. The interface docstring now says so, so
the deviation is written down where T11 will read it. **This sets the spec the Blob registry
must match.**

### D46 — A pack name may not *end* in `.`, and the reason is written down in the code
**Rejected:** validating only leading dots and separators, which is what shipped and what review
caught.
**Reasoning:** Windows strips a trailing dot when it resolves a path for an existence check but
not when it enumerates a directory. On this project's primary platform that meant `outline.`
passed validation, resolved to the `outline` directory, and returned a `SkillPack` whose `name`
field was `"outline."` — a pack whose identity did not match what it was loaded from, which is
the one thing `parse_pack` promises cannot happen. `outline..` passed the same existence check
and then raised a raw `FileNotFoundError` out of `versions()`, straight through the adapter
boundary and in direct violation of the never-raises promise.

The rule looks like tidiness, so the rationale sits in a comment above `_check_segment` rather
than only here. Both rejection lists in the tests now carry trailing-dot cases; neither did
before, which is why it shipped.

**A second fix came out of the same finding.** `DiskSkillRegistry._listing` now performs the
`glob`/`iterdir` call *and* the iteration inside one `try`, translating `OSError` to
`ProviderUnavailable`. `iterdir` and `glob` are generators, so a failure surfaces at the first
item pulled rather than at the call — catching only one of the two positions leaves the other
uncovered, and which one a given filesystem uses is not something this adapter should have to
know. An unreadable directory is the backend failing, not a pack being absent, so it translates
rather than returning a misleading `[]`.

### D47 — Disk reads stay synchronous inside the `async def`s
**Rejected:** wrapping every read and listing in `asyncio.to_thread`.
**Reasoning:** a pack is a few kilobytes read once at the start of a job, so the thread handoff
costs more than the blocking read it avoids — and it would give the appearance of an async
filesystem that neither this adapter nor `pathlib` has. The parity that matters against the Blob
registry is in return types and error behaviour, not in where the work runs.
**Open:** raised in review and correct to revisit. Once T12's asyncio pool runs jobs concurrently
on one loop, a slow read — network share, antivirus scan, contended disk — stalls every job
sharing that loop rather than only the one reading. **Re-check at T12/T13**, when there is
concurrency to measure against instead of speculate about.

## 2026-08-23 · T8-T11 — Azure groundwork and the first real adapters

Four tasks in one session, by user request. The first code in this project that leaves the
machine, and the first time any of iteration 1's contracts had a second implementation — which is
the only thing that ever tests whether a boundary was drawn in the right place.

### D48 — Azure Speech runs on the existing S0 resource, not a new F0. D7 is reopened.
**Rejected:** provisioning an F0 alongside it, which is what D7 chose.
**Reasoning:** user decision, taken with the numbers in front of it. D7 picked F0 for 500k free
neural characters a month, and that reasoning was sound when the alternative was paying for
something. It is not free that was actually wanted, though — it was *cheap*, and S0 neural TTS at
roughly $15/1M characters puts a 7-minute video at about **$0.09**, which against a $200 credit is
noise. What F0 costs instead is a request-rate cap of 20 per 60 seconds, and T16 narrates ~15
segments concurrently. So the free tier buys nothing here and constrains the one traffic shape
this project actually generates. **D7's conclusion changes; its reasoning does not** — on a
subscription with no credit, F0 would still be right.

### D49 — The deployment is `gpt-5.4-mini` on **DataZoneStandard**, not GlobalStandard
**Rejected:** GlobalStandard, which is the default and what an unthinking `az ... deployment
create` produces. Also rejected: `gpt-5-mini` on GlobalStandard (500k TPM) and `gpt-4.1-mini`.
**Reasoning:** this is the failure T8's definition of done was written for, met in the wild.
`az cognitiveservices usage list -l eastus` reports `OpenAI.GlobalStandard.gpt-5.4-mini` with a
limit of **0** and `OpenAI.DataZoneStandard.gpt-5.4-mini` with **200** (200k TPM). Deploying the
obvious way yields a deployment that exists, reports `Succeeded`, and can never serve a token —
and the resulting failure looks exactly like an adapter bug for as long as you are willing to
stare at it. Same picture in westus3, so it is a subscription-level quota shape rather than a
regional accident. **Check the SKU's quota, not just the model's availability**, before every
future deployment.

### D50 — `check_key` is promoted to `interfaces/storage.py`
**Rejected:** a shared module under `adapters/`, and leaving the copy in `tests/fakes/storage.py`
for the two real adapters to duplicate.
**Reasoning:** D43's argument, applied a second time, and the first option is again not merely
worse but *impossible*: `tests/test_fakes.py` bans `adapters` as an import root inside fakes, so
`FakeStorage` could never import it and the three implementations would drift. `interfaces/` is
the one home all three can reach, and it is right on merits — the `Storage` docstring is where
"keys are relative POSIX strings" is promised, so the function enforcing it belongs beside the
promise. D39 set this spec from inside a test; it is now production code that the test depends on
rather than the other way round.

### D51 — Adapters take explicit constructor arguments and never read `os.environ`
**Rejected:** each adapter reading its own settings, which is shorter and is what the
`LLMProvider` docstring's "adapter configuration read from the environment" could be taken to mean.
**Reasoning:** `config.py` is the only module permitted to name a concrete adapter class, and
T13's definition of done is that flipping `RUNTIME_ENV` swaps every adapter with no change in
`core/`. An adapter that reads the environment itself makes that test vacuous — it would pass
whether or not `config.py` did its job, because the adapters would be self-wiring. The environment
is read in exactly two places, both outside the adapters: `scripts/verify_azure.py` and
`tests/azure_live.py`.

### D52 — The adapter owns the retry policy outright; the SDK's own retries are switched off
**Rejected:** leaving `openai`'s default `max_retries=2` in place underneath tenacity.
**Reasoning:** two independent retry loops compose by multiplication, not addition. A configured
bound of 4 attempts silently becomes 12, and a rate limit that should surface in seconds takes
minutes — with the retries that did the waiting invisible to every log line and every test. One
policy, in one place, is worth more than two good ones. `max_retries=0` on the client is the whole
fix and it is one line, but it is one line nobody adds by accident.

### D53 — A 400 that rejects the *schema* is `ProviderMisconfigured`, not `StructuredOutputError`
**Rejected:** routing every 400 to `StructuredOutputError` on the grounds that it concerns the
structured-output request.
**Reasoning:** `StructuredOutputError` promises "retry may help, bounded", and that is false here.
The model never ran: Azure refused the schema before generation, and it will refuse it identically
forever. Sending it to the retryable class burns every attempt T14 grants to arrive at the message
the first attempt already had. The split is made on a substring match against the message, which is
admittedly not a stable contract — but the *retry answer* is stable even when Azure's error bodies
are not, and a 400 that is not about the schema stays `StructuredOutputError`, since that is a
request this schema provoked.

### D54 — `duration_ms` is measured from the written WAV, never read from the SDK
**Rejected:** returning Azure Speech's `result.audio_duration`, which is available, free, and
correct — T8's smoke run had it agree with `ffprobe` to the millisecond.
**Reasoning:** Invariant 1 is not "the number is right", it is "the number is *measured*". Taking
the SDK's word for it works until an adapter appears whose SDK offers no such field — Kokoro at
T12 — at which point one adapter measures and the other reports, and the two agree right up until
they do not. `adapters/audio_duration.py` is shared by both, so parity in the single most
load-bearing number in the pipeline is structural rather than reviewed. D38 made this exact
argument about `FakeTTSProvider`; this is the same argument surviving contact with a real backend.

### D55 — `aclose()` exists on the Azure adapters and is deliberately *not* on the contracts
**Rejected:** adding a `close`/`aclose` method to `Storage`, `LLMProvider` and `SkillRegistry`.
**Reasoning:** the async Azure clients own connection pools and want closing; the disk adapters and
the fakes have nothing to close. Putting it on the interface would oblige two implementations out
of three to grow a no-op so that the third can be honest — the "written from one implementation's
perspective" failure the `adapter-contract` skill names. The owner of the instance closes it:
`config.py` at T13, the FastAPI lifespan at T19.
**Open, and worth revisiting at T19:** this genuinely is a gap, not a non-issue. If T19 finds
itself special-casing "does this adapter have an `aclose`", the interface was wrong and should
grow the method — with the no-ops accepted as the price.

### D56 — Live tests are a pytest marker, deselected by default, and most risk is pinned offline
**Rejected:** no live tests at all (trusting `scripts/verify_azure.py` alone), and live tests that
run by default.
**Reasoning:** `pytest` must stay offline, network-free and runnable on every edit — so `addopts`
carries `-m 'not live'` and the 25 live tests are opt-in via `pytest -m live`. The more important
half is what is *not* live: a live test only ever exercises whichever branch the backend took that
day, and it will never produce a 403, a truncated body and a 429 in one session. The translation
tables and the retry policies are ours, are pure functions over exception objects, and import fine
with no network — so they are tested exhaustively offline, and the live tests only have to prove a
real call reaches the same code. Live tests **skip** rather than fail without credentials, so a
fresh clone still runs green.

### D57 — Both TTS failure surfaces translate, and the adapter retries. Found by review.
**Rejected:** the version that shipped, which had no retry at all and let setup failures escape raw.
**Reasoning:** `project-reviewer` caught `AzureSpeechTTS` raising `RateLimited` on the *first*
throttle, against `interfaces/tts_provider.py`'s unconditional "the backend throttled the request
**and retries were exhausted**". A caller told its retries are spent backs off at the job level
over a blip that a few hundred milliseconds of backoff would have absorbed — and the sibling LLM
adapter, written the same afternoon, got this right. Two adapters with opposite answers to "does
this retry?" is invisible in either file alone.

Chasing it down surfaced a second, sharper hole that the review had explicitly declined to raise.
Speech fails in **two structurally different ways**: cancellations come back as *results*, but
`SpeechConfig(subscription=..., region="")` **raises `RuntimeError: 5`** — verified, not assumed —
before anything touches the network. That path was unguarded, so a single blank line in `.env`
sent a bare builtin straight through the adapter boundary. It is now `ProviderMisconfigured` with
a message naming all three settings, because the SDK's own message is the character `5`.
**The general lesson: "this SDK reports failures as results" was true and still left an exception
path uncovered.** Construction is not the same surface as invocation. The maps now live in
`adapters/azure/speech_errors.py`, split out when the adapter passed 200 lines.

### D58 — T10 ships its Azure half only; Kokoro moves to T12
**Rejected:** installing Kokoro this session to close T10 as written.
**Reasoning:** user decision. Kokoro needs `torch` (~2.5 GB), `soundfile`, and espeak-ng as a
native Windows install for out-of-dictionary words — the dependency D6 cites as one of the two
original reasons to reach for Docker. T12 already owns the local adapter set (Ollama, the asyncio
pool, Playwright), so Kokoro joining its siblings costs nothing and keeps a large download and a
real Windows risk off the critical path of a four-task session. **T10 stays `in-progress`**;
`adapters/audio_duration.py` is already shared and waiting for it.

## 2026-08-23 · T12 — Local render backend & job queue; Azure stubs

D58's plan changed again before this session finished: the user chose to stay Azure-focused rather
than build out the rest of the local stack right now. What actually shipped is narrower than
`tasks.md`'s original description, and the render backend's design turned up two real bugs during
manual smoke-testing that would not have been caught by any test written against assumption alone.

### D59 — Ollama and Kokoro are cut from T12 entirely, pushed to a future (unnumbered) iteration
**Rejected:** building all four local adapters as `tasks.md` originally scoped T12, and separately,
building Kokoro alone while cutting only Ollama.
**Reasoning:** user decision, made explicitly to stay Azure-focused rather than reopen D58's
Windows risk (torch, native espeak-ng) a second time. Ollama was cut alongside it rather than kept
— it is cheap and low-risk on its own, but there is no product reason to build a local LLM path
right now if the local TTS path is not coming with it. **`RenderBackend` and `JobQueue` stay in
scope** regardless of this cut: rendering is not a local-vs-Azure choice the way LLM/TTS are — the
same Playwright+HyperFrames rendering code this task builds is what T35's Container Apps job will
eventually run inside a container, not a local-only throwaway.
**Ripple, not resolved here:** T10 cannot close via T12 anymore (D58's plan is void a second time).
T13 lists T10 as a dependency and its DoD talks about `RUNTIME_ENV=local` swapping every adapter —
that is not achievable until Ollama/Kokoro exist. `tasks.md` is updated to flag this; **T13's own
planning session decides** whether to wire local without them, stub them, or defer T13's local-swap
claim. Not decided here.

### D60 — `RenderBackend.capture` drives Playwright directly; `render`/`lint` shell to the HyperFrames CLI
**Rejected:** doing everything through the CLI, including stills, via `npx hyperframes snapshot
--at <t1,t2,t3>`.
**Reasoning:** the user's explicit priority is shortest time to video. `snapshot` boots a fresh
Node process and browser per invocation; Tier 1 needs several stills per segment, across many
segments per job, so that cost multiplies where a kept-alive browser page does not.
`adapters/local/playwright_capture.py` launches Chromium once, lazily, and reuses it across every
`capture()` call for the adapter's lifetime. `render` (full Tier-2 video) and `lint` (the
composition-wide validation gate) stay on the CLI — CLAUDE.md already names those as the render
adapter's job, and the CLI owns frame-accurate video encoding in a way reimplementing would not
improve on.
**Discovered as a real constraint while building this, not designed in advance:** `hyperframes
lint`/`check` always validate a whole *project directory* (`index.html` + `compositions/`), with no
flag to target one arbitrary file — confirmed empirically, not assumed, and it is the reason two
composition files with `data-composition-id` in the same directory both fail lint
(`multiple_root_compositions`). `hyperframes_cli.py` therefore assumes each composition already
lives alone in its own directory, named literally `index.html`, and raises `RenderFailed` loudly
rather than silently lint-validating the wrong file if that assumption is violated. **Flagged for
T17 to confirm** once composition generation actually exists and picks a real directory layout.

### D61 — Every `page.evaluate` seeking the GSAP timeline must discard its return value
**Discovered, not decided** — a real bug that shipped in the first version of
`playwright_capture.py` and was caught by manual smoke-testing, not by any test written in advance.
`"([id, t]) => window.__timelines[id].seek(t, true)"` hung indefinitely on every call: GSAP's
`.seek()` returns the timeline itself for chaining, and an implicit-return arrow function hands
that back to Playwright, which then tries to structurally clone a large, circular, DOM-and-function
-laden object across the browser/Python boundary rather than erroring outright.
**Fix:** braces, not an implicit return — `"([id, t]) => { window.__timelines[id].seek(t, true); }"`
— so nothing comes back to serialise. `project-reviewer` grepped the rest of the codebase for other
`page.evaluate`/`eval_on_selector` calls during its pass; the remaining three all return plain
primitives (a string, two numbers) and carry no equivalent risk. **Worth remembering generally:**
an arrow function passed to `page.evaluate` should return nothing unless the caller actually wants
the value back — GSAP's chaining convention makes this trap easy to hit by habit.

### D62 — Three resource-leak / contract-escape bugs in the render adapter, found by `project-reviewer`, all fixed before checkpoint
**Rejected:** the versions that shipped from the first build pass.
**Reasoning:**
1. `hyperframes_cli._run` cancelled `proc.communicate()` on an `asyncio.wait_for` timeout but never
   touched `proc` itself, leaving the `hyperframes` process — and the node/chrome-headless-shell
   children `npx` spawns under it on Windows — running orphaned. Combined with `render_backend.py`'s
   retry (which does treat a timeout as retryable `RenderFailed`), a second attempt could start a
   second writer pointed at the same destination path while the first was still running. Fixed with
   a `_kill_tree` helper (`taskkill /T /F /PID`, with a `proc.kill()`/`proc.wait()` fallback) called
   before re-raising. Pinned by
   `tests/test_render_backend_parity.py::test_a_timeout_raises_render_failed_and_leaves_the_backend_usable`
   — forces a nearly-zero timeout, asserts `RenderFailed`, then confirms a normal call afterward
   still succeeds; run live against the real installed CLI, with a `tasklist` check afterward
   confirming no orphaned browser process was left behind.
2. `playwright_capture.PlaywrightCapture._ensure_browser` let a `chromium.launch()` failure escape
   as a raw, untranslated exception — a caller catching `RenderFailed` per the interface contract
   would not catch it — and on a second failed attempt would overwrite `self._playwright` without
   stopping the first one, leaking a driver process per failed call. Fixed: launch failures are now
   caught, the driver is stopped and reset to `None` before the exception is translated and
   re-raised, so a failed launch leaves the object in a clean state for the next attempt.
3. Found on a second, later review pass, after 1 and 2 were already fixed: `PlaywrightCapture.capture`
   called `page = await browser.new_page()` *before* its own `try` block. A crashed browser most
   often fails first at exactly that call (the first thing that has to reach it over CDP), not at
   `goto`, so a browser crash there raised an untranslated exception instead of `RenderFailed` --
   breaking the interface contract *and* silently defeating `render_backend.py`'s retry, which
   matches only on `isinstance(exc, RenderFailed)`. This is the same shape of bug as 2, one call
   later, and it shipped past the first review pass because that pass was scoped to the two bugs
   named above rather than a fresh read of the whole file. Fixed by moving `new_page()` inside the
   `try`, with `page = None` beforehand so the `finally` block's `page.close()` stays safe if the
   browser itself is what failed.
**General lesson, matching an existing one already in `handoff.md`'s Gotchas:** "check what
`project-reviewer` dismisses, not only what it reports" (D57) held again in a new shape -- a review
pass that is handed a specific list of things to verify can verify them perfectly and still miss a
sibling bug one call away. All three were real, and none were things offline tests could have
caught, since none reproduce without a real subprocess or a real (or deliberately broken) browser.

### D63 — New pytest marker `local_live`, alongside `live`
**Rejected:** reusing `live` for local-runtime-dependent tests too, and a separate whole test file
outside the existing parity-file pattern.
**Reasoning:** `live` is documented and understood specifically as "hits Azure, costs money, skips
without credentials" (D56). Folding "needs Playwright's browser and the HyperFrames CLI actually
installed" into the same marker would surprise a reader running `pytest -m live` expecting only an
Azure bill. `local_live` copies `live`'s exact contract — deselected by default via
`addopts = "-q -m 'not live and not local_live'"`, skips rather than fails when the dependency is
absent — for a different kind of "real backend." `tests/test_render_backend_parity.py` follows the
established `IMPLEMENTATIONS` fixture-parametrisation shape from `test_storage_parity.py` rather
than becoming a bespoke file, with `"local"` wrapped in `pytest.param(..., marks=pytest.mark.local_live)`
the same way `"blob"` is wrapped in `pytest.mark.live`.

## 2026-08-23 · T13 — Config resolver & parity

`config.py` closes the interface/adapter boundary: the one module still missing before flipping
`RUNTIME_ENV` could mean anything. This session also closed two items several earlier tasks had
left explicitly open for it -- T13's own T10 dependency gap, and D55's `aclose()` question.

### D64 — `RUNTIME_ENV=local` resolves four adapters for real and raises loudly for the other two, rather than stubbing or omitting them
**Rejected:** signature-matched `NotImplementedError` stubs for Ollama/Kokoro -- T12's exact
pattern (`ServiceBusJobQueue`, `ContainerAppsRenderBackend`), applied symmetrically to the local
side. Also rejected: narrowing `config.py`'s scope to skip `LLMProvider`/`TTSProvider` resolution
entirely and only wire the four interfaces that have two real implementations.
**Reasoning:** user decision, closing the three-way fork `tasks.md` and `handoff.md` both left for
this task's own planning session (T13 lists T10 as a dependency; T10 is not `done` -- Ollama and
Kokoro don't exist, D58/D59). `Storage`, `SkillRegistry`, `JobQueue` and `RenderBackend` all resolve
for real under `RUNTIME_ENV=local` (`config._storage` et al, exercised directly by
`tests/test_config.py::test_each_local_builder_returns_the_local_adapter`), but `build_adapters()`
raises one `RuntimeError` naming both Ollama and Kokoro and pointing at D58/D59 -- before calling
any of the four working local builders -- rather than assembling a partial bundle. The stub-adapter
alternative was seriously considered and is the established precedent, but the user chose not to
write any Ollama/Kokoro code, even raise-only, until a task actually claims T10; `_llm_provider`/
`_tts_provider`'s local branch raises inline in `config.py` instead, so there is still no local
implementation of either interface anywhere in the repo.
**Open:** T10 stays `in-progress`. Whichever future task builds Ollama/Kokoro only has to fill in
`_llm_provider`/`_tts_provider`'s local branch and delete `build_adapters()`'s upfront raise -- the
Azure branch and the other four interfaces need no change.

### D65 — `config.py` owns adapter lifetimes via `close_adapters()`, closing D55; best-effort by design
**Rejected:** adding `aclose()` to the six interface contracts (D55's original rejection,
reaffirmed rather than revisited), and a first-failure-stops-everything `close_adapters()`.
**Reasoning:** D55 predicted `config.py` would be the module positioned to own the four adapters'
off-contract `aclose()` (`AzureOpenAILLMProvider`, `BlobStorage`, `BlobSkillRegistry`,
`PlaywrightHyperFramesRenderBackend`) once it existed -- this task is that module. `close_adapters()`
closes whichever of the six resolved instances define `aclose()` via `getattr`, generic over which
four so a future real `ServiceBusJobQueue`/`ContainerAppsRenderBackend` (T34/T35) growing one needs
no edit here. `project-reviewer` caught the first version stopping at the first failing `aclose()`
-- a real risk once T19's FastAPI lifespan is the caller, since a browser or connection-pool close
raising during shutdown would otherwise leak every adapter ordered after it. Fixed with
`asyncio.gather(..., return_exceptions=True)` plus a log line per failure, pinned by a regression
test that one adapter's `aclose()` raising does not stop a later one's from running.
**Also caught by the same review pass, fixed alongside:** `_env`'s `required` check treated a
whitespace-only value (`AZURE_OPENAI_API_KEY="   "`) as satisfied, which would have failed later
inside the vendor SDK with a far less clear error than `config.py`'s own; and the two
`int(_env(...))` concurrency reads raised a bare `ValueError` instead of the module's usual named
`RuntimeError`. Both are one-line fixes (`value.strip()`; a small `_env_int` helper), both pinned by
new tests, and both are the same shape as D57/D62's standing lesson -- a review pass scoped to what
it was asked to check can still turn up a sibling issue on a fresh read of the whole file.
