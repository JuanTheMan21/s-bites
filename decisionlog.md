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

## 2026-08-23 · T14 — LangGraph skeleton

The first code to actually drive the six interfaces as a pipeline. `core/graph/` now holds state,
a real `interfaces/errors.py`-aware retry classifier, three placeholder-ish nodes, and the
`Send`-based fan-out/checkpoint/resume mechanics every later pipeline task hangs off. Two
`project-reviewer` passes this session, both finding real issues in the same file -- D67 records
both.

### D66 — `GraphContext` is its own type, not `config.Adapters`, and drops `JobQueue`
**Rejected:** reusing `config.Adapters` directly as the graph's `context_schema`.
**Reasoning:** `config.py` is allowed to know about `core/graph/`; the reverse would tie `core/`
to the concrete resolver module for no functional gain, since nothing here needs six adapters
bound to five. `GraphContext` (`core/graph/context.py`) is typed only against `interfaces/` ABCs
plus a `working_dir: Path`. `queue` is deliberately absent -- driving `JobQueue` (claim a job,
complete/fail it) wraps a whole graph invocation from the outside; no node inside one run touches
it, and no runner exists yet to do that wrapping (T18's CLI is the likely first one). Whoever
builds that runner constructs a `GraphContext` from `config.build_adapters()`'s five matching
fields -- a few lines, not a redesign.

### D67 — D24's "retry, but bounded" cap is a per-error-type `RetryPolicy` pair, not `QueuedJob.attempt` -- and two review passes each found the first version's own claims about it wrong
**Rejected (first pass, shipped then corrected same session):** one shared
`RetryPolicy(max_attempts=3)` applied uniformly to every retryable error, justified by a claim in
the module docstring that `RetryPolicy` only offers one `max_attempts` per node. **That claim was
false** -- `project-reviewer` checked it against the installed `langgraph==1.2.11` source
(`langgraph/pregel/_retry.py`) rather than taking the docstring's own reasoning at face value:
`add_node`'s `retry_policy` accepts a `Sequence[RetryPolicy]`, and the runner picks the *first*
policy whose `retry_on` matches the raised exception and applies *that policy's own*
`max_attempts`. `core/graph/retry_policy.py` now returns `build_retry_policies()` -- two policies:
`RateLimited`/`ProviderUnavailable`/`RenderFailed` at a looser cap (transient, may genuinely need
a few tries), `StructuredOutputError` at a tighter one (sampling noise gets a couple of tries; a
schema the model consistently can't satisfy gives up sooner). `ProviderMisconfigured`,
`ObjectNotFound`/`SkillPackNotFound`, `CompositionInvalid` still match neither policy and
propagate on the first attempt. Both policies and the full classification are unit-tested in
`tests/test_retry_policy.py`, including that every retryable class matches exactly one policy
(not zero, not two).

**A second, independent fresh review pass on the corrected diff found a further wrinkle in the
same fix, also corrected same session.** The two-policy split's own docstring claimed the caps
apply "independently per exception type" -- checked again against the installed LangGraph source
and confirmed also wrong: the runner keeps one shared `attempts` counter for the whole node
invocation, incremented on every failure regardless of which policy matched, and only checks that
shared counter against whichever policy matched the current exception. Reproduced empirically: a
node that fails once with a transient-classified error and then only with `StructuredOutputError`
gets just one further try at the bounded error, not the two `structured_output_max_attempts=2`
promises in isolation -- a prior failure of a different family silently eats into a later
family's budget. `retry_policy.py`'s docstring now states this precisely instead of overclaiming
isolation, names it accepted rather than solved (no node in T14 itself can raise both families in
one invocation -- `synthesize_segment` only calls `TTSProvider`/`Storage`), and tells a future
mixed-failure node (T15's outline/scripting node, the first that can plausibly raise both) what to
do instead of relying on this split: wrap the `LLMProvider.generate` call in its own explicit,
locally-counted retry loop rather than depending on the graph-level `RetryPolicy` sequence for
that isolation. Pinned by
`tests/test_retry_policy.py::test_a_prior_transient_failure_eats_into_the_bounded_policys_own_budget`.

**General lesson, matching D57/D62's standing one, in a third shape now:** a review pass scoped to
verifying one named fix wrote a second bug into the same explanation it used to justify the fix --
worth a fresh, independent read after any correction this size, not just a recheck of what was
named.

**Still genuinely open, not closed by either fix:** D24 literally said to cap
`StructuredOutputError` "using `QueuedJob.attempt`" -- a counter that survives a *requeue*, not
just a node-level counter that survives a *checkpoint resume*. Verified empirically that
LangGraph's per-node attempt counter resets on every fresh `ainvoke` against the same thread, so a
job requeued by a future runner after exhausting the cap above gets the full cap again,
indefinitely -- the exact runaway-cost scenario D24 named T14 to prevent, not yet actually
prevented. `GraphContext` deliberately excludes `JobQueue` (D66), so nothing in `core/graph/` can
see `QueuedJob.attempt` to enforce a cross-requeue ceiling even in principle. **Whichever future
task builds the runner that calls `JobQueue.fail(..., requeue=True)` owns closing this for real**
-- it should refuse to requeue past some `QueuedJob.attempt` ceiling before this module's per-run
cap is reached a second time.

### D68 — Resume relies on LangGraph's own pending-writes durability, verified empirically
**Verified, not assumed:** against the installed `langgraph==1.2.11` /
`langgraph-checkpoint-sqlite==3.1.1` (newer than the `>=0.2.60` floor `requirements.txt` pins from
T1) -- a spike confirmed that with a real file-backed `AsyncSqliteSaver` and `Send`-based fan-out,
one segment's task raising an exception its `RetryPolicy` doesn't cover causes `ainvoke` to raise,
but sibling segments' already-completed writes are checkpointed and are NOT recomputed when the
same `thread_id` is invoked again via `ainvoke(None, config, context=..., durability="sync")`.
`tests/test_graph_pipeline.py::test_a_killed_run_resumes_without_repeating_completed_segments`
pins this: injects `ProviderMisconfigured` (never-retried, so it reliably escapes to `ainvoke`
rather than being absorbed by the node's own policy) via `FakeTTSProvider.fail_next`, then
reconnects a fresh saver/graph against the same sqlite file and thread id. `durability="sync"` is
passed explicitly on every `ainvoke` rather than relying on whatever the library's default is, so
the crash simulation stays meaningful regardless of that default.
**Gotcha found along the way:** `FakeTTSProvider.synthesize` calls `self._maybe_fail("synthesize")`
*before* appending to `self.calls`, so a failed call is never logged. The resume test's assertions
account for this (`calls_before_resume == segment_count - 1`, final
`len(fake_tts.calls) == segment_count`, not `+1`) -- worth remembering if a future test on this
fake assumes failed calls are logged.

### D69 — D47's disk-I/O-under-concurrency question, measured
**Measured:** `scripts/measure_segment_concurrency.py` runs 15 segments through the real graph
against real `DiskStorage` (fake TTS, to isolate disk contention from network/synthesis time).
Observed **0.417s total, 27.8ms/segment**, run via `python -m scripts.measure_segment_concurrency`.
**Reasoning:** in this skeleton, every step inside a segment's task (`FakeTTSProvider.synthesize`,
`DiskStorage.put_file`) is synchronous with no internal `await`, so concurrent `Send` tasks don't
actually interleave I/O -- they run back-to-back within the event loop, same as a plain loop
would. That confirms the shape of D47's concern rather than disproving it: synchronous disk I/O
*does* serialize under this adapter's current implementation. What the measurement adds is scale:
at narration-file size (a few KB-MB of WAV), the absolute cost is small enough not to matter
(order of tens of ms per segment). **Open, carried forward:** this may look different once T18
pushes rendered MP4 segments (tens of MB each) through the same `Storage.put_file` pattern -- worth
re-measuring there rather than assuming today's number holds.

### D70 — `plan_segments` is a deliberate placeholder T15 replaces, not redesigns
`plan_segments` (`core/graph/nodes/plan.py`) builds deterministic placeholder segments (fixed
`VisualIntent.TITLE_CARD`/`Importance.NORMAL`, a templated narration sentence) rather than calling
an `LLMProvider` -- no outline schema/prompt exists until T15. T15's job is to replace this
function's *body* with a real `LLMProvider.generate` call against `core.outline_schema.Outline`;
the graph shape (this node feeding the `Send` fan-out) does not need to change.

## 2026-08-24 · T15 — Outline & scripting nodes

The first task to make a real, non-placeholder `LLMProvider` call from inside the graph. Scoped
down from the user's initial "T15,T16 together" ask, and the session that found -- and fixed -- a
new instance of D67's shared-retry-counter risk in the wild, in a shape severe enough to redo an
entire node's work silently rather than fail loudly.

### D71 — Outline and scripting stay one graph node's body, in two code modules
**Rejected:** two sequential graph nodes (`plan_segments` for the outline, a new node for
scripting) feeding the existing `Send` fan-out, which is one reading of the task's own title,
"Outline & scripting **nodes**" (plural).
**Reasoning:** T14's handoff already pinned `plan_segments`'s contract for this exact task --
"same node name, same position in the graph, same return shape... the graph shape doesn't need to
change." A second graph node would also have required reasoning through whether LangGraph's
`Send`-based fan-out composes safely when its source is itself downstream of another node's
completion, in a resumability-sensitive area this project has already spent real effort getting
right (D68). "Nodes" plural is honoured at the code level instead: `core/graph/nodes/outline.py`
(`generate_outline`) and `.../scripting.py` (`write_narration`) are two small, single-responsibility
modules, both called in sequence from `plan.py::plan_segments`, which remains the graph's one node.

### D72 — T16 is not built this session, despite the user's initial request to combine it with T15
**Rejected:** planning and building T15+T16 together, as literally asked.
**Reasoning:** raised to the user directly, with reasoning, before planning began; they agreed to
split. T16 adds its own materially separate surface on top of T15's already-nontrivial first real
LLM integration -- wiring `core/tier_resolver.py` into the graph, a new scene-authoring LLM node,
and revisiting `FRAME_BUDGET` per D32 -- and this project's own history (D62, D67) already showed
that even a single node's diff can need a second independent review pass to catch a real bug.
That held again in this exact session (D73). T16 now starts against a finished, real T15 instead
of a planned one.

### D73 — `plan_segments` must register with a transient-only `RetryPolicy`; found and fixed by review, then independently re-verified against LangGraph's own source
**Rejected:** the version that shipped first, which attached `build_retry_policies()` (both the
transient policy and the `StructuredOutputError`-bounded one) to `plan_segments`'s node
registration, mirroring how `synthesize_segment` is already registered.
**Reasoning:** this node makes up to `1 + segment_count` (~16) sequential `LLMProvider.generate`
calls in one invocation -- T14's nodes made one interface call each -- which is exactly the
condition `retry_policy.py`'s own docstring (D67) names as the point its shared-attempt-counter
gap stops being inert: a transient failure on one call could silently spend budget a later call's
`StructuredOutputError` cap gets checked against. `core/graph/nodes/structured_retry.py::
generate_with_bounded_retries` was added to close that -- a small, local, per-call retry loop
giving each individual `generate` call its own independent `StructuredOutputError` budget, letting
every other exception propagate immediately to the node-level policy.

That fix was necessary but, as first wired, not sufficient. The node-level `RetryPolicy` still
matched `StructuredOutputError` too, so once a call's *local* budget was exhausted and it
re-raised, LangGraph's node-level retry mechanism caught the same exception and silently retried
the **entire node** -- redoing the outline call and every already-narrated segment to reattempt a
call D24 already says a retry can never fix. Worse than merely wasteful: in the common case (no
further armed failures), the redo would quietly succeed, masking the fact that the "isolated"
retry budget was never actually isolated -- this would have shipped as apparently-correct
behaviour until a schema failure persistent enough to survive a whole-node redo too. Caught by a
`project-reviewer` pass, which reproduced it concretely against the real code (8 raw LLM calls for
a scenario that should have needed at most 4, and the queued failure silently consumed by a redo
rather than raised).

**Fix:** `core/graph/retry_policy.py::build_transient_retry_policy()` -- the transient half of
`build_retry_policies()` alone -- and `plan_segments` now registers with that instead. A second,
independent review pass verified the fix directly against the installed `langgraph==1.2.11`
source (`pregel/_retry.py`), not just the module's own docstring claims, per this project's
standing D57/D62/D67 lesson that a confident retry-semantics claim in a docstring is a claim, not
a fact, until checked against the library itself. Manually reproduced both ways: the old wiring
silently redoes the node and reports success; the fixed wiring raises `StructuredOutputError` for
good, pinned by
`tests/test_plan_segments_retry.py::test_a_persistent_structured_output_error_propagates_without_redoing_the_whole_node`.
**Rule for future nodes, recorded in both functions' docstrings:** any node using
`structured_retry.py`'s local isolation must register with `build_transient_retry_policy()`, never
`build_retry_policies()`, or the isolation is defeated in a different, harder-to-notice way than
not having it at all.

### D74 — The outline call's segment count is a target, not an enforced invariant
**Rejected:** raising `StructuredOutputError` from `generate_outline` if the model returns a
different number of segments than `job.segment_count` asked for.
**Reasoning:** Azure strict mode has no length keyword (`minItems`/`maxItems` are unsupported per
D26), so there is no way to make the model structurally honour an exact count -- only ask for one
in the prompt. Nothing downstream requires an exact match either: the `Send` fan-out and
`core/tier_resolver.py` both operate over however many segments actually exist. Enforcing it would
invent a new failure/retry mode over a property the DoD, and the rest of the pipeline, do not
actually depend on.

### D75 — The `outline` and `scripting` packs work at `1.0`; no `1.1` was needed
**Verified, not decided.** T7 and T14's handoff both flagged that these packs had never been sent
to a real model and might need a `1.1` once they were. The live test
(`tests/test_live_plan_segments.py`) and a manual run against the real Azure deployment for a
"SQL injection" topic both came back clean on inspection: short declarative sentences, no
markdown, correct second/third-person voice per house-style, narration in the 63-67 word range
against the scripting pack's ~70-80-word target (under, not padded -- which the pack itself
prefers). No pack edit was made this session. Left open for a future session if a different topic
or model version surfaces a real gap; not treated as a settled "never needs revisiting."

## 2026-08-24 · T16 — TTS, tiering & scene authoring

The task that finally connected `core/tier_resolver.py` and `core/frame_budget.py` to the graph --
both were built whole at T5/T6 and had never been called from anything -- and the task where D32's
suspicion about `FRAME_BUDGET` was replaced with a measurement that turned out worse than the
suspicion.

### D76 — Scene authoring is a second `Send` fan-out after a tiering join, not part of `synthesize_segment`
**Rejected:** folding scene authoring into `synthesize_segment`'s existing per-segment task (one
task doing TTS then slots), and a sequential join node looping over segments the way
`write_narration` does inside `plan_segments`.
**Reasoning:** the first was rejected on ordering and on cost. Tier assignment needs *every*
segment's measured duration, so it can only be a join after the fan-out converges -- which means
folding scene authoring into that same fan-out puts slots *before* tiers, inverting the order
`tasks.md` states ("assign tiers against real measured durations, then fill scene slots"). It also
puts a billed Speech synthesis and an LLM call in one node, so a whole-node retry of a failed scene
call re-synthesises audio that was already correct. The sequential join was rejected for latency
and blast radius: ~15 serial calls, and a transient failure retries the node, redoing every scene
already authored. The second fan-out reuses machinery T14 already proved durable and gets
per-segment resume for free -- verified, not assumed, by
`tests/test_graph_resume.py::test_a_kill_during_scene_authoring_does_not_repeat_narration`, which
confirms a kill inside the second fan-out re-authors exactly one segment and makes zero further
TTS calls.

### D77 — `frame_budget` and `fps` live on `GraphContext`, not on `GraphState`
**Rejected:** carrying them as state channels alongside `job` and `segments`.
**Reasoning:** `core/frame_budget.py`'s docstring already anticipated an edge-read: the budget and
the frame rate arrive as parameters precisely so neither it nor the resolver learns that
`FRAME_BUDGET` and `FPS` exist. Context is the edge. It is also re-supplied on every invocation,
where state is checkpointed -- so a resumed run picks up the current configuration rather than
being pinned to whatever the run first started with, which matters specifically because this is
tuning configuration someone changes *between* runs. `TierPlan` was likewise kept out of state:
`Segment.tier` is what downstream consumers need, and demotion detail exists for `/tiers` to
report, which builds its own plan directly.

### D78 — `FRAME_BUDGET` is 1400, and D32 understated the problem
**Measured, not decided.** D32 predicted that at 600 frames Tier 2 would buy *shortness* rather
than importance, because 600 frames at 24fps is 25s of animation against a 28s average segment.
Against real measured narration the answer was worse: **600 bought nothing at all.** A live run
(`scripts/tier_dry_run.py`, "teach me about SQL injection") produced 15 segments measured at a
uniform 19-29 seconds -- there are no short segments in real narration, because the scripting pack
narrates a title card at the same length as everything else. Spread at 600 was **T0=0 T1=15 T2=0**,
using 120 of 600 frames: every segment reveal-tiered, nothing animated, 480 frames unspent because
no single segment could afford the ~600-frame step up to Tier 2.

Measured curve at those real durations: 900 buys 1 animated scene, **1400 buys 2**, 2000 buys 3 --
each step roughly 600 frames apart, because that is what a 25-second animation costs. 1400 was
chosen as the smallest budget meeting D9's original "2-3 Tier-2 scenes" floor, at ~8-13 minutes of
rendering against D16's measured 1.7-2.7 frames/sec. 2000 was rejected: a third animated scene
costs another ~6 minutes of render for a seven-minute video.
**Rejected:** tuning against `tests/segment_examples.py`, which T5 wrote by hand and which contains
a 9-second title card and a 12-second stat callout. Those short segments are what made a 2/11/2
spread look achievable at 600. Real narration has no such segments, and T16's own task description
said not to tune against a fixture -- this is why.

### D79 — Tier 0 is a rendering floor, not a target, and the DoD's "all three tiers" is met for two
**Decided by the user, on measured evidence.** The DoD asks that "tier spread covers all three
tiers." At real durations no workable budget produces that. A reveal costs 8 frames, so any budget
large enough to animate anything is far more than enough to reveal *everything* -- Tier 0 and Tier
2 are effectively mutually exclusive at these durations. Tier 0 is reachable only when a segment's
*ideal* is `STATIC`, i.e. when the outline rates it `ASIDE`, and the model rated nothing `ASIDE` in
either live run.

**Rejected:** rebalancing `IDEAL_TIER` so `MINOR` maps to `STATIC`, which was measured to give
T0=2 T1=11 T2=2 deterministically and would have met the DoD as written. Rejected because Tier 0's
purpose, per `core/tier_resolver.py` and the `scene-templates` skill, is that *every* intent must
degrade to a single static frame since the budget can put any segment there -- it exists so a
segment always **can** render, not so that one **must**. An explainer whose budget is adequate
enough that nothing falls to Tier 0 is working, not broken. The DoD item is over-specified;
recorded as met for Tier 1 and Tier 2 rather than quietly claimed in full.
**Consequence for T17:** every template still needs its Tier 0 form. Tier 0 being empty on a
typical run makes it *less* likely to be exercised, not less necessary -- it is the degradation
path, and the resolver will use it the moment a budget is tight or a segment is rated `ASIDE`.

### D80 — An `outline` pack `1.1` was written, measured, and deleted rather than shipped
**Rejected:** shipping `runtime_skills/outline/1.1.md`, which rewrote the importance section after
the first live run showed the model rating 9 of 15 segments 4-5 and nothing 1 -- rating on merit
rather than the ranking the pack asks for.
**Reasoning:** it was written to make Tier 0 reachable by getting one segment rated `ASIDE`. It did
not: the second live run still produced no `ASIDE`, and the distribution barely moved (4/5/5/1/0 to
3/6/4/2/0 across CRITICAL..ASIDE), with 9 segments still wanting Tier 2 both times. Once D79
settled that Tier 0 is not a target, its motivation was gone and its measured effect was nil.
Shipping it would have left a future session believing the over-rating problem had been addressed.
Packs are immutable once versioned (D44/D46), so an unproven version is not free -- it is a file
every later run loads and every later reader has to account for.
**The finding it was chasing is real and is carried forward, unfixed:** the outline model rates on
merit rather than ranking, so most segments carry an "ideal" tier the budget can never honour. That
is a prompt problem for a future session with a hypothesis better than "ask harder", and it costs a
few cents per attempt to test with `scripts/tier_dry_run.py`.

### D81 — `/tiers` gets a script, and its own documentation was stale
**Discovered mid-task.** `.claude/commands/tiers.md` described a table column of "estimated
duration" and a cost of "one LLM call". Both predate T14 and T15: duration is measured, never
estimated (Invariant 1), and a real run is 1 + `segment_count` completions plus `segment_count`
syntheses. The command also had no implementation -- nothing in the repo could run a pipeline "as
far as tier assignment". `scripts/tier_dry_run.py` is that implementation, in `scripts/` rather
than `core/` because it names concrete adapters through `config.py` (D51's precedent).
**Caught by review, and worth recording as a class of bug:** the script's summary line divided
animated frame cost by a literal `24` rather than the run's configured `fps`, so the "seconds of
animation" figure -- the one number someone tuning `FRAME_BUDGET` actually reads -- would have been
overstated by 2.5x at `FPS=60`. A tuning tool that is silently wrong exactly when the knob it
reports on is changed is worse than no tool. `FRAME_BUDGET` and `FPS` are now read through a helper
that raises rather than defaulting, so those numbers live only in `.env`/`.env.example` and cannot
drift into a third copy.

### D82 — The three-pass review rhythm paid for itself again, in the same shape as D73
**Reconfirmed, not decided.** Pass one found nothing above trivial. Pass two -- a fresh full read,
not a re-verification -- found the `fps`/24 unit bug above, and correctly showed that a test
loosening made earlier in the session had become tautological (`load(name)` and `versions(name)`
resolve through the same private helper in `DiskSkillRegistry`, so asserting they agree asserts
nothing). Pass three confirmed both fixes and found nothing new. That is the fourth consecutive
task where the *second* independent pass, asked for a fresh full read rather than a check of named
fixes, is the one that found the real bug (D57, D62, D67, D73, now this).
**Also worth noting:** the tautological-test finding came from work done to accommodate the
`outline` `1.1` that D80 then deleted. Reverting `tests/test_runtime_skills.py` to its committed
state was the correct fix, and the episode is a small argument for making the speculative change
and the test change in separate steps, so that abandoning one does not leave the other stranded.

## 2026-08-24 · T17 — The three renderers

The first task to turn a filled slot payload into pixels. Planning had already produced a
minimal-but-correct plan (six bare-bones templates, matching `_reference_tier2.html`'s dark-navy
reference styling) before the user interrupted with two reference screenshots of what they
explicitly did not want -- a generic auto-diagram export: flat circles, crossing connector lines,
mid-word text truncation, zero motion -- and asked for something "production grade... cool, vibrant
and fun to watch." Everything below D83 is downstream of that redirect.

### D83 — Visual identity is "Data Drift" (`hyperframes-creative`'s named style), not the reference
tier-2 composition's cyan-on-navy
**Rejected:** extending `_reference_tier2.html`'s existing dark-navy/cyan palette as-is (the
default a minimal-scope plan would have produced), and three other named styles offered to the
user (Swiss Pulse refined, Deconstructed, a custom style).
**Reasoning:** user's explicit choice, from a set curated for this project's actual content
(tech/security/ML explainers) after loading `hyperframes-creative`/`hyperframes-animation`. Worth
recording because the reference template's cyan-on-dark-navy scheme is *exactly* what
`house-style.md` names as a lazy AI default ("Cyan-on-dark / purple-to-blue gradients") -- a
literal reuse of it would have shipped the very thing the user was pointing at in the screenshots.
Concrete system: `--bg:#0b0a14`, accents `--accent-purple:#7c3aed`/`--accent-cyan:#06b6d4` (a
lighter `--accent-purple-text:#b794f6` for small text -- see D89.5), **Montserrat** (statement
voice, 400/900 only -- the family's real bundled weights) + **JetBrains Mono** (data/technical
voice: stat values, code, labels), a shared background layer (two radial glows, a 24-particle
field, one accent rule) reused identically across all six templates. Declared in one Jinja partial,
`rendering/templates/_tokens.html`, imported by every template rather than copy-pasted six times.
**DIAGRAM_FLOW specifically fixes the screenshot's crossing-lines failure**, structurally: nodes
sit on one straight rail in array order, never a free-floating graph layout, so two connectors can
never cross by construction.

### D84 — `mux/frames_to_clip.py` is populated in T17, ahead of T18
**Rejected:** putting Tier 0/1's stills-to-video ffmpeg calls inside `rendering/` itself, deferring
`mux/` entirely to T18 as `tasks.md`'s own title ("Mux & CLI") might suggest.
**Reasoning:** CLAUDE.md's layout table is a project-wide, task-independent rule -- "ffmpeg
subprocess calls" live in `mux/`, full stop -- not a T18-scoped one. Tier 0 (hold one screenshot)
and Tier 1 (crossfade several) both need ffmpeg to become a clip at all, so honouring the rule
means starting `mux/` here. T18's own scope (audio mux + concat) is unaffected and unblocked.

### D85 — Every composition is the sole file `dest_dir/index.html`, closing D60's open item
**Verified, not chosen freely.** `adapters/local/hyperframes_cli.py::lint` (D60) already hard-requires
this -- literal filename `index.html`, alone in its directory -- so `rendering/compose.py` simply
enforces it by construction (always writes `dest_dir / "index.html"`) rather than trusting a future
caller to know the constraint exists. T17's functions take an explicit `dest_dir`/`dest` from the
caller and invent no job/segment path convention of their own; that belongs to whichever task first
wires rendering into the graph (T18), the same way `SEGMENT_AUDIO_KEY` belongs to `synthesize.py`.

### D86 — No new error family for "our own code judged this invalid" beyond `CompositionInvalid`
**Rejected:** a new exception class, which `handoff.md` and D23 both left as an open question for
T17 to decide.
**Reasoning:** `CompositionInvalid` (D23) already means exactly "our code decided a lint finding
was fatal" -- the composition-level gate `render_segment.py` raises before all three tiers. Slot-
*payload*-level invalidity is a separate concern, closed by `rendering/compose.py` validating
`segment.slots` back through `slot_schema_for` (D29's "point of use") and letting pydantic's own
`ValidationError` propagate -- consistent with how `Segment`/`VideoJob` validation already works
elsewhere in this codebase, never translated to an `AdapterError` since nothing outside the process
is at fault. Two failure points, two pre-existing exception types.

### D87 — `TIER_SUPPORT`'s no-op `ALL_TIERS` map is confirmed correct, not edited, closing D36
**Verified, not decided.** D36 left `core/tier_resolver.py::TIER_SUPPORT` as a no-op registration
point specifically for T17 -- "the first code in a position to know" whether any intent lacks a
meaningful reveal or static form. What T17 found: every template is one seekable GSAP timeline
(D15); Tier 0 and Tier 1 differ from Tier 2 only in *how many times and when* that timeline is
seeked and screenshotted, never in the markup. Every intent genuinely supports all three tiers, so
the map is correct as it stood. `core/tier_resolver.py` is untouched -- its 198/200-line headroom
is not spent here, and the next intent still forces a split when it comes.

### D88 — `render_segment`'s lint gate treats any finding as fatal, applied before all three tiers
**Rejected:** parsing `severity` out of `RenderBackend.lint`'s formatted finding strings and only
failing on `"error"`; also rejected gating only before Tier 2 (the expensive path) and letting
Tier 0/1 screenshot a composition lint never approved.
**Reasoning:** simpler than severity-parsing, and consistent with this project's "catch it at
write time, no repair loop" stance (D2, scene-templates skill) -- lint is cheap, and a broken
composition is equally wrong screenshotted as rendered. `npx hyperframes check`'s own layout/
contrast/motion audits stay *outside* this gate deliberately (see D89) -- stricter and slower than
what should block an ordinary job, so that extra scrutiny lives in template-authoring's own test
suite (`tests/test_render_segment_live.py`) rather than the render path itself.

### D89 — Five real bugs found only by the live toolchain, none catchable by the offline suite alone
**Discovered, not decided.** Every template passed its own authoring review and the offline test
suite before any of these surfaced -- all five needed a real `npx hyperframes check` or a real
Playwright seek to show up, which is why `handoff.md`'s "render every template at all three tiers
explicitly" instruction (D79) mattered more than it looked like it would.

1. **Unsized composition root.** `_tokens.html`'s `#root` never got explicit `width`/`height` --
   exactly `hyperframes-core`'s documented "silent layout bug" (every child is `position:absolute`,
   so the root collapses toward 0 and everything piles into the top-left, with no lint error).
   Confirmed via Playwright: `#root`'s rendered height was `0`. Fixed with explicit
   `width:1920px; height:1080px;`.
2. **Manual `onUpdate` DOM writes are invisible under this renderer's seek convention.** The
   particle field's ambient drift was written as a phase-driven `onUpdate` proxy (`sine-wave-loop`
   `.md`'s own documented "onUpdate form"). HyperFrames seeks with `suppressEvents=true` -- this
   project's own `_SEEK = "...seek(id, t, true)"` convention (D15), used both by
   `playwright_capture.py` and, evidently, by `hyperframes check`'s own driver -- and GSAP's
   `suppressEvents` explicitly skips `onUpdate`/`onStart`/`onComplete` callbacks while still
   applying a *tracked property's* own interpolated value. Verified empirically: a probed
   particle's `style.transform` stayed the empty string across every seek, while a sibling
   `opacity` tween (a real tracked property, not a manual write) updated correctly. **Rule for any
   future ambient motion in this project's templates: use genuine GSAP property tweens
   (`fromTo`/`to` on `x`/`y`/`scale`/`opacity`/etc.), never a manual `onUpdate` DOM write** --
   `sine-wave-loop.md`'s onUpdate form does not render under this project's capture/check pipeline,
   only its own preview tooling.
3. **`hyperframes check`'s frozen-sweep guard (`sweep_static`) treats opacity below 0.2 as
   invisible.** `isVisibleElement`'s default opacity floor, read from the installed CLI's own
   source (`layout-audit.browser.js`), excludes anything with a computed opacity chain under 0.2
   from its per-sample geometry fingerprint -- regardless of how much it is actually moving. The
   particle field's resting opacity (0.16, chosen for subtlety) sat just below that floor, so its
   drift never registered even after fix #2. Raised to 0.22, still inside `video-composition.md`'s
   12-25% decorative-opacity range.
4. **SVG `stroke-dasharray`/`stroke-dashoffset` animation never changes an element's own
   `getBoundingClientRect()`.** `diagram_flow.html`'s rail-segment draw (`svg-path-draw.md`) is
   real and correct, but is *structurally invisible* to any bbox-based liveness/motion check --
   the geometric endpoints of a `<line>` never move, only its rendered dash pattern does. This is
   why `diagram_flow` alone still tripped `sweep_static` after fixes #1-#3: it was the one template
   whose only non-background motion was an SVG stroke draw, invisible by construction, plus an
   entrance that fully settles before the check's first layout sample. No template code change was
   needed once the shared particle field (fix #3) gave every template genuine, checker-visible
   ambient motion throughout the full duration.
5. **libx264 refuses odd, and *zero*, width/height.** `mux/frames_to_clip.py`'s even-dimensions
   filter initially used `trunc(iw/2)*2`, which rounds a 1px source (the offline test fixture's
   `FakeRenderBackend` still writes a 1x1 PNG) down to 0 -- also refused. Switched to
   `2*ceil(iw/2):2*ceil(ih/2)`, which rounds up instead and is a no-op for any already-even real
   capture (1920x1080).

**A sixth, related bug came from `project-reviewer`'s fresh pass, not the live toolchain directly,
and is worth recording alongside these because it is the same class of mistake as #2/#3 in a new
place:** `comparison.html`'s counter-phase idle card bob used a hardcoded `repeat: 1`
(`duration:1.3`), covering only 2.6s starting at 1.8s -- both cards froze for the remainder of any
segment longer than 4.4s, which is essentially every real segment. The particle field had already
been made duration-aware (computing `repeat` from `duration_sec`, per fix #2/#3's fallout) but that
fix was never generalised to this second, template-local ambient tween.
`tests/test_render_segment_live.py`'s own fixture duration (4000ms, chosen short deliberately to
keep an 18-case real-render matrix tractable) happened to end *inside* the bob's original active
window, so the test suite passed for the wrong reason and never exercised the tail of a realistic
segment. Fixed the same way the particle field was: `repeat` computed from `duration_sec` via
`ceil` plus a margin. Verified directly with `npx hyperframes check` at a realistic 21s duration
(clean), not just the short test fixture.

**Also fixed along the way, infrastructure rather than a template bug:** `scripts/hook_asset_quality.py`
(T2-era) called `npx hyperframes lint <single-file>` on every `.html` write under
`rendering/templates/` -- broken twice over, independently of anything in this task: the CLI only
ever lints a whole project *directory* (D60, discovered after this hook was written), and a Jinja
source template (`{{ }}`/`{% %}`) is not valid standalone HTML in the first place. Fixed narrowly:
skip linting a `.html` file that contains Jinja delimiters, leaving `_reference_tier2.html` (a
literal, Jinja-free composition) linted exactly as before.

### D90 — Checkpoint's own git state must be read from `git log`/`git remote -v`, never carried
forward from the previous handoff
**Discovered, not decided,** during this checkpoint rather than the build itself. T16's handoff
claimed "T15 and T16 are uncommitted"; that was already false by the time this session started --
`6b52ec2` (visible in plain `git log`) already contained both. A second, independent staleness in
the same section: the same handoff claimed no git remote was configured, when `origin` -> GitHub
already existed and `origin/master` already matched local history through `6b52ec2`. Both claims
were carried forward, unverified, into this session's own first handoff draft before being caught
by actually running `git log`/`git remote -v`/`git status -sb` rather than trusting the prior
file's prose.
**Reasoning this is worth a decision entry rather than just a fix:** the Git row in handoff.md's
environment table is exactly the kind of fact that goes stale silently -- nothing in the normal
build loop re-verifies it, since `/checkpoint` writes it once and the next session reads it as
ground truth. Two wrong claims in a row in the same three-line table is a pattern, not a fluke.
**Rule going forward: `/checkpoint`'s Git row is always written from a fresh `git log --oneline`
and `git remote -v` in the same session, never copied from the previous handoff and edited.**

## 2026-08-26 · T18 — Mux & CLI

The task that produced the first complete, playable video -- and then, once a real person actually
watched and listened to it, the session that found how much "the offline suite is green" still
doesn't tell you. Two real videos got made; the second exists specifically because the first one's
problems could only be found by looking and listening, not by any test.

### D91 — `render_scene`/`finalize` extend the graph with a third `Send` fan-out, chosen over a CLI-side loop
**Rejected:** driving `render_segment`/mux/concat from `cli.py` directly, outside the graph, once
each segment's synthesize/tier/author steps complete -- the shape `handoff.md`'s own T17 close-out
leaned toward as "most likely."
**Reasoning:** raised as an explicit fork and decided by the user. Extending the graph means a
killed run resumes without re-rendering already-finished segments -- T14/D68's guarantee, now
covering the one stage that actually costs real wall-clock minutes (D78's animated-tier render
time), where the CLI-side alternative would have to redo it from nothing on every crash.
`collect_scenes` (`core/graph/pipeline.py`) is a deliberately empty join node between the second and
third fan-outs, existing only because LangGraph needs a named node to converge a superstep before
fanning out again -- the same structural reason `assign_tiers` sits between the first two.

### D92 — `RUNTIME_ENV=azure` cannot drive a render end to end yet; T18's DoD was met by hand-mixing adapters, not by `cli.py` alone
**Discovered while running T18's own DoD command, not assumed.** `python cli.py "<topic>"` under
`RUNTIME_ENV=azure` reaches `render_scene` and immediately raises `NotImplementedError` from
`ContainerAppsRenderBackend.lint` -- `config.py`'s azure branch for `RenderBackend`, unchanged since
T12/D25, is still exactly the stub it always was; real implementation doesn't land until T35.
`RUNTIME_ENV=local` cannot substitute either, since its `LLMProvider`/`TTSProvider` still don't
exist (D58/D59/D64). **No single `RUNTIME_ENV` value can currently produce a real video** -- a gap
that predates this task and stayed invisible until an actual end-to-end render was attempted.
**Rejected:** waiting for T35 before calling T18 done, and separately, quietly changing `config.py`
so `RUNTIME_ENV=azure` silently resolves local rendering -- which would make "azure" a lie about
what actually runs.
**Reasoning:** the real videos this task's DoD asks for were produced by resolving Azure's
`LLMProvider`/`TTSProvider`/`Storage`/`SkillRegistry` and the *local* `RenderBackend` by hand,
calling `config.py`'s own per-interface builder functions directly against two different `env`
mappings rather than through `build_adapters()`'s single-stack resolution -- a one-off, explicitly
not committed as a new code path, since silently mixing stacks would defeat `config.py`'s whole
reason for existing. T18A's local entrypoint is where this mixing becomes real, labeled, permanent
code instead of a manual step; T35 is what closes the gap for good.

### D93 — Real crossfade transitions between segments, not a hard cut -- and the audio design mistake it produced
**Rejected (the version that shipped, then was found wrong by actually listening to it):**
`mux/concat_segments.py` chaining `xfade` (video) and `acrossfade` (audio) together at the same
`transition_s`, on the reasoning that a smooth visual dissolve needed a matching audio treatment.
**Reasoning for the original change:** the second real video's biggest complaint was reading as "15
independent slides," and the previous stream-copy concat (D3/D18-era, `-c copy`, zero transition)
was a real contributor on top of every segment being composed independently regardless. The
`xfade`/`acrossfade` chain fixed the hard-cut symptom and is verified correct on its own terms --
offset/cumulative-duration math checked by hand and independently by `project-reviewer`, both
against real mixed-tier renders (a Tier 0/1 clip and a Tier 2 clip in the same chain, the specific
risk flagged when this was built).
**What was wrong with it, found only by listening:** `acrossfade` blends the *tail of one segment's
narration with the head of the next* for the full transition window -- two different sentences
audibly overlapping, which reads exactly like the narrator interrupting themselves. Every duration
and sync assertion passed throughout, because they only ever checked timing, never content -- the
same class of lesson D89 already drew about rendering bugs (only a real render, or here a real
listen, catches it), arriving in a new medium.
**Deferred to T18A, not fixed here.** The correct fix is designed, not yet built: pad each non-last
clip's *video* stream with a held last frame (`tpad`) so `xfade` consumes only that padding, never
real narrated time, while audio becomes a plain, unshrunk `concat` with no blending at all --
landing both streams at exactly `sum(durations_ms)`, and eliminating every bit of speech overlap.
Recorded here so `mux/concat_segments.py`'s current `acrossfade` is understood as a known,
accepted-for-now defect rather than a silent one.

### D94 — `diagram_flow`'s node markers are too transparent to hide the rail line behind them
**Discovered by the user, from the actual rendered video** -- not caught by any test or review pass
in this task. `.df-node-marker`'s fill (`rgba(79, 168, 255, 0.1)`, 10% opacity) doesn't occlude the
SVG rail line drawn at the same position, so the connecting line visibly cuts through every node
circle instead of appearing to pass behind it.
**Deferred to T18A, not fixed here.** Recorded rather than left implicit because the fix is narrow
and easy to lose track of otherwise: an opaque (or near-opaque) marker background, e.g. `var(--bg)`,
occludes the line regardless of the exact stacking cause -- worth confirming empirically what that
cause actually was, not just patching the symptom, when T18A picks this up.

### D95 — The redesigned visual identity replaces glow/gradient with two flat colors used for meaning, not mood -- and quietly fixes a font that was never actually loading
**Rejected:** the "Data Drift" identity D83 chose at T17 (near-black + blurred purple/cyan glow
blobs + a particle field), after the second real video's own screenshots showed it still reading as
generic "AI dark-mode" despite D83's stated intent to avoid exactly that. A named cliché is a
specific instance, not the whole territory it warns about.
**Reasoning:** `--accent-primary` (`#ffb703`, flat amber) marks emphasis; `--accent-secondary`
(`#4fa8ff`, flat blue) marks structure/data -- no gradients, no blur, anywhere.
**Found in passing while doing this:** no template ever linked a Google Fonts stylesheet, so
"Montserrat"/"JetBrains Mono" in the CSS had been silently falling back to system fonts (Segoe UI)
since T17 shipped -- decisionlog and handoff both described a typographic identity that was never
actually rendering. Fixed alongside the palette change (a real `<link>`, IBM Plex Sans replacing
Montserrat as the display face) rather than left to compound further.
**The particle field's replacement -- a single breathing hairline frame -- initially shipped with
its opacity range (0.14-0.2) sitting at or below D89.3's documented 0.2 floor** for
`hyperframes check`'s frozen-sweep guard, found by `project-reviewer`'s checkpoint pass reasoning
from that exact prior lesson before any render proved it either way. Fixed to 0.22-0.32, comfortably
clear of the floor at every point in the cycle, matching the particle field's own proven-safe 0.22
baseline exactly.
**Still open, from the same content:** the user's own read after the fix landed -- "still reads navy
blue" -- is a fair miss on its own terms. This specific video's content mix (8 of 15 segments were
`diagram_flow`, which leans almost entirely on the blue token) made blue dominant regardless of the
palette itself having changed. Not resolved here; carried into T18A's discussion of a richer diagram
intent that can lean amber instead.

### D96 — `hyperframes check` is non-deterministically flaky at the CLI version currently resolved (0.8.15), independent of anything in this diff
**Discovered while re-verifying D95's opacity fix, not assumed.** Running `npx hyperframes check
--json` repeatedly against the *same, unchanged* composition directory produced `ok: false` (a
`sweep_static` finding claiming `[data-composition-id]` "did not advance under seek," with an
all-zero bounding box) on some runs and `ok: true` on others -- 2 of 5 runs failed, no code change
between them. The CLI has drifted again (0.8.10 at T16 -> 0.8.12 at T17 -> 0.8.15 now), each time
with no project-level pin (still no `package.json` at the repo root).
**Not fixed here -- cannot be, from this codebase.** Recorded as a real, current gap: any future
session leaning on `hyperframes check` as a hard gate should expect occasional false failures at
this CLI version and re-run before treating one red result as real, or investigate pinning the CLI
to something known-stable.

### D97 — Resume durability across the render/finalize fan-out is unverified, and narrower than the graph's earlier stages
**Found by `project-reviewer`'s checkpoint pass, not fixed here.** `render_scene`/`finalize` both
reconstruct local-disk paths (`local_narration_path`, `local_clip_path`) for files an *earlier*
superstep wrote, with no fallback to `Storage` if that file is gone -- new territory, since no node
before this task ever needed to re-read another node's on-disk output across a potential resume
boundary. `tests/test_graph_resume.py` covers a kill/resume across the first two fan-outs only;
there is no case covering one that crosses `render_scene` or `finalize`.
**Accepted, not solved, here.** For the CLI's own single-machine, job-id-keyed `working_dir` this is
unlikely to bite in practice, but it is a real, untested narrowing of what "resume" guarantees in a
codebase that has otherwise treated resume-durability as verified (D68) rather than assumed.
Whichever future task next touches resume (T18A's local entrypoint, or T35's cloud render backend,
where `working_dir` surviving between processes is a real question) should close this for real
rather than continue inheriting the assumption.

### D98 — T18A, not a renumbered T19-T35, for the follow-on work the second real video surfaced
**Rejected:** cascading every task from old-T19 onward up by one to make room for the new work as a
clean "T19" -- fully drafted (`tasks.md`, plus every in-code comment/docstring/test referencing
T19-T35) before the user reconsidered mid-edit and asked for a lettered insertion instead.
**Reasoning:** user's explicit call. A renumber touches far more than `tasks.md` --
`tests/test_adapter_stubs.py` asserts on the literal string "T34"/"T35" inside exception messages
the Azure stubs raise, and half a dozen other files carry the same numbers in docstrings/comments
(`config.py`, `core/models.py`, `adapters/local|azure/*`, more) -- all reverted back to original
once the direction changed. `T18A` sits between T18 and the untouched original T19, with its own
"task numbers are identity, not order" note in `tasks.md` (the same device already used for
T34/T35's Iteration 5.5 insertion) -- zero blast radius on anything already numbered, at the cost of
one non-sequential label.

### D99 — T18A: D16's frame budget was wrong by at least 6x, measured and corrected
**The trigger.** A real viewer's verdict on T18's two videos ("looks like a slideshow") traced to a
measurable cause: `FRAME_BUDGET=1400` (D78) bought Tier 2 for only 2 of 15 segments, because D16's
underlying throughput figure -- 1.7-2.7 frames/sec -- was itself wrong. That figure came from a
90-frame (3-second) sample, dominated by browser cold start and (at the time) unpinned `npx`
resolution overhead, not by steady-state rendering.

**Contradicted by this project's own evidence before it was re-measured.**
`adapters/local/render_backend.py` applied a flat 60s timeout to full Tier-2 renders, and
~600-frame (25s) segments completed inside it -- 600 frames in under 60s is already >=10
frames/sec, more than 3x D16's ceiling.

**Measured for real:** `npx hyperframes benchmark` (the CLI's own tool, not a hand-rolled timer) on
one realistic 25-second composed segment, `--workers 4`, `standard` quality:
30fps/750 frames -> 44.7s avg (~16.8 fps); 60fps/1500 frames -> 86.4s avg (~17.4 fps). Both land
around **~17 frames/sec**, roughly **6-10x** D16's figure. `scripts/measure_render_throughput.py`
reproduces this.

**Consequence, in two parts:**
1. `core/tier_resolver.py::IDEAL_TIER` raised NORMAL and MINOR from `Tier.REVEAL` to
   `Tier.ANIMATED` -- only `ASIDE` still settles for a reveal. The old ladder was tuned around a
   budget too small to ever fund more than a couple of segments; correcting the budget without
   raising the ladder would have left most segments still capped below their real ceiling.
2. `.env`/`.env.example`'s `FRAME_BUDGET` raised from 1400 to **9500** -- enough for the corrected
   ladder to fund Tier 2 on every non-ASIDE segment of a 7-minute/15-segment video (~9000 frames
   for full coverage, confirmed against `tests/segment_examples.py::seven_minute_segments`), while
   staying inside a ~9-minute render at the measured rate -- comfortably under the ~15-minute
   wall-clock target even allowing for contention.

**Also changed:** `RENDER_MAX_CONCURRENCY` dropped 4 -> 2, and a new `RENDER_WORKERS=auto` was
added. Reasoning is memory, not CPU: `hyperframes doctor` reports 16 cores but as little as ~2.4GB
free RAM on the build machine, and each render worker is its own Chrome process (~256MB). Running
several segments concurrently *and* several workers per segment risked OOM thrash long before CPU
became the bottleneck -- `--workers auto` already accounts for low-memory mode, so it was left to
calibrate rather than pinned to a number chosen without a memory-constrained measurement.

**Not touched:** `STATIC_FRAME_COST`, `REVEAL_FRAME_COST`, `frame_cost`, and the two-pass greedy
promotion in `resolve_tiers` -- the mechanism was never the problem, only its inputs were.
`tests/test_tier_resolver.py`'s two budget-shape tests were re-pinned to the new ladder's actual
numbers rather than adjusted to preserve the old assertions; a third test
(`test_a_generous_budget_animates_nearly_every_segment`) was added as a regression guard against
`FRAME_BUDGET` quietly shrinking back toward D16's original, wrong figure.

### D100 — `config.py`'s render-backend resolution moved to `config_render.py`, and `RENDER_ENV` closes D92 for real
**The trigger.** T18A needed `RenderBackend` resolution to grow: a `RENDER_ENV` bridge (below),
explicit `--workers` wiring, and an integer-or-`"auto"` `RENDER_WORKERS` parse. Adding that in
place pushed `config.py` over the 200-line ceiling.

**The split.** `config_render.py` (new, top level, sibling to `config.py`) now holds
`render_env()` and `resolve()`, and is the only other module importing
`PlaywrightHyperFramesRenderBackend`/`ContainerAppsRenderBackend`. CLAUDE.md's "config.py is the
only module naming concrete adapter classes" is about there being **one resolution seam**, not
literally one file on disk -- `config.py` still owns calling this, still owns every other
interface's resolution, and `config_render.py` has no other caller and no reason to exist outside
this seam. Precedent: `core/frame_budget.py` was already split out of `core/tier_resolver.py` on
the same "split by responsibility, not by compressing" principle CLAUDE.md states directly.

**`RENDER_ENV`, the actual fix D92 asked for.** D92 recorded that `RUNTIME_ENV=azure` cannot drive
a render end to end (`ContainerAppsRenderBackend` is still T35's stub), and that T18's DoD was met
only by hand-mixing real Azure LLM/TTS with the real local render backend outside of any committed
code path. `config_render.render_env(env)` reads a new `RENDER_ENV` variable, falling back to
`RUNTIME_ENV` when unset -- so nothing changes for any caller that has never heard of it -- and
`resolve()` checks that instead of `RUNTIME_ENV` directly. Setting `RENDER_ENV=local` alongside
`RUNTIME_ENV=azure` (now the default in `.env`/`.env.example`) is the hand-mixing from T18's
session, made real, labeled, and tested (`tests/test_config.py::
test_render_env_bridges_azure_llm_to_the_real_local_render_backend`).

**Explicitly temporary.** `RENDER_ENV` exists only until T35 makes `ContainerAppsRenderBackend`
real -- at that point `RUNTIME_ENV=azure` alone will resolve a working render backend and
`RENDER_ENV` becomes unnecessary. It is not meant to grow a third value or become a permanent
second stack switch; both `.env.example`'s comment and `config_render.py`'s docstring say so.

### D101 — Word-level TTS timing lives in `interfaces/tts_provider.py`, not `core/models.py`
**The trigger.** T18A needed a `WordMark`/`SynthesisResult` pair to carry Azure Speech's
word-boundary events through the pipeline. The plan drafted them as `core/models.py` domain
models; building them there would have made `core/` import nothing new, which looked right until
checking precedent.

**Rejected:** `core/models.py`. `core/__init__.py`'s own docstring already draws this line:
*"The contracts' own vocabulary -- `SkillPack`, `QueuedJob` -- stays in `interfaces/` and is not
duplicated here; `Segment`, `VisualIntent`, `Tier` and `VideoJob` are domain concepts and appear
in no interface signature."* `WordMark`/`SynthesisResult` are exactly the first kind: they exist
because `TTSProvider.synthesize`'s return shape needs a name, the same reason `SkillPack` exists
because `SkillRegistry.load`'s return shape needs one.

**Landed:** both classes defined in `interfaces/tts_provider.py`, re-exported from
`core/synthesis.py` (`from interfaces.tts_provider import SynthesisResult, WordMark`) purely so
`core/models.py::Segment.word_marks` and anything importing `core` can reach `WordMark` without
naming `interfaces` directly at every call site -- the same convenience `core/__init__.py`
already provides for pieces of `core/frame_budget.py`, `core/tier_resolver.py`, etc. D22's
boundary (`core` imports `interfaces`, never the reverse) is unaffected either way.

### D102 — `render_segment.py`'s lint gate now distinguishes `[error]` from `[warning]`/`[info]`
**Found live, not by a test.** The first real end-to-end run since T18A's template changes
(captions macro, palette tokens) failed at `render_segment`: `hyperframes lint` returned exactly
one finding, `[warning] composition_file_too_large: This HTML composition file has 315 lines`,
and D2's original "any finding is fatal" stance (unmodified since T17) blocked the render
outright.

**Rejected:** shrinking the templates to duck under whatever line count triggers the warning.
That treats a stylistic nag as a hard ceiling on how much a composition is allowed to do, which
is exactly backwards from this task's goal of putting more into each scene, not less.

**Landed:** `render_segment.py` now raises `CompositionInvalid` only on findings that are not
`[warning]`/`[info]` severity. This mirrors a distinction `hyperframes check` itself already
draws (`--strict` fails on errors only, the default; `--strict-all` also fails on warnings) --
D2's "catch it at write time" stance is preserved for what it was actually protecting against
(a composition the renderer cannot correctly play), not for a code-style opinion about file
length. Verified against a real render immediately after: the same job that failed on the
warning proceeded to a real 3-segment video, all Tier 2, once the fix landed.

### D103 — Palettes, captions, count-up, GSAP vendoring, and the two carried-forward bugs, verified against the real toolchain, not asserted
**What shipped, briefly** (fuller detail lives in the T18A build's own commit and in D99-D102
above; this entry is the roundup for anyone scanning history):
- `rendering/palettes.py` -- six hand-picked, contrast-checked palettes, selected deterministically
  per `job_id`. Verified with real numbers: WCAG contrast ratios computed for all six (4.5:1 AA
  floor; every value landed well above 5.8:1) and, separately, `hyperframes check --contrast` run
  against real composed scenes under six different `job_id`s all reported `passed == checked`.
- `rendering/templates/_captions.html` -- word-timed in-frame captions, degrading to an even
  stagger when `word_marks` is empty; `mux/subtitles.py` -- the SRT sidecar, offsets trivial by
  construction because D93's audio fix (below) leaves the audio track unshrunk.
- `core/slot_schemas.py::StatCalloutSlots.value_number/prefix/suffix` -- a real count-up for
  `stat_callout`, ported from the registry's own `count-up` component's deterministic frame-row
  technique (`npx hyperframes add count-up --json`, inspected, then hand-adapted into this
  project's Jinja/GSAP conventions rather than cloned wholesale, since the registry's `<template>`
  clone mechanism assumes a `window.__hyperframes` runtime this project's compositions don't load).
  `hyperframes check` caught a genuine overlapping-tween bug in the first version (the entrance
  scale tween ran past the count's own landing time); fixed by making the value's scale timeline
  strictly sequential. Snapshot-verified: 0 -> 123,784 -> 187,200 -> 199,916 -> 200,000 across five
  timestamps in a single second.
- **D93 (narration crossfade) fixed for real**, not just redesigned: `mux/concat_segments.py`
  pads each non-last clip's video tail via `tpad` so `xfade` consumes only that padding, and
  audio is now a plain unshrunk `concat` with zero blending. Verified two ways: a duration-based
  regression test (`tests/test_concat_segments.py`, both tracks now land at exactly
  `sum(durations_ms)`, not the old shrunk figure), and a real spectral check -- two clips with
  distinct sine tones (440Hz/880Hz) concatenated, then FFT-analyzed in a sliding 20ms window
  across the join: energy at the "wrong" frequency drops to near-zero within about 40ms of the
  cut, versus the ~500ms blend the old `acrossfade` produced. Also varies the video transition
  style across a 5-way cycle instead of always `fade`.
- **D94 (diagram_flow marker opacity) fixed**: the node marker's `background` was a hardcoded
  `rgba(79, 168, 255, 0.1)` -- both under-opaque (D94's original finding) and stale (predates
  per-job palettes). Now `var(--bg)`, fully opaque and palette-correct. Confirmed visually in the
  same real end-to-end render: markers render as solid discs, no rail line visible through them.
- GSAP vendored locally (`rendering/templates/vendor/gsap.min.js`, copied alongside every
  composition's `index.html` by `rendering/compose.py`) instead of loaded from jsDelivr on every
  render. Confirmed a sibling file does not violate D60's lint constraint by testing directly
  against `hyperframes check` before relying on it -- D60's actual requirement is the entry
  file's name and location, not the directory being literally empty otherwise.

**All of the above verified together** in one real end-to-end run: `RUNTIME_ENV=azure` +
`RENDER_ENV=local` (D100), topic "how binary search works", 90-second target. Three segments, all
three landed on `Tier.ANIMATED` (the corrected budget/ladder from D99 funding what D78's original
1400 could not), real `final.srt` produced from real Azure word-boundary events, 165.9s
wall-clock -- comfortably inside the ~15-minute target with two full segments' worth of margin
to spare on a video less than a third that length.

### D104 — T18B scoped to a richer fixed template set, not fully compositional LLM-authored scenes; Mermaid rejected for the diagrams it was proposed for
**The trigger.** Reviewing T18A's real output, the user pushed back hard on three things: motion
that's really just an idle bob after a 1.5s entrance, captions that accumulate into a wall of text
instead of clearing, and `diagram_flow` looking identical to the pre-T18A reference screenshot no
matter the topic. They also shared a reference video (a 2:20 binary-search explainer) showing
patterns this project has no template for -- an array/list visualization (boxes crossed out as the
search space halves) and a composite code+diagram split panel -- and asked directly whether the
project needs to stop using predefined templates at all, "each video topic will have a different
requirement."

**Rejected: Mermaid for the diagrams in the reference video.** The reference video's specific
asks (array-slicing, a code+diagram split) are not graph/flowchart content Mermaid renders --
they're a data-structure visualization and a layout composition, neither of which Mermaid's own
diagram types cover. Even where Mermaid could apply (arbitrary graph topology), it only produces
a static SVG; HyperFrames' whole rendering model is a paused, seekable GSAP timeline (D15), so
Mermaid output would need the identical stroke-draw animation technique `diagram_flow` already
uses, bought at the cost of a new Node-side render step and a determinism question (must lay out
identically for the same input every time, since frame-accurate seeking depends on it). Not ruled
out forever -- flagged as a real option for a future task if genuinely arbitrary graph topology
becomes a concrete need, just not for what T18B's reference video actually shows.

**Rejected (for T18B specifically, not permanently): fully compositional LLM-authored scenes** --
the LLM assembling a segment's visual from primitives per topic instead of picking from a fixed
template set. This is exactly what T18A's own plan (and the original T18A task description before
it) already named and deliberately scoped out as "a much larger, research-shaped undertaking."
Reopening it now would mean shipping it alongside everything else already on T18B's list under the
"one solid pass, ship it" iteration budget the user picked -- LLM-authored layouts need real
validation cycles (more `hyperframes check` failures, more render-watch-adjust loops) that budget
doesn't have room for. The user's own stated concern ("each video topic will have a different
requirement") is real, but is addressed for now by growing the *set* of fixed templates to match
the concrete patterns their reference video showed, not by removing the fixed-template model.

**Landed: T18B's scope is a richer, better-curated fixed template set.** New intents (array/list
visualization; a composite code+diagram split); shared, reusable annotation components (a
pointing-hand/cursor indicator, a success-check) usable by any template rather than baked into
one; a guaranteed title card (the outline pack currently only *suggests* one segment be
`title_card` -- nothing enforces it, which is why the real T18A test run had none); cue-based
captions replacing the accumulate-forever bug; full-duration per-template motion instead of an
idle-bob liveness hack; and a per-video "motif" system (three starting directions: Blueprint,
Terminal, Broadcast) that varies palette *and* which template variant renders each intent, so
repeats within one video and across different videos both look genuinely different. Full detail
in the planning conversation preceding this checkpoint; `tasks.md`'s T18B entry carries the
scoped list forward.

**If this still isn't enough after a real 7-minute video under T18B**, the fully-compositional
approach becomes its own later task with its own scoping conversation -- not folded into T18B.

## 2026-08-29 · T18B — Compositional scenes, whole-video visual planning, narration-anchored motion

The user reopened D104 explicitly, after reviewing T18A's real output a second time: forget the
frame-budget/architecture assumptions that shaped prior scoping, keep only the ~15-20 minute
render ceiling, and build toward genuinely bespoke, per-topic segments. This entry records what
actually shipped, what it cost to get there, and what stays open.

### D105 — D104 reopened; D30 deliberately left alone; the fan-out isolation, not template
variety, was the real cause of repetition

**Reopened:** D104 ("richer fixed template set, not fully compositional"), on the user's explicit
instruction. **Deliberately NOT reopened:** D30 (six `VisualIntent` members) -- the enum survives
unchanged as a coarse outline-time hint, not a rendering key. `VisualIntent` was never the
problem; `rendering/compose.py:66`'s one-intent-one-template *dispatch* was.

**The diagnosis that changed the plan mid-session:** reading `core/graph/pipeline.py` directly
(not assumed) showed `author_scene` running inside a `Send` fan-out -- every segment's visual was
authored in total isolation from every other. That is the actual, structural cause of D95's "8 of
15 segments were `diagram_flow`," not a template-quality problem no amount of new templates would
have fixed. The fix is a new join node, `plan_visuals`, inserted between `assign_tiers` and the
`author_scene` fan-out, that sees every segment at once and plans the whole video's visuals in one
call -- the first thing in this pipeline positioned to notice and prevent repetition, rather than
only ever seeing it after the fact.

**Architecture, in one pass:**
- `core/block_types.py` (new) -- `BlockType` (6 members), `SceneLayout` (2: `SINGLE`,
  `SPLIT_HORIZONTAL` -- a third, stacked, is real cheap future work, not built speculatively),
  `MotifName` (3), `ALLOWED_BLOCKS` (a `VisualIntent -> BlockType` hint table, TIER_SUPPORT's own
  "spelled out, no-op registration point" convention, never enforced on the LLM's response --
  strict mode cannot make an enum choice conditional on another field).
- **Routes around D29 (Azure strict mode cannot express a discriminated union) with two calls
  instead of one union schema:** `plan_visuals` asks for a `VideoScenePlan` (motif + per-segment
  layout + an ordered list of `PlannedBlock{block_type, role, anchor_phrase}` -- flat enums only,
  never content); `author_scene`'s `fill_block` then asks one further call per planned block, each
  constrained to that block's own concrete schema (`core/block_schemas.py`, renamed from
  `core/slot_schemas.py`). Never a union in one schema, always N calls each with one concrete
  shape -- the direct generalisation of `fill_slots`'s old one-call-per-segment pattern to
  one-call-per-block.
- `Segment.slots` renamed to `Segment.scene` (`core/models.py`), holding a
  `core.scene_schemas.ComposedScene` (motif, layout, blocks, each block's `payload` nullable until
  `author_scene` fills it) -- the same D29 "untyped at rest, validated at point of use" pattern
  `slots` used, one level down, and genuinely progressive: `plan_visuals` writes it with every
  payload `None`, `author_scene` fills them one call at a time.
- Segment 0 is forced to a single `TITLE` block **unconditionally in code**
  (`visual_plan.py::_forced_title_scene`), not an advisory prompt line -- confirmed live: the
  first segment of the real render below is a title card with no LLM call for its plan at all.
- **`rendering/compose.py` dispatches by `SceneLayout`, not `VisualIntent`** --
  `_layout_{single,split_horizontal}.html` import per-block-type Jinja partials
  (`rendering/templates/_block_*.html`) dynamically (`{% import "_block_" ~ block.block_type ~
  ".html" as blk %}`), each block's markup+script namespaced by an `id_prefix` (`b0`, `b1`, ...)
  unique within the composition. Five of six blocks (`title`, `text_panel`, `stat_callout`,
  `code_panel`, `diagram_chain`) are direct lifts of five working pre-T18B templates' proven
  choreography, parameterised by prefix and a `compact` flag for the split layout.
  **`array_grid` is the one genuinely new block**, with no pre-T18B equivalent and no turnkey
  HyperFrames registry component (confirmed by this session's own capability research): a row of
  cells that narrows over the narration via `ArrayEliminationStep`s, each with its own
  `remaining_start`/`remaining_end`/`anchor_phrase`.
- **Narration-anchored choreography** (`rendering/anchors.py`, pure and tested): a block's own
  `anchor_phrase` and, for `text_panel`/`diagram_chain`, each item's own text, are matched against
  `segment.word_marks` in `rendering/compose.py` before any template sees them -- real timing when
  a match is found, the old fixed cascade otherwise. `array_grid`'s steps use the same
  `resolve_anchor` machinery against their own already-authored `anchor_phrase` field rather than
  a derived one.
- **Scene-level camera drift**: every layout wraps its content in a `#camera` element carrying a
  single slow, continuous GSAP scale+translate across the segment's full duration, independent of
  which blocks fill it -- attacks "reads like a slideshow" at the architecture level rather than
  per-template.
- **Cue-based captions**: `mux/caption_cues.py` (new) extracts the cue-grouping
  (`MAX_WORDS_PER_CUE=8`) `mux/subtitles.py` already had, now shared with
  `rendering/templates/_captions.html`, which shows one cue at a time and clears it the instant
  the next begins -- the accumulate-forever bug this was scoped to fix.
- **Motif-keyed palettes**: `rendering/palettes.py` replaced six job-id-hashed palettes with three
  motif families (Blueprint: light paper, schematic connectors -- the actual fix for D95's "still
  reads navy blue," which no *count* of dark palettes could ever have answered; Terminal: warm
  dark, zero blue; Broadcast: light neutral, one bold accent), selected by `plan_visuals`' own
  `motif` choice rather than a hash.

**Confirmed NOT reopened, by reading the live files this session:** D2 (LLM never writes HTML --
if anything tightened, since the LLM's vocabulary per call is now smaller: enums plus one block's
small payload), D3, D9/D99, D19-D24, D73 (followed: `plan_visuals` and `author_scene` both
register with `build_transient_retry_policy()` alone, each individual LLM call isolated via
`generate_with_bounded_retries`), Invariant 1 (`duration_ms` required, structurally, in both
`fill_block` and `compose_scene`), D93, D101.

### D106 — Four real bugs found only by running the real toolchain, not by reading the templates

Every one of these passed `pytest`/`ruff` clean and was caught only by an actual `hyperframes
check` or `project-reviewer` render -- the same lesson D89 already drew about this project's
templates, recurring in the new mechanism.

1. **Captions rendered with no visible text, and cross-cue ids collided** (found by
   `project-reviewer`, confirmed by direct render). `_captions.html`'s `captions_markup` dropped
   `{{ word.text }}` from the span entirely, and used the *inner* loop's `loop.index0` for both
   halves of the cue-scoped id (`{prefix}-cap-{cue}-{word}`), so every cue's first word collided
   with every other cue's first word. Fixed: the text is written back in, and the cue index is
   captured via `{% set cue_idx = loop.index0 %}` before the inner loop, matching the pattern
   `captions_script` already had right. New regression test:
   `test_captions_render_every_words_text_with_unique_ids_across_cues` (nine words forces two
   cues, which is what exercises the cross-cue id path at all).
2. **`_block_text_panel.html`'s `compact` split-layout choreography never ran** (found by
   `project-reviewer`). Its `script` macro never declared a `compact` parameter, so the layout's
   `compact=true` call site silently bound nothing and `{% if compact %}` always took the `else`
   branch -- every split-panel headline played the full-width entrance instead of the compact one,
   and tried to tween an underline element `markup()` correctly never renders in compact mode.
   Fixed by adding `compact=false` to every block's `script` macro signature (matching `markup`'s
   existing parameter) and passing it explicitly from both layout templates. **Zero test coverage
   previously exercised `SPLIT_HORIZONTAL` end to end** -- new parametrized test
   (`test_a_split_horizontal_scene_has_no_id_collision`, all six block types) closes that gap.
3. **`code_panel`'s own internal wrapper id collided with the split layout's own wrapper id**
   (found by this session's own Phase 0 benchmark, via a real `hyperframes check` warning --
   `overlapping_gsap_tweens` on `#b0-panel` -- not by reading the templates, and not caught by (2)
   above, which only ever paired `text_panel` with itself). `_layout_split_horizontal.html`'s
   region wrapper and `_block_code_panel.html`'s own internal panel div both used the identical id
   `{{ prefix }}-panel`. Renamed the layout's wrapper to `{{ prefix }}-region`.
4. **`array_grid`'s strike-through line's collapsed state lived in static CSS, not GSAP** -- a
   direct instance of the exact anti-pattern `_tokens.html`'s own docstring already warns every
   template author about ("no element carries its animated end-state in static CSS... every
   from-state is set in JS via fromTo, never in CSS"), reintroduced once by the one genuinely new
   template this task wrote. `hyperframes check` failed with `text_occluded` errors on
   `.blk-array-cell-value` for cells that were *never eliminated* -- a cell with no elimination
   tween targeting it had no JS ever set its strike's transform, so it sat at CSS's default
   (full-width, fully opaque) instead of collapsed. Fixed with an unconditional
   `tl.set(..., {scaleX: 0}, 0)` for every cell's strike at timeline start, not only the ones a
   step later targets. **A second, distinct finding surfaced once real cells were actually
   eliminated**: `text_occluded` fired again, correctly identifying that the strike visually
   overlaps the value it crosses out -- which is the whole point of a strikethrough, not a
   legibility bug. Marked intentional with `data-layout-allow-occlusion`, the exact escape hatch
   `hyperframes check`'s own fix-hint names for this case.

None of these four are visible to `pytest` or `ruff` -- three surfaced only via `hyperframes
check` against a real composition, one via a real render's rendered frame. Recorded here rather
than only in the diff because a future template author hits the same traps this session's own new
block did.

### D107 — Two pre-existing gaps found during this task's own verification, neither caused by it

Discovered while trying to satisfy T18B's own DoD, not part of the compositional-scene work
itself:

- **The Blob skill registry (`RUNTIME_ENV=azure`) had silently drifted from local disk since
  T18A**: `scene-authoring/1.1.md` was never uploaded when T18A shipped it, so a real
  `RUNTIME_ENV=azure` run has been loading `1.0` (missing the count-up guidance) for an entire
  task without anyone noticing, because no `local_live`/live verification in T18A or since
  actually exercised the Blob-backed registry against a real graph run. Fixed as a one-off sync
  (all five current packs, including this task's new `visual-plan` and `scene-authoring/1.2`) --
  **no automated sync exists**; this is manual, per D4's own design, and will drift again the same
  way unless a future task builds one.
- **`tests/test_graph_pipeline_live.py`'s mixed-tier test is unsatisfiable under the current
  ladder**, discovered by actually running it (not by reading it): its `FRAME_BUDGET=55` arithmetic
  assumes `Importance.ASIDE`'s ideal tier is `STATIC`, which was true before D99 but has been
  `REVEAL` since T18A's ladder correction. Worked out by hand: under `resolve_tiers()`'s two-pass
  algorithm (all `REVEAL` promotions before any `ANIMATED` ones, `REVEAL`'s frame cost a
  duration-independent constant), a two-segment CRITICAL+ASIDE pair **cannot** produce an exact
  `{STATIC, ANIMATED}` split at any budget -- the same budget window that keeps ASIDE off `REVEAL`
  (`9 <= budget <= 15`, fixed regardless of duration) is always far below what CRITICAL needs to
  reach `ANIMATED` (`>= 49` at the durations this test needs for a safe crossfade, per D93's own
  "comfortably above 2x `DEFAULT_TRANSITION_S`" constraint). **Not fixed here** -- `core/
  tier_resolver.py` has zero diff this task and this is a pre-existing D99-era gap in one
  `local_live` test file, not a T18B regression; genuinely fixing it needs either a third segment
  or a different tier pairing, not a constant tweak, and is scoped work for whichever future
  session next touches this file. T18B's own "real render, watched" DoD was satisfied instead by
  the 18-combo `test_render_segment_live.py` sweep (every block type, every tier, real
  `hyperframes check`, all green) plus the real `cli.py` run below.

### D108 — Phase 0: composite scenes measure ~13% slower than the old single-block baseline, still
comfortably inside budget; no `tier_resolver` change made

Per the plan's own Phase 0 gate: `scripts/measure_render_throughput.py` (rewritten to compose a
realistic `SPLIT_HORIZONTAL` scene, `CODE_PANEL` + `DIAGRAM_CHAIN`, with the new scene-level
camera drift) fed to `npx hyperframes benchmark`. **First attempt timed out at 900s** -- not a
hang (no orphaned processes; `hyperframes check` on the same composition completed in under two
minutes with no errors), but `benchmark`'s default sweep covers *both* 30fps and 60fps
configurations, doubling the real work a single `--runs N` implies. A single-run probe at each
config measured **30fps: 51.0s for 750 frames (~14.7 fps); 60fps: 101.6s for 1500 frames
(~14.8 fps)** -- consistent with each other, and about **13% slower** than T18A's ~17 fps
single-block baseline. Under the plan's own ~15-20% threshold for "fold into a constant, don't
touch the algorithm": `core/tier_resolver.py` is untouched (still zero diff), and `FRAME_BUDGET`
stays at `9500` -- at the new measured rate a 7-minute/15-segment video's ~9000 frames costs
~10.7 minutes of rendering (up from ~9 minutes), still comfortably inside the ~15-20 minute
target even with contention. `.env.example` and `core/frame_budget.py`'s docstring both now carry
the real composite-scene figure alongside the old single-block one, rather than leaving the more
representative number unrecorded -- the same discipline D99 was written to enforce after D16's
wrong figure went unquestioned for weeks.

### D109 — Real end-to-end verification: `cli.py "how binary search works"`, 90s target, watched

`RUNTIME_ENV=azure` + `RENDER_ENV=local` (D100), the same bridge T18A used, same topic for
continuity. 3 segments, all three `Tier.ANIMATED`, 140.8s wall-clock. Verified by extracting real
frames at multiple timestamps and looking at them, not only by asserting durations (D93's own
lesson: timing assertions never catch content or perception bugs) --

- **Segment 0** (forced title, structural): "Binary Search" / "Find the right shelf," Blueprint
  motif (light paper, orange accent) -- genuinely distinct from every prior video's near-black
  amber/blue, the concrete fix for D95's "still reads navy blue."
- **Segment 1**: `diagram_chain`, a 4-node rail ("Check middle" -> "Discard half" -> "Repeat
  narrowing" -> "Stop or find") -- the direct-lift block rendering correctly end to end.
- **Segment 2**: `SPLIT_HORIZONTAL`, two `text_panel` blocks side by side with the 3D tilt entrance
  -- confirmed both panels' own headlines and items render (a second frame a few seconds later
  than the first checked one showed both labels present; the first check briefly caught panel 2's
  own headline before its entrance tween, a timing artifact, not a bug).
- **Captions**: confirmed clearing and replacing correctly across multiple cues in the same
  render, at 1920x1080, real audio+video streams, ffprobe-verified.

**Not exercised in this specific run**: `array_grid` and `stat_callout` (the outline/plan-visuals
call did not choose either for this particular 3-segment, 90-second topic) and a second motif
(one job, one motif, by design) -- both already verified independently via the 18-combo live sweep
and `hyperframes check`, respectively, so this is a gap in *this run's* content mix, not in
verification coverage.

**One real content-quality observation, not a bug**: the LLM authored one `SPLIT_HORIZONTAL`
panel's `headline` as "Sorted case vs unsorted case" -- an overall comparison title rather than a
short per-side label ("Sorted"/"Unsorted") the way `runtime_skills/scene-authoring/1.2.md`'s
guidance intends. The mechanism worked exactly as designed; this is a prompt-calibration nuance
for whichever future session next tunes the pack against more real output, not a code defect.

**Also discovered and fixed in passing**: the real run's first attempt failed outright with
`SkillPackNotFound: 'visual-plan'` -- see D107, the Blob-registry drift that made this necessary
before any real `RUNTIME_ENV=azure` render of T18B's work was possible at all.

### D110 — Captions are movie-style at the cue level only after removing the per-word ink; the
old karaoke reveal survived D106's own fix without being noticed as still-wrong

**The trigger.** The user watched a description of the real render and asked directly whether
"subs appearing word by word" was actually fixed. It was not, fully: D106's fix (this checkpoint's
own predecessor) corrected the *wall-of-text* bug -- a cue now clears the instant the next one
starts -- but kept "the same word-by-word-scalar ink mechanic as before" *inside* each cue on
purpose, carried forward from the pre-T18B captions rather than questioned. Each word still
dimmed until its own real `offset_ms`, so a cue still visibly assembled itself one word at a time
even though it now correctly cleared afterward. Two different bugs, wearing the same symptom --
fixing the accumulation did not fix the reveal style, and nothing forced a second look at the part
that was "kept" rather than "changed."

**Rejected:** leaving the per-word ink in place on the reasoning that it is a real, working
mechanic that D106 already verified. **Reasoning:** a viewer does not experience "the wall-of-text
bug is fixed" and "the reveal style is still word-by-word" as two separate facts -- both read as
"the captions come in one word at a time," which is the complaint. Movie-style means a line (or
the ~8-word cue this project already groups by) appears as one unit; that is a property of the
*reveal*, not just of *retention*.

**Landed:** `rendering/templates/_captions.html`'s `captions_script` macro no longer emits any
per-word tween -- the cue-level `tl.set(el, {opacity:1}, cueStarts[i])` (already instant, already
correct) is now the *only* animation, so every word in a cue is at full color the instant the cue
appears. `captions_markup`'s per-word `<span>`s and their ids are kept (individually addressable,
matches the existing id-collision regression test's expectations) but their CSS no longer carries
an initial dimmed/transparent state -- there is nothing left to tween.

**Verification gap, explicit not silent:** the user asked that this checkpoint run no further
tests. `pytest`/`ruff`/the boundary greps/`project-reviewer` were **not re-run** after this fix,
by explicit instruction -- a deliberate, narrower exception to this project's normal checkpoint
gate, not an oversight. The change itself is small and easy to reason about statically (two `tl.
fromTo` blocks and three CSS declarations removed, nothing else touched), but it has not been
verified against the real toolchain the way every other T18B change in this checkpoint was.
**Whoever next touches `_captions.html`, or runs the next real render, should confirm this by
actually watching one** rather than assuming it from this entry alone.

**Also flagged for T18C**, not fixed here: the caption band's own position is verified (
`hyperframes check --caption-zone`, by construction), but nothing checks whether a *block's*
content grows down into that same zone -- a real, not yet realized, risk once T18C's denser
blocks (`SEQUENCE_DIAGRAM` lanes, a `TIMELINE` row, a long `CODE_DIFF`) exist. Recorded in
`tasks.md`'s T18C entry directly, at the user's explicit request, rather than left to be
rediscovered live the way the id-collision and static-CSS-transform bugs in D106 were.

### D111 — A cleanup pass over the T18B diff found one genuinely broken script and two actively
misleading build-time docs; `get_dead_code` found nothing real

**The trigger.** The user asked directly whether the old architecture had actually been cleaned
up, not just superseded -- a fair question after a rewrite this size. `git grep` for every old
symbol name (`slot_schema_for`, `SLOT_SCHEMAS`, `TitleCardSlots`/`CodeWalkthroughSlots`/
`DiagramFlowSlots`/`ComparisonSlots`/`BulletListSlots`/`FlowNode`, the six retired template
filenames, bare `.slots` access) plus a RepoWise `get_dead_code` sweep, rather than trusting the
T18B checkpoint's own diff summary.

**Found and fixed:**
1. **`scripts/measure_segment_concurrency.py` was genuinely broken** -- `from core.slot_schemas
   import TitleCardSlots`, a module T18B deleted. Not caught by `pytest` because it is a standalone
   `__main__` script, not a test file. Updated to the plan_visuals+fill_block two-call sequence
   (mirrors `tests/graph_pipeline_fixtures.py`'s own `scene_plan()`/`slot_payloads()` pattern).
   **Smoke-running the fixed import surfaced a second, deeper, also pre-existing bug**: its
   `FRAME_BUDGET=600` (unchanged from before T18B) plus `FakeTTSProvider()`'s un-seeded duration
   estimate (very short synthetic narration text) promotes some segments to `Tier.ANIMATED` post-
   D99's `IDEAL_TIER` correction, and `FakeRenderBackend.render()` writes placeholder bytes, not a
   real MP4, so `render_scene`'s real ffmpeg mux fails on whichever segment lands there. This is
   the same class of gap as D107's two findings -- a D99-era ladder change silently invalidating a
   script nobody re-ran since -- just a third instance, found only because this checkpoint's
   import fix let the script run far enough to reach it for the first time. Fixed by adopting
   `tests/graph_pipeline_fixtures.py`'s own already-established answer: `FRAME_BUDGET=0`, which
   keeps every segment on Tier 0 deterministically and is sufficient for what this script actually
   measures (disk I/O contention, not tier/render behaviour). Re-run end to end after the fix:
   15 segments, 0.955s, succeeded.
2. **`.claude/skills/scene-templates/SKILL.md` and `.claude/commands/newintent.md` described the
   deleted architecture in full** -- one-`VisualIntent`-per-template, a slot schema per intent, no
   mention of `BlockType`/`SceneLayout`/`plan_visuals` at all. Both are build-time guidance loaded
   into a *future* Claude Code session's context, not runtime code -- wrong, they actively mislead
   whoever next touches `rendering/` rather than merely failing to help. Rewritten for the current
   architecture. `newintent.md`'s registration list shrank to match `VisualIntent`'s much narrower
   real role (an outline-time hint plus an `ALLOWED_BLOCKS` entry -- no template, no schema, no
   tier-cost characteristics of its own). **New `/newblock` command** added for the registration
   workflow that is now the common case -- adding a `BlockType` -- since T18C's whole scope is
   exactly that.
3. **Two stale in-code comments** (`core/models.py`'s `VisualIntent` docstring, one line in
   `tests/test_tier_resolver.py`) still named `core/slot_schemas.py`/`SLOT_SCHEMAS`. Fixed; the
   `core/models.py` one also needed real content changes, not just a filename swap -- the comment
   described `/newintent`'s old registration list, which no longer applies to what `VisualIntent`
   does.

**Checked and NOT touched, on purpose:**
- `runtime_skills/scene-authoring/{1.0,1.1}.md` -- superseded by `1.2` but deliberately kept, not
  deleted. Pack versioning is this project's own designed mechanism (T7, D43-D46), the same reason
  old git commits are not deleted; `SkillRegistry.versions()` promises a real history, and the
  `DiskSkillRegistry`/`BlobSkillRegistry` parity tests exercise more than one version existing.
- `rendering/templates/_reference_tier2.html` -- a frozen T4-era hand-written spike composition,
  labelled as such in its own history, predating and independent of the block/template system
  entirely. Reference material, not dead code masquerading as current.
- `.claude/skills/pipeline-debugging/SKILL.md` -- read in full; still substantively accurate
  (failure modes, artifact layout, isolation technique are all architecture-independent). Left
  alone rather than rewritten for the sake of touching it.
- RepoWise's `get_dead_code` flagged 5 `unreachable_file` and 4 `zombie_package` findings, all
  below the tool's own 0.5 confidence floor and all false positives on inspection: the five are
  hook scripts the harness invokes via `.claude/settings.json`, not Python imports (expected
  in-degree of zero), and the four "zombie" packages (`adapters`, `api`, `mux`, `rendering`) are
  imported constantly via `from adapters.x import y`-style deep imports the tool's package-level
  heuristic doesn't count. Nothing here indicated a real cleanup gap the manual grep sweep missed.

**Verified after all of the above:** `pytest` (562 passed, 1 skipped, unchanged from before this
pass), `ruff check .`/`ruff format --check .` clean, boundary/line-count checks clean, and the
fixed script actually re-run to completion, not just imported successfully.

### D112 — RepoWise's index was silently broken (73% SQL/vector drift); a real Azure embedder is
now wired in; the `/build-task` model-switch claim was false and is now a mandatory self-check
instead

Three infrastructure findings and fixes, prompted by the user asking directly whether the project's
own tooling (RepoWise, the plan/build model split) was actually working as documented, not by any
code change to the pipeline itself.

**RepoWise's index had drifted silently: `repowise doctor` showed `SQL=171, Vector=46,
Drift=73.1%`** -- 125 wiki pages had never been embedded, so `search_codebase`/`get_answer` had
been searching over less than a third of the indexed content, with nothing surfacing this until
asked to check. `repowise reindex --embedder mock` closed the SQL/vector gap structurally
(0% drift); semantic quality stayed capped by the mock embedder until the fix below.

**A real Azure OpenAI embedder is now wired in, on a separate deployment from the chat model.**
Quota checked first this time (`az cognitiveservices usage list -l eastus`) -- unlike D49's chat-
model surprise, every SKU for `text-embedding-3-small` had healthy headroom (1000K TPM under
`GlobalStandard`), so no repeat of that trap. Deployed `text-embedding-3-small` under
`GlobalStandard` on the existing `skill-bites` resource, verified working directly against Azure's
v1 API surface (`https://skill-bites.openai.azure.com/openai/v1/`, no `api-version` query param
needed) before wiring anything in. RepoWise has no native "Azure OpenAI" embedder, but its generic
`openai` embedder works unmodified against that v1 surface. Credentials live in `.repowise/.env`
(gitignored, loaded automatically by `repowise mcp` before the MCP server starts, per its own
`--help` text) -- **not** this project's own `.env`, and not `.mcp.json` (which is git-tracked;
committing a secret there was never on the table). `repowise reindex --embedder openai` re-ran
clean against all 171 pages. **Not yet live for this session's own MCP connection** -- the server
only reads `.repowise/.env` at startup, so a running session keeps using the mock embedder until
the MCP connection restarts. Also found, not yet fixed: `get_answer` still reports
`degraded: no-llm-provider` -- retrieval works, prose synthesis does not, because `REPOWISE_
PROVIDER` was never set. Separate scope from the embedder question that was actually asked;
flagged rather than silently fixed with a guessed provider choice.

**The `/build-task` model-switch mechanism was documented as reliable and is not.** CLAUDE.md
claimed "the session returns to Sonnet on your next message" after `build-task.md`'s `model: opus`
frontmatter expires. Verified false twice now: T18A's entire build ran on Opus because of exactly
this (recorded in that checkpoint's own handoff.md), and T18B's build very nearly did too --this
session was still on Opus when the plan was approved, and only proceeded on Sonnet because the user
caught it and typed `/model sonnet` by hand before approving. The real, observed behavior: an
explicit `/model` call earlier in a session pins the model, and nothing in the harness un-pins it
automatically once a command's own turn-scoped override expires. **Rejected:** continuing to assert
the false claim and hoping it holds next time. **Landed:** CLAUDE.md's "Which model runs what" and
`build-task.md`'s closing instruction both now state the real behavior and make a self-check
mandatory -- read the current-model line from the turn's own system info immediately after plan
approval, before any `Write`/`Edit`/`Bash`, and refuse to proceed if it isn't Sonnet. This is not a
technical enforcement (no hook can see which model is active); it is a documented, load-bearing
discipline replacing a documented, false assumption.

## 2026-08-29 · T18C — The broadened block library (block-library slice only)

`tasks.md`'s T18C entry scoped a much larger session than what shipped: six block-library items, a
vision critique/revision loop, and a full 7-minute validation render. Scoped down in planning, on
the user's agreement, to the block library alone (plus two related pre-existing gaps this session's
own research surfaced) -- the vision loop and validation render become a future task. Full reasoning
for each individual decision below.

### D113 — `DIAGRAM_CHAIN` is retired, not kept alongside `GRAPH_DIAGRAM`

**Landed:** `BlockType.DIAGRAM_CHAIN` is deleted outright -- the enum member, its template, its
schema, every `ALLOWED_BLOCKS`/test/fixture reference. `GRAPH_DIAGRAM` (`core/block_schemas_graph.py`,
`rendering/templates/_block_graph_diagram.html`) replaces it with two layout modes: `CHAIN`
reproduces the retired block's single straight rail exactly (a direct port of its entrance/rail-draw
choreography), `GRAPH` places nodes on a real 2D canvas for arbitrary topology, with a traveler-dot
traversal highlight (straight-line hops, not a curved path -- the vendored `gsap.min.js` was
confirmed not to bundle `MotionPathPlugin` before committing to this, `grep -i motionpath` came back
empty).

**Rejected:** keeping `DIAGRAM_CHAIN` alongside `GRAPH_DIAGRAM` as a separate, simpler block for the
common linear case, retiring nothing. Lower engineering risk (fewer registration points touched, no
re-verification that the linear case still renders identically), but leaves two block types with
overlapping capability, and `tasks.md`'s own T18C scoping already called for the absorption
explicitly ("`diagram_chain`'s existing linear-rail mode absorbs into this as one of its layouts, not
a separate block").

**Reasoning:** matches T18B's own precedent (retiring the six old whole-scene templates rather than
carrying them alongside the new compositional blocks) and the project's stated aversion to
carrying duplicate capability. The user chose this over the coexistence option directly when asked
during planning.

### D114 — `ARRAY_GRID` is generalized via a breaking rename, not a parallel legacy field

**Landed:** `ArrayEliminationStep` is renamed `ArrayStep` and gains `op` (`narrow`/`shift`/`push`/
`pop`) and `end_operation` (an optional `+`/`-` badge); `ArrayGridSlots` gains `orientation`. Every
consumer was updated in the same pass -- `tests/block_examples.py`'s fixture, the skill-pack
guidance bullet, the template's script macro -- rather than adding the new fields as optional with
defaults (Azure strict mode forbids defaulted/optional fields outright, so "additive and backward
compatible" was never actually available as an option here).

**A real bug in this generalization was found by `project-reviewer` at the FINAL checkpoint review
gate, after the offline suite was already green.** The new coverage test's own `shift` fixture
(`tests/test_array_grid_and_graph_modes.py`) started from the array's default full-width active
range and shifted to a *narrower* one -- numerically valid, but it meant the template's `enter()`
loop (`prevEnd..step.end`, SHIFT's whole reason for existing as distinct from `narrow`) never ran a
single iteration, so the "new cell enters as the window advances" code path had zero coverage
despite a test file whose entire stated purpose was covering exactly that. Fixed by prefixing the
fixture with a real `narrow` step first, establishing a genuine sub-window before the `shift`
translates it -- the same lesson D73/D82/D89 already recorded in different shapes: **passing an
offline test proves the fixture was well-formed, not that the fixture actually exercises the branch
its own docstring claims to.**

**Rejected:** validating `SHIFT`'s "must be a forward-advancing, width-preserving translation"
constraint with a pydantic model validator. Considered and dropped for the same reason
`ArrayEliminationStep`'s pre-T18C "the range only ever shrinks" constraint was never
validator-enforced either -- only documented in the field's own description, the same convention
this schema already used and this task chose not to reopen.

### D115 — Annotations are a cross-cutting overlay, not a `BlockType`; two real positioning bugs found only by the real toolchain

**Landed:** a new concept, not a new registration pattern -- `AnnotationType` (cursor/check/warning)
targets a specific element *inside* an already-planned block (`core/scene_plan_schema.py::
PlannedAnnotation`, `core/scene_schemas.py::ComposedAnnotation`) rather than filling its own
`SceneLayout` region. No new LLM call: an annotation's only content (a short optional caption) comes
from the same single `plan_visuals` call that already produces `PlannedBlock.role`'s free text --
doubling the call count for something this small was rejected as disproportionate to D2/D29's "one
call per genuinely separate decision" reasoning.

**Rejected (the more conservative alternative, considered explicitly during planning):** modeling
annotations as ordinary `BlockType`s occupying their own layout region. Simpler, zero new
architecture, but cannot literally point at or overlay a specific element inside another block's
content -- a real capability reduction from D105's own original framing ("shared, reusable...
usable by any template rather than baked into one"). The user chose the more faithful, more novel
overlay design when asked directly.

**The render-time positioning mechanism** (`rendering/annotations.py`, `rendering/templates/
_annotations.html`): every layout's GSAP timeline is built `paused: true` and never played during
script evaluation, so `getBoundingClientRect()` inside the composition's own inline `<script>`
always observes the same pristine, untransformed layout regardless of when in the script it runs --
the same category of technique `diagram_chain`/`graph_diagram` already use (`getTotalLength()`
measured once, baked into `strokeDasharray`), pointed at a foreign element instead of a block's own
SVG. The delta between an annotation and its target is computed once and baked into a `tl.set(...)`
at t=0; because the annotation renders as a DOM sibling inside its target's own container (`#stage`
for SINGLE, `#<prefix>-region` for SPLIT_HORIZONTAL), that delta stays correct under every later
transform (camera drift, panel idle-bob) both elements share.

**Two real bugs in this mechanism were found only by this task's own Phase-0 real-toolchain spike,
not by reasoning about the design** -- the same lesson D89/D106 already recorded for T17/T18B's
templates, recurring here for a genuinely new rendering mechanism:
1. `getBoundingClientRect()` returns viewport pixels, which do not equal this composition's own
   1920x1080 CSS-pixel space whenever the capture harness renders at a different effective scale.
   `hyperframes check`'s own `escaped_container` finding caught an annotation landing hundreds of
   pixels outside `#root`. Fixed by normalizing every measured delta against `#root`'s own known
   1920px width, measured live (`root.getBoundingClientRect().width / 1920`).
2. The annotation wrapper `<div>`s had `position: absolute` with no explicit `top`/`left` -- their
   untransformed base position was therefore wherever they naturally fell in the DOM flow (the last
   flex child in a `flex-direction: column` container), not the container's origin the delta
   calculation assumed. Fixed by adding explicit `top: 0; left: 0` to all three `.anno-*-wrap`
   classes. Both bugs, and the fix, were verified by composing real scenes and running the actual
   `hyperframes check --json` against them -- not merely reasoned through -- confirming `ok: true`,
   zero findings, in both `SINGLE` and `SPLIT_HORIZONTAL` layouts before being trusted.

An annotation caption legitimately overlapping the specific content it marks (`hyperframes check`'s
`content_overlap` finding, real and expected) got the same `data-layout-allow-overlap` escape hatch
D106 item 4 already established for `array_grid`'s intentional strike-through occlusion, rather than
redesigning the layout to avoid a deliberate overlap.

**Confirmed, not fixed:** the SPLIT_HORIZONTAL "same panel" restriction the skill-pack guidance
states is prompt-only, with no code-level guard in `rendering/annotations.py`'s bounds check.
`project-reviewer` confirmed this is not exploitable into a broken frame (an annotation's render
container is always derived directly from its own target block, never assumed), so it was left as a
narrative constraint rather than adding a redundant guard.

### D116 — The caption/content-overlap fix, and `--caption-zone`'s finding needs no new assertion

**A real, already-live bug, found by this session's own research, not by any new block:**
`_captions.html`'s caption band occupies `y=926px` to `y=1016px` on the 1920x1080 canvas. Both
layout templates' `#stage` used 2-value padding shorthand (`130px <side>px`, top=bottom), putting
`#stage`'s own content-box bottom edge at `y=950px` -- **already 24px past the band's top edge**,
before any block content even grew toward it. This predates T18C's new blocks entirely (present
since T18B) and was simply never checked for. Fixed: 3-value padding shorthand
(`130px <side>px 170px`) in both `_layout_single.html` and `_layout_split_horizontal.html`, clearing
the band with a real margin (content-box bottom edge -> `y=910px`).

**`hyperframes check --caption-zone`'s finding folds into the SAME `layout` category the existing
test already asserts `errorCount == 0` on -- confirmed empirically, not assumed.** Real
`check --json --caption-zone ...` runs against hand-composed scenes (including a deliberately
overflowing one, 16 sequence-diagram messages) never produced a separate top-level JSON key; a
caption-zone collision would surface as a `layout` finding alongside `canvas_overflow`/
`content_overlap`/etc. **Rejected:** writing a new assertion against a guessed key name (the plan's
own Phase-0 item explicitly flagged this as something to confirm empirically rather than assume).
The actual fix in `tests/test_render_segment_live.py::_run_check` is one flag added to an existing
subprocess call -- no new assertion needed, since the flag's findings are already covered by the
`errorCount` check two lines below where it was added.

### D117 — D107 closed: the mixed-tier live test's target tier set was unreachable for ANY input, not just the case it happened to use

D107 (recorded at T18B's checkpoint) found `tests/test_graph_pipeline_live.py`'s mixed-tier test
unsatisfiable at its then-current `FRAME_BUDGET`, and guessed the fix needed "a third segment or a
different importance pairing." Worked out fully this session, by hand, against
`core/tier_resolver.py`'s real constants: **`{Tier.STATIC, Tier.ANIMATED}` is unreachable at any
safe (crossfade-floor-respecting) duration, for any segment count or importance pairing whatsoever**
-- `REVEAL_FRAME_COST` is a flat `+7` over `STATIC` regardless of duration, while `ANIMATED`'s cost
is duration-scaled and always far larger at a safe duration, so a segment that fails `REVEAL`
promotion never leaves enough remaining budget for another segment to reach `ANIMATED`. No segment
count or pairing changes that arithmetic.

**Landed:** retargeted to `{Tier.REVEAL, Tier.ANIMATED}` instead -- genuinely reachable (minimum
budget 56, derived by hand from the same two-segment ASIDE+CRITICAL setup already in the test), and
still exercises the test's actual point, a real two-clip crossfade concat. `FRAME_BUDGET` raised
55 -> 80; unlike the old target, there is no upper bound to stay under (`ASIDE` can never be promoted
past `REVEAL` no matter how large the budget grows), so 80 is simply "comfortably above 56," not a
new fragile boundary. The test's own stale docstring (claiming `DEFAULT_TRANSITION_S` is 1.0s when
the real constant is 0.5s) was corrected in the same pass.

**Rejected:** chasing a `{STATIC, ANIMATED}` split by tuning a segment to a near-floor duration
(~500-600ms) where the arithmetic technically closes. Explicitly avoided -- this is the exact
fragile boundary a different test's own docstring already names as historically flaky ("a duration
right at that boundary made the one crossfade transition too tight to render reliably").

### D118 — Vision critique loop, full validation render, and a new "faster rendering" request all deferred to a future T18D

Two things were pushed out of this session's scope, both raised as scope questions during planning
rather than silently absorbed or silently dropped:

**The vision critique/revision loop and the full 7-minute validation render** (both originally part
of `tasks.md`'s T18C entry) -- deferred on the same reasoning D104 used to split compositional scenes
out of T18A: each is a substantial, independent axis of work (an `LLMProvider` image-input interface
change plus real Azure/local adapter parity, in the first case) that deserves its own scoping and
measurement pass, not a guess bolted onto an already-large block-library session.

**A new request, raised mid-planning: "make video making faster."** Not yet scoped to any specific
target (render throughput, LLM/TTS call latency, or overall wall-clock were all named as
possibilities, none chosen). Deferred for the same reason -- performance work needs its own
measurement pass, the same discipline D16/D99's own history argues for (a wrong measurement, once
written into a constant, propagates unquestioned across sessions until someone re-derives it from
first principles).

**Both land in a new task, and the user's own name for it is "T18D."** `tasks.md`'s T18C entry
already used "T18D" as a placeholder name for a different, unscoped idea ("push LLM compositionality
further, testing the limits of what the render-time budget allows"). This checkpoint's `tasks.md`
edit resolves the collision by merging the new performance item into that placeholder's scope rather
than renaming either -- all three (vision loop, validation render, performance) are real future work
with no scoping conversation yet, and none is promised for any particular future session.

### D119 — A real render (post-checkpoint) found `SEQUENCE_DIAGRAM`/`TIMELINE` were resolving
entrance timing from the wrong field; fixed. A second, distinct `GRAPH_DIAGRAM` layout issue found
in the same render is confirmed but NOT fixed yet.

Immediately after T18C's checkpoint, a real `cli.py` render ("how TCP's three-way handshake
establishes a connection", 90s target, `RUNTIME_ENV=azure`) was run specifically because T18C's own
new blocks had never been through a real render -- the trust-gap `handoff.md` flagged explicitly.
Frames extracted and watched directly (matching D109's own method), not just duration-asserted.

**Confirmed working:** D110's caption fix (still carried forward from T18B, also never watched
until now) -- captions appear as one unit and clear cleanly between cues, confirmed across two
frames in the same segment. `SEQUENCE_DIAGRAM`, `GRAPH_DIAGRAM` (in its `GRAPH` mode, not the
simpler `CHAIN` mode -- the plan chose the harder case on its own), both `CURSOR` and `CHECK`
annotations, and a `SPLIT_HORIZONTAL` layout all got real, unprompted use from a single topic.

**A real bug found and fixed:** `SEQUENCE_DIAGRAM`'s messages and `TIMELINE`'s events both carry
their own authored `anchor_phrase` field (`core/block_schemas_sequence.py`), added specifically for
narration-anchored timing -- but `rendering/block_timing.py` had them registered in `_ITEM_FIELDS`
(deriving a timing anchor from each item's own `label` text) rather than `_STEP_FIELDS` (using the
authored `anchor_phrase` directly), the same mistake `array_grid`'s steps and `graph_diagram`'s
traversal points do NOT make. The real render's frames showed it directly: the sequence diagram's
first message ("SYN") visibly entered AFTER its second ("SYN-ACK"), because the bare label "SYN" is
also a substring of spoken "SYN-ACK," and the narration mentioned "SYN-ACK" (as its own full label
match) before the standalone "SYN" mention resolved. **Landed:** moved both block types from
`_ITEM_FIELDS` to `_STEP_FIELDS` and updated both templates' script macros to read `step_starts`
instead of `item_starts` -- verified against a reconstructed narration reproducing the exact
ambiguity (a repeated bare "syn" token), producing correctly monotonic entrance times where the old
path did not. Re-verified against the real `hyperframes check` toolchain (still clean) and the full
offline suite (still green) after the fix.

**Confirmed but NOT fixed, flagged for a future session:** the same render's `GRAPH_DIAGRAM` (GRAPH
mode, `SPLIT_HORIZONTAL`'s compact panel) showed two of five nodes visually overlapping, plus an
edge line running off-frame. Root cause traced, not guessed: the circular auto-layout fallback
(`0.5 + 0.4*cos/sin(angle)`, `rendering/templates/_block_graph_diagram.html`) treats the canvas as
if it were square, but a compact `SPLIT_HORIZONTAL` panel's graph canvas is short and wide (`220px`
tall against ~700-800px wide) -- two adjacent nodes on the circle can land at very different X but
close-enough Y that their (auto-sized, ~100-150px-tall) bounding boxes collide in the short
dimension even though their fractional position differs correctly. A fifth node's item_starts also
resolved to a fallback timestamp (27.7s) that plausibly falls outside its own segment's actual
on-screen duration, from the same underlying risk D119's fix above addresses for a different block
type -- worth checking whether `graph_diagram`'s own node labels have the same short/generic-token
collision risk `sequence_diagram`'s did. **Not fixed here** -- this needs either an aspect-ratio-
aware layout formula or a real collision-avoidance pass, a genuine design question rather than a
one-line field-mapping fix, and deserves its own look rather than a rushed change appended to an
already-large checkpoint's aftermath.

### D120 — Watching D119's own verification render found more real problems than its one fix
covered; split into T18D (catalog, no fixing) and T18E (one comprehensive fix pass), video
generation deferred to T18D's own session

D119 fixed one bug (`SEQUENCE_DIAGRAM`/`TIMELINE` entrance timing) found by watching the real
render its own Phase-0-style verification produced. The user then watched the same video frame by
frame and found more, worse ones no toolchain check had caught:

1. **Segment 0 (the title card) sat static for ~25 seconds while the narration moved well past
   it** -- nothing new appeared on screen the whole time. The exact "reads like a slideshow"
   problem T18A/T18B already fought once (D95, D99), recurring in a place neither task's fixes
   covered -- a single static block with no per-word reveal and no visual progression, held for a
   duration a static card was never designed to justify.
2. **`SEQUENCE_DIAGRAM`'s annotation coverage was incomplete and, on inspection, timed wrong.**
   The user expected all three messages in the handshake (SYN, SYN-ACK, ACK) to get their own
   annotation, appearing one by one as each was spoken. Only the later ones did, and even those
   didn't clearly land on their own message's beat. Two candidate causes, not yet distinguished:
   `runtime_skills/visual-plan/1.1.md`'s "use annotations sparingly, one or two per scene" guidance
   fighting a case where per-step marking is exactly right, or a planning-choice problem
   independent of that guidance.
3. **`GRAPH_DIAGRAM`'s GRAPH-mode layout is confirmed broken in the exact two ways D119 already
   traced** (node overlap in a compact/split canvas; one node's entrance timing landing outside
   its own segment's window) -- watching it directly, rather than just reading the composed HTML,
   added one more concrete symptom: an edge line running off-frame, never closing on its own
   target node. **The user's own proposed design alternative is recorded here because it changes
   what T18E should actually build, not just what it should fix**: rather than keep chasing
   reliable per-node entrance timing (fragile by construction -- short/generic node labels can
   mismatch narration the same way `sequence_diagram`'s did before this session's own fix),
   reveal the whole graph up front and let the traversal dot alone carry the "explained in order"
   storytelling. The user explicitly accepted either that, or a correctly-working one-by-one
   reveal -- just not the mix of both this render produced.

**Rejected: fixing any of this now, in the same session that just checkpointed T18C.** Considered
and explicitly declined by the user -- this session is already large, and D119's own one-bug fix
already showed that a fix made without seeing the fuller picture risks missing a shared root cause
another bug would have revealed. **Landed: split into two tasks.** `tasks.md`'s new **T18D**
catalogs -- renders a deliberately varied topic matrix (chosen to individually stress block
types/situations this session's one video never exercised: `ARRAY_GRID` with `shift`/`push`/`pop`,
`CODE_DIFF`, `TIMELINE`, `GRAPH_DIAGRAM` in `SINGLE` layout, a denser `SEQUENCE_DIAGRAM`, multiple
annotations in one segment), watches every render properly (full playback or dense frame
extraction, not just `hyperframes check` -- which caught none of the three findings above), and
documents everything found, categorized by root cause where one can be traced. **No fixing in
T18D**, on purpose. `tasks.md`'s new **T18E** is the comprehensive fix pass against T18D's finished
catalog, flagged with a working hypothesis worth testing before assuming N independent fixes are
needed: several of these findings (item-anchor-timing reliability, pacing/density judgment) may
share root causes closer to the surface than they first look.

**Video generation is deferred to T18D's own fresh session, not done in this one** -- also the
user's own call, made explicitly on context-budget grounds (this session was already large from
T18C's own build). This session's job was writing up exactly what T18D should render and why, so
that session can start executing immediately rather than re-deriving scope.

**The pre-existing `tasks.md` T18D entry (vision critique/revision loop, full validation render,
rendering speed -- D118) is renamed to T18F**, same content, same unscoped status, moved only to
free the T18D/T18E names for the split above. Its own validation-render item is now explicitly
sequenced after T18E, not before -- a full-length showcase render belongs after known bugs are
fixed, not before.

### D121 -- T18D executed (real catalog, real bugs, one new systemic root cause); the user's own
critique of the six real videos plus an independent Opus analysis produced T18E's real scope,
including reopening D47 to parallelize two call sites

**T18D ran to completion, same session as this entry.** Pre-flight: the Blob skill registry had
drifted again (the same D107 gap, `scene-authoring/1.3.md`/`visual-plan/1.1.md` local-only) --
synced via `az storage blob upload` with the account-key connection string, not the `mcp__azure__
storage` tool's AAD path (that path lacks the RBAC role for blob data-plane writes on this
account, `AuthorizationPermissionMismatch` -- worth remembering before trying it again). All six
topics from D120's own matrix rendered, each opened for the user to watch directly in addition to
this session's own frame-by-frame review (cross-referenced against every segment's own authored
timing arrays, not just eyeballed). Full findings: `t18d_catalog.md` -- deliberately a separate
tracked file, not folded into this entry, because the catalog is dense (six topics, frame-level
evidence per finding) and needed to survive as working material for T18E's own planning, which is
exactly what happened.

**The headline finding is new, not one of D120's three seeded items.** `rendering/
block_timing.py::resolve_item_starts` (`_ITEM_FIELDS`: `graph_diagram.nodes`, `text_panel.items`,
`code_diff.lines` -- block types with no authored `anchor_phrase`, matched on their own short
display text instead) falls back to `_DEFAULT_ITEM_START + i * _DEFAULT_ITEM_STAGGER` **keyed
only by an item's own array index**, with zero regard for where any sibling item actually landed.
Found by grepping every rendered `*Starts` array across the matrix against the fallback's own
literal sequence (`0.75, 0.97, 1.19, ...`), then visually confirmed: 9 of ~20 arrays sampled hit
this, producing three symptoms -- whole blocks dumping in under a second then sitting static for
the rest of their segment; items appearing wildly out of authored order (a node overlap in
`t18d-code-diff` seg1 turned out to be exactly this, not a fresh instance of D119's overlap bug);
and two cases of two different items resolving to the identical timestamp. `_STEP_FIELDS` blocks
(authored `anchor_phrase`, D119's own prior fix) resolved cleanly in every case but one --
strong, now-evidenced support for extending D119's fix (label-matching -> authored-phrase-
matching) to the three `_ITEM_FIELDS` block types, which T18E's E1 does not yet cover (out of
this task's chosen scope, worth flagging for whoever scopes the next one).

**D120's three seeded findings, confirmed and refined, not just re-confirmed:**
1. Static/low-motion holds -- confirmed, now with at least two distinct causes (the structural
   title card, unchanged, D96; and the anchor-fallback total collapse above, new), plus a third
   variant (a fully blank panel for 8+ seconds, not just static-with-content).
2. `GRAPH_DIAGRAM` layout -- confirmed **and isolated**: broken specifically in `SPLIT_HORIZONTAL`
   (`t18d-code-diff` seg1 showed two independent overlapping node pairs in one diagram, worse than
   D119's single-pair finding), **confirmed clean in `SINGLE`** (`t18d-graph-single`, zero overlap
   across every frame sampled) -- a real isolation result the topic was chosen specifically to
   produce, not a guess.
3. `SEQUENCE_DIAGRAM` annotation coverage -- refined: per-message *reveal* timing is reliable when
   `anchor_phrase` resolves (D119's fix holds); what's actually thin is **annotation** coverage
   specifically -- never more than one annotation per scene across all six renders, including the
   two segments built to invite more, confirming `visual-plan`'s "use sparingly" guidance is the
   real operative constraint, not a fluke.

**New, not in D120's seed list:** two text-collision bugs (a CHECK annotation's caption printed
directly over its own block's headline; the caption band printed over a dense `SEQUENCE_DIAGRAM`'s
last message) -- exactly the risk T18C's own scope notes flagged and left unchecked. And a
planning-choice gap: the topic phrased specifically to force `ARRAY_GRID` never got it across any
of its three segments.

**No code changed in T18D itself** -- `git diff` against `core/`, `rendering/`, `adapters/`,
`interfaces/` stayed empty the whole session, confirmed before this checkpoint; `pytest` still
640 passed / 1 skipped, untouched.

**Immediately after, same session: the user watched all six videos directly** and raised four
complaints `t18d_catalog.md` didn't cover -- worse and slower than T18A's output, `GRAPH_DIAGRAM`
reading as "random lines pointing to nothing," no topic-specific visual freshness (every video
converges on the same couple of generic blocks), and annotations appearing seemingly at random.
**Dispatched a fresh Opus-model agent** (no access to this session's own diagnosis, explicit user
instruction to "use opus") to investigate independently against the real template code and real
render timings. All four confirmed, each traced to a specific, cited cause:
- Edge lines anchor to the node div's center, not the visible marker circle (label/caption height
  pushes the true circle 40-50px below where every line actually terminates) -- and every edge
  draws at node-0's own start time regardless of which two nodes it connects. Together, "random
  lines pointing to nothing," explained structurally, not just observed.
- Across the six renders' 26 content blocks, `TEXT_PANEL`/`STAT_CALLOUT` (the two most generic,
  content-agnostic types) accounted for 31%; `TIMELINE` rendered **zero** times, `CODE_DIFF` and
  `ARRAY_GRID` once each -- traced to `plan_visuals`'s own guidance table biasing toward the
  generic types plus an anti-repetition rule that only forces *alternation*, never a match to the
  actual topic.
- All 20 real annotations across the matrix had `target_item_index=null` -- traced to `plan_
  visuals` asking for an item index before any block has content to index into; the model can only
  ever answer null honestly. Not a scarcity problem (T18D's own framing) so much as a wiring
  problem: the decision runs at a point in the pipeline that structurally cannot make it.
- A ~216 second silent gap between two LLM calls in `t18d-timeline`'s own render, with the actual
  render stage running at or above the T18B-era throughput baseline the whole time -- the render
  system did not get slower; something in the LLM-call layer (likely retry/backoff stacking,
  unlogged) did, compounded by T18C roughly doubling `fill_block` call count per video.

**T18E's real scope (replacing its old "not yet scoped" placeholder) is this analysis's 8-item
list, narrowed to the 6 the user chose to build in one session** (items 7-8 -- a real layered-
layout rewrite for `GRAPH_DIAGRAM`, and payload-driven block *variants* as the actual fix for
"everything looks the same" -- explicitly deferred, per the analysis's own recommendation not to
attempt them before the smaller fixes land). Full sub-part breakdown: `tasks.md`'s T18E entry.

**A seventh part was added mid-scoping, on a direct follow-up request to parallelize the pipeline
as a whole.** Reading the actual node code (not guessing) found two real sequential-when-
avoidable spots: `author_scene`'s per-block `fill_block` calls run in a plain list comprehension
(sequential despite being fully independent -- for the common two-block `SPLIT_HORIZONTAL` case,
pure waste), and `scripting.py::write_narration`'s per-segment loop, which is sequential *by a
documented prior decision* -- its own docstring cites D47 directly: "no measured reason yet to
add node-level concurrency." **D47 is reopened here, explicitly, not silently worked around** --
the same `asyncio.Semaphore` that makes the first fix safe already exists for narration calls too,
so nothing about issuing them concurrently is less safe than one at a time, only faster. What
stays firmly out of scope: retuning `AZURE_OPENAI_MAX_CONCURRENCY`, `RENDER_MAX_CONCURRENCY`, or
`FRAME_BUDGET` -- every one of those has a documented history (D16, D47, D69, D99) of a guessed
number being wrong once someone actually measured it, and this task's own E5 (per-node timing +
retry logging, newly added specifically because of the 216s stall above) is what a future task
would need before touching any of them for real.

**Not built this session, deliberately.** The user chose to checkpoint the scope rather than
build T18E immediately, planning a fresh session next time. `tasks.md`'s T18E entry now carries
the real scope so that session's `/build-task T18E` has something real to read instead of a
placeholder.

## 2026-08-31 · T18E

### D122 -- T18E built (E1-E7 plus a bounded E2.4), verified against three real renders, one new
gap found and fixed live, three more recorded for a future task

**Scope note, decided at plan-approval time, not mid-build:** the approved plan was D121's
six items (E1-E6) plus E7 (parallelization), **plus a bounded slice of the deferred analysis
item 7** -- the user asked directly whether item 7/8 (the two things D121 explicitly deferred)
should be pulled forward, since item 7 is what actually fixes the confirmed `GRAPH_DIAGRAM`
node-overlap bug that nothing in E1-E7 as originally scoped touched. Answer: an
aspect-ratio-aware fallback layout for the compact `SPLIT_HORIZONTAL` canvas (E2.4) -- bounded,
because T18D's own isolation result said the bug was wrong-shape-canvas, not general layout
quality, so the cheap fix matched the evidence. A full layered/rank-based layout (item 7 proper)
and payload-driven block variants (item 8) both stay deferred, item 8 now explicitly pending
E4's effect on the block-choice distribution that motivated it.

**What shipped, in one line each:** E1 moved annotation authoring out of `plan_visuals` into a
new `core/graph/nodes/annotation_author.py`, run from `author_scene` after every block is filled
(`core/annotation_plan_schema.py`, `core/block_items.py`, new pack
`annotation-authoring/1.0`) -- `target_item_index`/`anchor_phrase` are now required, not
nullable, and `rendering/annotations.py` drops rather than guesses at anything that doesn't
resolve. E2 fixed `GRAPH_DIAGRAM` edge anchoring (measured marker-circle center, not the node
div's CSS center), added both-endpoint gating, and arrowheads; E2.4 (above) added the
compact-canvas fallback layout in the same template. E3 gave `GraphEdge` an optional `label`.
E4 added `core/block_triggers.py` and one bounded re-ask in `plan_visuals` when a segment's
narration clearly calls for an unused block type. E5 added `core/graph/node_timing.py` (wraps
every pipeline node) and a `before_sleep` retry-logging callback on the Azure adapter. E6 added
`hfAnnotationPlace` to `_annotations.html`, replacing three ad hoc fixed offsets with a
container-bounded placement. E7 made `author_scene`'s per-block fills and `write_narration`'s
per-segment calls concurrent via `asyncio.gather`, reopening D47 on the user's own instruction.

**A real bug found by this session's own `project-reviewer` review, before any render:**
`_block_graph_diagram.html`'s edge-label lookup used a separately-incremented "labelled-only"
counter in the script while the markup indexed labels by each edge's overall position in
`payload.edges` -- the two only agreed when every labelled edge preceded every unlabelled one.
Fixed to use the same overall index (`i`, matching the markup's `loop.index0`) on both sides;
`tests/test_graph_diagram_edges.py` was reordered (unlabelled edge first) specifically to make
this class of bug fail loudly rather than passing by coincidence.

**A real concurrency assumption was wrong, caught by the offline test suite, not reasoning about
it.** The original plan assumed `author_scene`'s two per-segment LLM calls (fill, then annotate)
would stay contiguous in a shared `FakeLLMProvider` queue because nothing in the fakes
themselves truly suspends. That held for a single segment's own internal `asyncio.gather`, but
`test_graph_pipeline.py`/`test_graph_resume.py` both use a real `AsyncSqliteSaver` checkpointer,
whose genuine I/O gives each segment's `Send` task a real suspension point -- confirmed live by
`FakeLLMProvider` running out of queued responses mid-run. Fix: `tests/graph_pipeline_fixtures.py
::PhaseQueueLLMProvider`, a `FakeLLMProvider` subclass used only by the checkpointer-backed
graph-level tests, matching a queued response by type rather than strict position.
`FakeLLMProvider`'s own strict-FIFO contract (deliberately tested by `test_fake_providers.py`)
was left untouched -- the fix is additive and narrowly scoped, not a change to shared test
infrastructure other tests rely on.

**Verification matched the plan's own DoD: three real `RUNTIME_ENV=azure` renders**
(`t18e-array-grid`, `t18e-timeline`, `t18e-graph-single`, mirroring T18D's own topics for direct
comparison), Blob-synced first (`annotation-authoring/1.0`, `scene-authoring/1.4`,
`visual-plan/1.2` were missing from Blob, same recurring drift D107/T18D already hit), each
watched via targeted frame extraction against the exact frames T18D's catalog cited. Confirmed
live, not just offline: E1's annotations resolve to real items (a cursor's arrow lands on a real
node's marker circle); E5's retry logging fired for real (`APITimeoutError`, one render); E2's
edge anchoring and arrowheads render cleanly against an authored-position graph; E2.4's fallback
layout genuinely separates nodes in a real 5-node compact canvas (the confirmed T18D bug is
gone); E3's edge labels render on a real weighted Dijkstra graph.

**One more real gap found live, and fixed in-session rather than merely recorded:** none of the
three renders showed a single `core/graph/node_timing.py` "node ... started" log line -- only
the Azure adapter's `WARNING`-level retry line appeared. Python's own logging module drops
`INFO`-level records by default unless something calls `logging.basicConfig` (or otherwise
attaches a handler); nothing in this project ever had, because nothing needed `INFO`-level
output before E5. Fixed with one `logging.basicConfig(level=logging.INFO, ...)` call in
`cli.py::main()`, smoke-tested directly (confirmed `timed()`'s log lines print once configured)
rather than re-spending a fourth real render to prove it. Judged in-scope rather than
record-only because it directly contradicted E5's own stated DoD ("the run's own logs show
per-node elapsed times"), unlike the three findings below, which are new problems E1-E7 didn't
promise to solve.

**Three findings recorded, not fixed -- the user's own explicit choice, offered directly rather
than assumed:**
1. **Inter-annotation collision.** Two `CHECK` annotations targeting adjacent lines in the same
   `CODE_PANEL` block rendered with overlapping rings and illegible overlapping captions
   (`t18e-array-grid` seg2). `hfAnnotationPlace` (E6) only keeps one annotation clear of the
   block's own headline and the caption band -- it has no idea another annotation exists.
2. **E4's trigger vocabulary missed a textbook case.** `t18e-timeline`'s own topic (HTTP/1.0 to
   HTTP/3) never rendered `TIMELINE` -- its real narration describes a chronological version
   progression ("HTTP 1.0 makes... HTTP 1.1 keeps... HTTP/2 keeps... HTTP/3 moves...") without
   ever using a generic timeline word ("timeline," "history," "milestone," "decade" -- the whole
   `TRIGGER_VOCABULARY[BlockType.TIMELINE]` set). The scan's own `_MIN_HITS = 2` threshold, added
   to avoid single-generic-word false positives, also filters out a narration that signals
   chronology entirely through domain-specific version numbers rather than vocabulary.
3. **Dense-scene collision in E2.4's own fallback layout.** `t18e-graph-single` seg2 (5 nodes,
   no authored positions, two `GraphEdge` labels, one `WARNING` annotation, all on one compact
   canvas): nodes themselves stayed properly separated (E2.4 holds), but edge labels, node
   captions, and the annotation's own caption all landed in the same crowded region and
   overlapped illegibly. E2.4, E3, and E1/E6 were each individually verified against a simpler
   scene; nothing hardens the interaction between all three at once.

**Every sub-part re-verified after the fixes above; full suite green.** `pytest` --
633 passed, 1 skipped (offline; `local_live`/`azure_live` deselected), unchanged in count logic
from before this session other than new tests added. `ruff check`/`format` clean except one
pre-existing, untouched drift (`.claude/skills/python-pro/SKILL.md`, carried forward, not
T18E's). Both boundary greps empty (the one `core/graph/node_timing.py` hit for "azure" is a
docstring mention of `adapters/azure/llm_provider.py`, verified by AST-level import inspection,
not a real import). No `.py` file over 200 lines.

**Depends:** T18D -- met.

## 2026-09-01/02 · T18G

### D123 -- T18G scoped and built in one session: both of D121's deferred analysis items pulled
forward at the user's own explicit choice, ICON_PANEL scoped to abstract graphics not real photos,
one real 7-minute render found three more bugs, checkpoint's own review found a fourth

**Scoping decision, made explicit before any code was written, not assumed.** The user's own
comprehensive complaint list (5th iteration on video generation: opening segment too long, diagrams
overlapping/open-ended, no per-topic visual freshness, animation/annotations appearing at random
times or places, cursor movement not timed to narration, captions interacting with content, and a
genuine full 7-minute render) mapped almost entirely onto D121's own two explicitly-deferred
analysis items (7: a real `GRAPH_DIAGRAM` layout algorithm; 8: payload-driven block variety) plus
D122's three recorded-not-fixed findings plus two still-open older findings (D120's title-card
staleness, T18C's caption/content-overlap gap). Given the size, the planning session asked the user
directly rather than assuming: whether to include both big deferred items in one session (risking
the same "verified in isolation, not together" failure D122 itself recorded once already), and
separately, whether "images" meant real photo/logo sourcing or abstract/generated graphics.

**Rejected: deferring the two big items again**, which is what was recommended (matching the
project's own established pattern -- T18D/T18E's split existed for exactly this reason). **The user
chose to include both anyway**, explicitly, after the size/risk tradeoff was stated -- not a case of
the recommendation being ignored without acknowledgement; the concern was raised, the user
reaffirmed the full scope, and the session proceeded under that instruction per the project's own
standing policy for exactly this situation.

**Rejected: real photo/logo image sourcing** (a new `interfaces/ImageProvider`-shaped contract plus
local and Azure adapters plus config wiring plus parity tests -- architecturally the same scale as
T29/T30, not a template). **The user chose abstract/generated graphics** once shown the real cost
difference -- `ICON_PANEL` ships as a template-only `BlockType` addition (16 hand-authored inline
SVG icons), no new interface, no new adapter, matching `/newblock`'s existing checklist exactly.

**Reasoning the scoping session used to justify attempting both big items in one sitting anyway,
despite recommending against it:** the two items are structurally independent (a layout algorithm
inside one existing template's script macro; a new block type following an existing, well-worn
registration checklist), so the actual risk was integration-testing gaps, not code conflicts --
mitigated by treating the closing full render as load-bearing verification, not a formality.

**What that render actually found, which is the real vindication (or refutation) of the "attempt
both, verify hard" bet.** One real `RUNTIME_ENV=azure` ~7-minute render, watched frame by frame
(not sampled), found three real bugs no offline test or earlier live-toolchain check had caught:
1. The new layered layout's coordinate mapping used the same max-fraction range for whichever axis
   ended up as the canvas's Y axis as for the X axis -- fine for node markers themselves (E2.4's own
   verification target), wrong once a bottom-rank node's caption text (which extends downward from
   its own point, never accounted for by node-center placement alone) is added to the picture.
   Fixed by tightening the Y-mapped axis's max fraction to 0.62 (from 0.82), asymmetric with the
   X-mapped axis's fuller range, since only Y risks the caption band.
2. An SVG `marker-end` arrowhead is positioned at a path's endpoint geometry and is NOT hidden by
   `stroke-dasharray`/`stroke-dashoffset` -- confirmed live as "an arrowhead pointing at a node that
   hasn't appeared yet," on an edge whose *line* correctly read as not-yet-drawn. This bug predates
   T18G (T18E's own E2 added the arrowheads) but was only ever exercised by a real GRAPH-mode
   diagram where an edge's own reveal time trails its destination node's -- neither T18E's nor
   T18G's own earlier live tests happened to construct that exact timing relationship. Fixed by
   gating the line's own `opacity` at t=0 alongside the dash offset, in both CHAIN and GRAPH mode.
3. `hfAnnotationPlace`'s two-pass fallback (T18G's own F4, built this same session) had a real gap:
   a candidate list with only one entry (CURSOR's own `["tip"]`, unchanged since T18C) never
   actually benefited from collision avoidance -- Pass 1 fails once (no alternative to try), Pass 2
   ("in-bounds is enough") accepted the *same* overlapping position right back. A CHECK and a CURSOR
   on the same `GRAPH_DIAGRAM` node visibly collided in the real render. Fixed with a vertical
   nudge-search (offsets of increasing magnitude, both directions) tried per candidate before moving
   to the next side or giving up -- confirmed live afterward: the second-placed annotation moved
   to a genuinely clear position instead of stacking.

Each of the three was re-verified against a hand-built reproduction of the exact scene shape that
showed it broken (not just re-running the same full render a second time, which would have cost
another ~13 minutes and ~$0.10 for marginal new information once the specific failure was already
isolated).

**A fourth finding came from `project-reviewer`'s own close-out pass, not from watching anything:**
the two shrink-to-fit height formulas F7 added (`_block_sequence_diagram.html`'s `row_h`,
`_block_array_grid.html`'s vertical `v_cell_h`) had no floor -- a badly-oversized LLM item count
(unenforceable at the schema level, `core/strict_schema.py`'s own documented limit) could shrink the
computed height to zero or negative, which a browser silently ignores on an inline style, reverting
to the pre-F7 unbounded-growth bug rather than degrading gracefully. Fixed with a `max(computed,
floor)` clamp before the existing `min(base, ...)`. The review's own residual note, recorded not
chased further (diminishing returns against an already-narrow exposure): the floor stops a single
row from collapsing, but total content height can still exceed the caption-band budget once item
count is far enough past the advisory schema range that `floor * count` alone exceeds it.

**Known residual, not fixed, flagged rather than silently left implicit:** CURSOR's `"tip"` position
targets a `GRAPH_DIAGRAM` node's whole div (marker+label+caption stack) -- fine for a node whose
label is short and centered, but on a captioned node the div's geometric center can land on the
label text rather than the marker circle. This is a distinct, narrower issue from the collision-
avoidance bug above (which is genuinely fixed) -- it is about *which point* a single annotation
targets, not about two annotations fighting over one point. Left for whoever next touches annotation
placement; the fix would need `_ANNOTATION_TARGET_SUFFIX` to vary by annotation type as well as
block type, not just block type, which is a real (if small) structural change, not a one-line one.

**Verification, full account:** `pytest` -- 653 passed, 1 skipped offline; `ruff check`/`format`
clean except the same pre-existing, untouched `.claude/skills/python-pro/SKILL.md` drift T18E's own
checkpoint already carried forward. Both boundary greps empty. No `.py` file over 200 lines. Two
`project-reviewer` passes (mid-build against the working diff, and a final pass against the actual
committed commit `4f10ae7`) both came back clean modulo the one floor-clamp finding, which was fixed
between the two passes and confirmed present and correct by the second. Real-toolchain verification:
targeted `hyperframes check` live sweeps for every new/changed block combination (GRAPH_DIAGRAM
diamond/cycle topologies in both layouts, TITLE with/without key_terms, ICON_PANEL at all three
tiers, dense SEQUENCE_DIAGRAM/ARRAY_GRID at the guidance's own stated maximums, the two-annotation
collision reproduction), plus the one full real render described above.

**Depends:** T18E -- met.
