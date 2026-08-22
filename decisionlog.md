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
