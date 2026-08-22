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
