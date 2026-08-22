# Task Backlog

35 tasks across 8 iterations. **One task per session.** Descriptions are deliberately high-level —
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

### T4 — Domain models · `todo`
`Segment`, `VisualIntent` (closed enum), `Tier`, `VideoJob`, plus the per-intent pydantic slot
schemas the LLM fills. These same models serve LLM structured output, internal state, and later the
API contract — one definition, three uses.
**DoD:** models cover every visual intent; schemas satisfy Azure strict-mode constraints.
**Depends:** T3
**Flagged in T3 planning — target length must be a parameter.** `VideoJob` carries
`target_duration_ms`; nothing may hardcode 7 minutes or 15 segments. Segment count is *derived*
(~28s of narration each), so a 10-minute request yields ~21 segments on its own.

### T5 — Tier resolver · `todo`
The pure function at the heart of the render budget: importance-ranked segments in, tier
assignments out, under a global frame budget. No I/O, no LLM, no clock. The one piece of this
system with no excuse for external dependencies.
**DoD:** `core/tier_resolver.py` imports nothing but stdlib and `core.models`.
**Depends:** T4
**Flagged in T3 planning — the frame budget is an argument, not a constant.** The caller scales it
with `target_duration_ms` under a hard ceiling. `FRAME_BUDGET` is really a *render-time* budget
(D16: 1.7-2.7 frames/sec), so linear scaling with no cap turns a 20-minute video into a 20-minute
render, and no scaling at all spreads 600 frames so thin that everything lands on Tier 0.

### T6 — Test foundation · `todo`
Thorough unit tests for the tier resolver — budget exhaustion, ties, degenerate inputs, and a
realistic 7-minute case asserting all three tiers appear — plus in-memory fakes for all six
interfaces so every later task can be tested without network.
**DoD:** `pytest` green; tier resolver at full branch coverage.
**Depends:** T5

### T7 — Runtime skill registry · `todo`
Versioned prompt packs the *pipeline* loads at runtime, so the system starts from accumulated
knowledge rather than a cold prompt. Registry behind an interface; packs on disk locally, in Blob
on Azure, updatable without redeploying code.
**DoD:** four packs load through the interface; pack content is data, not code.
**Depends:** T3

---

## Iteration 2 — Azure provisioning & adapters

### T8 — Azure groundwork · `todo`
Resource group, model deployment, Speech resource on the free tier, storage account, credentials
into `.env`. **Verify non-zero TPM quota before writing any adapter code** — this is the step that
fails silently on a mis-provisioned subscription.
**DoD:** a raw completion and a raw TTS call both succeed from the command line.
**Depends:** T1

### T9 — Azure LLM adapter · `todo`
Azure OpenAI behind `LLMProvider`, with strict JSON-schema structured output, retry/backoff on rate
limits, and a concurrency bound matched to deployment throughput. All resilience lives here, never
in `core/`.
**DoD:** returns validated model instances; survives an induced rate-limit response.
**Depends:** T3, T8

### T10 — TTS adapters · `todo`
Azure Speech (primary) and Kokoro (offline), both returning audio plus **measured** duration. That
measured duration is what every downstream timing decision depends on.
**DoD:** both satisfy `TTSProvider`; durations match `ffprobe` within tolerance.
**Depends:** T3, T8

### T11 — Storage adapters · `todo`
Blob and local disk behind `Storage`, plus the Blob-backed skill registry from T7.
**DoD:** identical behavior for put/get/url across both; skill packs load from Blob.
**Depends:** T3, T7, T8

### T12 — Local adapters & Azure stubs · `todo`
Ollama, the asyncio-pool queue, the Playwright + HyperFrames render backend. Service Bus and
Container Apps get signature-matched stubs that raise clearly — stubs are what make the interface
boundary reviewable rather than aspirational.
**DoD:** local stack complete; stubs match signatures exactly.
**Depends:** T3

### T13 — Config resolver & parity · `todo`
`config.py` — the single module permitted to name concrete classes — plus parity tests proving both
implementations of each interface agree on signature and semantics.
**DoD:** flipping `RUNTIME_ENV` swaps every adapter with no change in `core/`.
**Depends:** T9, T10, T11, T12

---

## Iteration 3 — Pipeline & rendering

### T14 — LangGraph skeleton · `todo`
Graph state, checkpointing, per-segment fan-out, and resume-after-failure. Scoped strictly to
`core/graph/`; nodes call interfaces like everything else.
**DoD:** a killed run resumes without repeating completed segments.
**Depends:** T6, T13

### T15 — Outline & scripting nodes · `todo`
Topic to segments to narration, driven by the runtime skill packs. Produces roughly 15 segments for
a 7-minute target.
**DoD:** structured output validates on every segment; skill packs demonstrably change behavior.
**Depends:** T14

### T16 — TTS, tiering & scene authoring · `todo`
The ordering-critical stretch: narrate, measure, assign tiers against the real durations, then fill
scene slots. Scene authoring takes measured duration as a required input so it cannot run early.
**DoD:** timing attributes derive only from measured audio; tier spread covers all three tiers.
**Depends:** T15

### T17 — The three renderers · `todo`
Static screenshot, multi-state reveal with crossfade, and full HyperFrames animation — one module
per tier, with composition linting before render.
**DoD:** each tier produces a valid clip; invalid compositions are caught before rendering.
**Depends:** T16

### T18 — Mux & CLI · `todo`
Per-segment audio mux, then concat, then the CLI entrypoint. **This task produces the first
complete video.**
**DoD:** `python cli.py "<topic>"` yields a playable ~7-min MP4 on both stacks; no drift.
**Depends:** T17

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
on the developer machine.
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
