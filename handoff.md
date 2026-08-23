# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-23 · after T14_

---

## Where we are

**The pipeline has a skeleton.** `core/graph/` now drives the six interfaces as an actual
LangGraph: state, a checkpointer, `Send`-based per-segment fan-out, and a resume story that
survives a killed process — verified, not assumed, against the installed
`langgraph==1.2.11`/`langgraph-checkpoint-sqlite==3.1.1`. Iteration 3 (Pipeline & rendering) is
now underway; T15-T18 fill in the real outline, scripting, TTS/tiering/scene-authoring, and
rendering logic that this skeleton's placeholder nodes stand in for today.

**Done:** T1-T9, T11-T14 (T10 stays `in-progress`, unclaimed — see below).
**Next:** **T15 — Outline & scripting nodes.** Depends on T14 (done).

## What T14 produced

`core/graph/` — the sole place `langgraph` may be imported, all files well under 200 lines:

| File | Holds |
|---|---|
| `context.py` | `GraphContext` — frozen dataclass, 5 fields (`llm`, `tts`, `storage`, `skills`, `render`, `working_dir`). Its own type, not `config.Adapters` — see D66 |
| `state.py` | `GraphState` (`job: VideoJob`, `segments: Annotated[dict[int, Segment], merge_segments]`), `SegmentTask` (the `Send` payload) |
| `retry_policy.py` | `build_retry_policies()` — two `RetryPolicy` objects classifying every `interfaces/errors.py` exception. Read this file's docstring before touching it — see D67 below, it documents a real LangGraph limitation, not a design choice |
| `nodes/plan.py` | `plan_segments` — deterministic placeholder segments, no LLM call. T15 replaces its *body*, not the graph shape (D70) |
| `nodes/synthesize.py` | `synthesize_segment` — the one node doing real interface work: `TTSProvider.synthesize` then `Storage.put_file`, key `{job_id}/segments/{index}/narration.wav` |
| `nodes/finalize.py` | `finalize` — folds `segments` back onto `VideoJob`, sets `SUCCEEDED` |
| `pipeline.py` | `build_graph(checkpointer)` — wires `START → plan_segments → (Send fan-out) → synthesize_segment → finalize → END` |

Plus `scripts/measure_segment_concurrency.py` (outside `core/`, closes D47 — see below) and three
new test files (`tests/test_graph_pipeline.py`, `test_graph_state.py`, `test_retry_policy.py`).

**Two `project-reviewer` passes this session, both found real issues in the same file
(`retry_policy.py`), both fixed (D67 has the full account):**
1. First pass: the module wrongly claimed `RetryPolicy` only supports one shared `max_attempts`
   per node, so `StructuredOutputError` never actually got the tighter cap D24 called for. Fixed
   with `build_retry_policies()` returning two independently-capped policies.
2. A second, independent fresh pass on the corrected diff — per this project's own standing
   lesson (D57/D62) that a review scoped to one named fix can still miss a sibling bug — found
   that the *fix's own* docstring overclaimed "independent per exception type" caps. LangGraph
   actually shares one attempt counter across a whole node invocation, so a transient failure
   before a `StructuredOutputError` silently shrinks the latter's effective budget. Fixed: the
   docstring now states this precisely, and it's pinned by a regression test
   (`test_a_prior_transient_failure_eats_into_the_bounded_policys_own_budget`) rather than left as
   prose alone.

**`D24`'s `StructuredOutputError` "retry, but bounded" item is now real, but not fully closed.**
`build_retry_policies()` gives it its own tighter node-level cap — that part works, and is
correctly isolated as long as a node's failures stay within one classified family per invocation
(not guaranteed once T15's LLM-calling node exists; the retry_policy.py docstring tells that node
what to do instead if it needs true isolation: an in-node retry loop around just the
`LLMProvider.generate` call). What's still open is the *cross-requeue* half D24 literally named:
capping retries using `QueuedJob.attempt`, which survives a job being requeued, not just a
checkpoint resume. `GraphContext` deliberately excludes `JobQueue` (D66), so nothing in
`core/graph/` can enforce that. **Whichever future task builds the runner that calls
`JobQueue.fail(..., requeue=True)` owns this** — without it, a job whose LLM output consistently
fails schema validation (a genuine prompt/schema bug, not sampling noise) will retry, get
requeued, retry, get requeued, indefinitely.

**D47's disk-I/O-under-concurrency question is measured, not carried forward a fourth time.**
`scripts/measure_segment_concurrency.py` (run manually: `python -m
scripts.measure_segment_concurrency`) pushes 15 segments through the real graph against real
`DiskStorage`. Observed **0.417s total, 27.8ms/segment**. The finding: synchronous I/O *does*
serialize concurrent segments in this skeleton (nothing in `synthesize_segment` actually yields
control), confirming D47's concern rather than disproving it — but at narration-WAV file sizes the
absolute cost is small enough not to matter. **Re-measure at T18**, once real rendered MP4
segments (tens of MB, not KB) move through the same `Storage.put_file` pattern.

**Resume mechanics rely on LangGraph's own pending-writes durability**, confirmed empirically
rather than assumed from docs (D68): `ainvoke(None, config, context=..., durability="sync")`
against a real file-backed `AsyncSqliteSaver` resumes only the failed segment's task; sibling
segments that already completed in the same superstep are not recomputed. This is what the T14
DoD test (`test_a_killed_run_resumes_without_repeating_completed_segments`) exercises directly.

## Next task: T15 — Outline & scripting nodes

Topic to segments to narration, driven by the runtime skill packs. Depends on T14 (done).

**What T15 should know going in:**

- **`core/graph/nodes/plan.py::plan_segments` is the node whose *body* T15 replaces** — same node
  name, same position in the graph, same return shape (`{"segments": {index: Segment}}`). Call
  `core.outline_schema.Outline` through `context.llm.generate(...)` in place of the deterministic
  placeholder loop; the graph shape in `core/graph/pipeline.py` doesn't need to change.
- **`core/graph/retry_policy.py::build_retry_policies()` is ready to attach** to T15's node via
  `add_node(..., retry_policy=build_retry_policies())` — no new classification needed. But read
  the module's docstring first: if this node can raise both a transient error (`ProviderUnavailable`
  etc.) and `StructuredOutputError` across its own retries within one invocation, the two-policy
  split does **not** give `StructuredOutputError` an isolated budget (D67) — a prior transient
  failure eats into it. If that isolation matters, wrap the `LLMProvider.generate` call in its own
  explicit, locally-counted retry loop instead of relying on the graph-level policy alone.
  **This task does not have to solve that** — just don't assume the two-policy split already did.
- **The cross-requeue attempt cap (`QueuedJob.attempt`) is still not T15's job either** — it
  belongs to whichever task builds the runner driving `JobQueue`. Leave it open.
- `core/graph/context.py::GraphContext` already carries `llm` — nothing to add there for T15.
- Segment audio's artifact key convention is `{job_id}/segments/{index}/narration.wav`
  (`core/graph/nodes/synthesize.py::SEGMENT_AUDIO_KEY`) — keep using it rather than inventing a
  second layout when T16 builds on top of T15's segments.
- T7's carried note is still live and now T15's to close: **the `outline` pack may need a `1.1`**
  — it's never been sent to a real model, and the DoD's "skill packs demonstrably change
  behavior" is the first real test of it.
- T4's flag still applies: segment count comes from `VideoJob.segment_count`
  (`target_duration_ms`-derived), never a literal `15`.

**Verify at any time:**

```bash
pytest                        # full suite, offline, no network -- includes tests/test_graph_*.py
ruff check . && ruff format --check .
python -m scripts.measure_segment_concurrency   # manual, real DiskStorage -- see D69
```

## Environment state

| | |
|---|---|
| Models | Opus plans, Sonnet builds and reviews |
| `RUNTIME_ENV` | **`azure`** in both `.env` and `.env.example` (D25) — unchanged this task |
| `.env` | Exists and is filled in. Gitignored. Never commit it. Still not updated with the two T13-added placeholder groups (harmless — `config.py` defaults them to `""`, and T14 doesn't touch `config.py` at all) |
| Azure sub | `d4a261bd-760c-41bd-9e22-ef58e2329ce0`, `az login` done |
| Azure OpenAI | `skill-bites` (eastus) · deployment `gpt-5.4-mini` 2026-03-17, DataZoneStandard (D49) · api-version `2024-10-21` |
| Azure Speech | `skill-bites-tts` (eastus), S0 (D48) · voice `en-US-AvaMultilingualNeural` |
| Azure Storage | `sbitesartifacts25817` (eastus) · containers `explainer-artifacts`, `runtime-skills` |
| Python | 3.11.0, venv at `.venv/`. Use `.venv/Scripts/python.exe` explicitly |
| Node | 24.16.0 · npm 11.13.0 · ffmpeg/ffprobe 8.1.1 on PATH |
| `langgraph` | **New this task, actually exercised for the first time.** `langgraph==1.2.11`, `langgraph-checkpoint-sqlite==3.1.1` — both already installed in `.venv`, ahead of `requirements.txt`'s `>=0.2.60`/`>=2.0.0` floors from T1. No version bump needed, just noting the gap between floor and installed |
| HyperFrames CLI | Installed — 0.8.10, via `npx hyperframes`. Chrome Headless Shell cached at `~/.cache/hyperframes` |
| Playwright browsers | Installed — both `chromium-1234` *and* `chromium_headless_shell-1234` at `%LOCALAPPDATA%\ms-playwright` |
| Ollama, Kokoro | **Still not installed. Deliberately deferred (D59, reaffirmed D64)**, not forgotten |
| Git | on `master`. **Nothing from T1 onward pushed or committed yet** — every task since T1/T2's two commits is still working-tree state |

## Before the next session

Nothing blocking. T15 is `core/graph/` + `core/` work (the outline/scripting node and its
schemas) against the already-`done` T7 skill packs and T14 graph skeleton; it needs `RUNTIME_ENV`
live only if you want to run it against the real Azure LLM rather than `FakeLLMProvider` — the
offline suite doesn't require that.

## Known gaps and open questions

**New in T14:**

- **The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open** — D24's
  original ask, only half-closed. See "What T14 produced" above; owned by a future runner task,
  not T15.
- **`retry_policy.py`'s two-policy split does not give isolated attempt budgets across mixed
  failure types within one node invocation** (D67) — inert today (no node mixes families yet),
  live risk starting at T15. The module's own docstring tells the next node author what to do if
  it matters for them.
- **D47's measurement (D69) used small WAV files only** — re-measure once T18 moves real rendered
  MP4 segments through `Storage.put_file`.

**Carried forward, unchanged:**

- **The composition-directory-layout assumption is unverified** (`hyperframes_cli.py` assumes one
  composition per directory, named `index.html`). T17 is the first task that generates composition
  files and picks a real layout — check this assumption then.
- **`FRAME_BUDGET` is mistuned and cannot be fixed yet** (D32). Owned by T16, once real measured
  durations exist.
- **The `outline` pack may need a `1.1`.** Now T15's to close directly — see "Next task" above.
- **`core/tier_resolver.py` is at 198 of 200 lines.** The seventh intent forces a split.
- **No coverage gate exists (D42).**
- **`FakeRenderBackend.render` writes placeholder bytes, not a real MP4.** T18's mux work must run
  against the real local adapter, which exists (`PlaywrightHyperFramesRenderBackend`).
- **`Segment.slots` is an untyped dict** (D29). Revisit at T24.
- **No family for "our own code judged this invalid" errors** beyond `CompositionInvalid` itself
  (D23). Decide at T17.
- **Scope: 35 tasks across 8 iterations**, and the local stack's priority is still unsettled (T12's
  rescoping, T13's D64) — worth confirming with your manager before iteration 4.
- **T10 stays `in-progress`, unclaimed.** Ollama/Kokoro still don't exist; no task currently
  builds them.

## Gotchas worth remembering

**New in T14:**

- **The "quality hook autofixes on write" gotcha bit twice more, in a new shape.** Adding an
  import in one `Edit` call and its first use in a later `Edit` call risks the autofix hook
  stripping the "unused" import in between — hit on `pytest` in a test file, `build_retry_policies`
  in `pipeline.py`, and a whole `TypedDict`/`StateGraph`/`START`/`END`/`Runtime` import block in a
  test file, all in this one task. **Always add an import in the same edit as its first use.**
  This is now the third time this exact lesson has been learned the hard way (see T13's handoff);
  it is worth treating as a hard rule, not a reminder.
- **A docstring's factual claim about a third-party library is a claim, not a comment** — verify
  it against the installed library's actual source (or a runnable spike) before writing it down,
  especially when the claim is the *reason* for a design choice. Two separate wrong claims about
  LangGraph's `RetryPolicy` shipped in the same file this session, both caught only because
  `project-reviewer` checked `langgraph/pregel/_retry.py` directly rather than trusting the
  reasoning already in the file.
- **LangGraph's per-node `RetryPolicy` sequence shares one `attempts` counter across the whole
  node invocation** — `Sequence[RetryPolicy]` lets different exception types have different
  `max_attempts`, but does not give each type an isolated budget. A prior failure of one
  classified type spends shared budget that a later, different classified type's cap gets checked
  against. Relevant to any future node whose retryable failures can span more than one family.
- **A real, file-backed `AsyncSqliteSaver` plus `durability="sync"` is what makes a "killed
  process" test meaningful** — the in-memory checkpointer or the default durability setting would
  test something weaker than the DoD actually asks for.

**Carried forward:**

- **Check the *SKU's* quota, not the model's availability** (D49).
- **An SDK that "reports failures as results" can still raise** (D57).
- **Windows path semantics**: a trailing dot is stripped on existence checks but not on directory
  enumeration (D46).
- **A generator raises where it is iterated, not where it is called** — wrap both the call and the
  iteration in one `try`.
- **A validation rule tested on one method of six is tested nowhere** (D39).
- **`project-reviewer` is worth running and worth checking in both directions, and worth running a
  second, independent fresh pass after any non-trivial fix** — this task is the clearest example
  yet in this project's own history: a first pass caught a real bug, and a second pass on the
  *fix* caught a second, different real bug in the same explanation. Re-verifying only the named
  fix would have missed it. **When re-running review after fixes, ask for a fresh full read, not
  just verification of the named fixes** (carried from T13, reconfirmed here in a sharper form).
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
