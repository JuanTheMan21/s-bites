# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-22 · after T6_

---

## Where we are

Iteration 1 is one task from done. The contracts exist, the domain vocabulary exists, the tier
resolver computes, and as of T6 there is a **test foundation**: 196 tests, six in-memory fakes,
and the resolver at 100% branch coverage. `adapters/`, `rendering/`, `mux/` and `runtime_skills/`
are still empty.

**Done:** T1 (scaffold), T2 (operating system), T3 (six interfaces), T4 (domain models),
T5 (tier resolver), T6 (test foundation)
**Next:** T7 — runtime skill registry. **The last task before Azure.**

## What T6 produced

196 passing tests, up from 103.

| File | Holds |
|---|---|
| `tests/fakes/failure_injection.py` | `FailureInjector` — `fail_next(method, exc)`, inherited by all six fakes |
| `tests/fakes/{llm_provider,tts_provider,storage,skill_registry,job_queue,render_backend}.py` | One fake per contract, 21 async methods total |
| `tests/fakes/__init__.py` | Re-exports, and the parity rule stated in the docstring |
| `tests/conftest.py` | Six function-scoped fixtures: `fake_llm`, `fake_tts`, `fake_storage`, `fake_skills`, `fake_queue`, `fake_render` |
| `tests/segment_examples.py` | `a_segment()`, `SEVEN_MINUTE_OUTLINE`, `seven_minute_segments()` — shared, mirroring `tests/slot_examples.py` |
| `tests/test_fakes.py` | Conformance: signature equality, async-ness, AST scans |
| `tests/test_fake_providers.py` · `test_fake_storage.py` · `test_fake_execution.py` | Semantics, per fake |
| `tests/test_tier_resolver.py` · `test_frame_budget.py` | The resolver at full branch coverage |
| `pyproject.toml` | `branch = true` under `[tool.coverage.run]` |

**Verify the DoD at any time** — both files must read 100% with an empty Missing column:

```bash
.venv/Scripts/python.exe -m pytest --cov=core.tier_resolver --cov=core.frame_budget \
  --cov-report=term-missing
```

`--cov-branch` is no longer needed; `branch = true` is configured (D42).

### The fakes, in one paragraph

They are **adapters**, held to the standard `adapter-parity` applies to the real ones at T13
(D37): no vendor imports, errors only from `interfaces/errors.py`, and semantics matching the
contract rather than merely the signature. Every one can be made to fail —
`queue.fail_next("dequeue", RateLimited("throttled"))` — which is the only way T14's retry
classifier can execute its own error paths offline. `FakeTTSProvider` writes a real WAV and
derives the returned duration from the file (D38); `ffprobe` confirms a 9000ms synthesis as
`duration=9.000000`, so T10's DoD is already satisfiable offline. `FakeStorage` and
`FakeJobQueue` enforce two documented preconditions an in-process implementation would otherwise
hide (D39), which **sets the spec T11 and T34 must match.**

## Next task: T7 — Runtime skill registry

Versioned prompt packs the *pipeline* loads at runtime, so the system starts from accumulated
knowledge rather than a cold prompt. **DoD: four packs load through the interface; pack content
is data, not code.** Depends on T3 only — nothing blocks it.

Most of the surface already exists:

- **`interfaces/skill_registry.py` is written.** `SkillPack` (a pydantic model: `name`,
  `version`, `content`, `metadata`) and three abstract methods — `load(name, version=None)`,
  `versions(name)`, `list_packs()`. Do not change the contract to suit the implementation.
- **`tests/fakes/skill_registry.py` is the reference semantics.** It already encodes the
  asymmetry the contract specifies and T7 must reproduce: `load` raises `SkillPackNotFound` for
  an unknown pack *or* an unknown version, while `versions` returns an **empty list** and never
  raises, because that is the question you ask before committing to a pack.
- **`runtime_skills/` exists and is empty.** T7 fills it. Note it is *not* `.claude/skills/` —
  different audience, and CLAUDE.md is emphatic about the distinction.
- The registry goes behind the interface now and gains a Blob-backed implementation at **T11**,
  so the disk adapter must not leak filesystem assumptions into anything above it.

Three things worth knowing before starting:

1. **`version_key` in the fake is a promise T7 has to keep (D41).** `SkillRegistry.versions`
   promises "newest first", and a string sort puts `2.10` below `2.9`. The fake defines a
   numeric-aware rule; the real registry must adopt it or replace both. The two only diverge
   once a pack has a second version, which is late and quiet. **This is T7's to close.**
2. **"Pack content is data, not code" is the load-bearing half of the DoD.** The `SkillPack`
   docstring already says it: content is interpolated into a prompt and nothing else — never
   evaluated, never imported, never a template that can reach back into the process. A pack
   format that needs `eval`, or a Jinja template with access to globals, fails this DoD.
3. **Which four packs** is not specified anywhere. The pipeline's four LLM-facing steps are
   outline (T15), scripting (T15), scene authoring (T16), and — plausibly — a shared house-style
   pack. Decide it in plan mode; it determines what T15 and T16 can ask for.

## Environment state

| | |
|---|---|
| Models | Opus plans, Sonnet builds and reviews — `.claude/settings.json`, `build-task.md` frontmatter, agent files |
| `RUNTIME_ENV` | `local` in `.env.example`; **flips to `azure` at T8** (D25) |
| `.env` | **Still missing.** Copy `.env.example` before any Azure task — the session hook says so at each start |
| Python | 3.11.0, venv at `.venv/`. Use `.venv/Scripts/python.exe` explicitly |
| Toolchain | pydantic 2.13.4, pytest 9.1.1, pytest-asyncio 1.4.0, pytest-cov 7.1.0, coverage 7.15.4, ruff 0.16.4 |
| Node | 24.16.0 · ffmpeg 8.1.1 on PATH (and `ffprobe`, which T6 used to verify the TTS fake) |
| Azure | PAYG, $200/30-day credit. **Nothing provisioned** — that is T8 |
| Git | on `master`. **T4, T5 and T6 committed together** — see the commit for why |
| RepoWise | CLI on PATH and registered in `.mcp.json` |

## Before the next session

Nothing blocks T7 — it is a registry and four text files, entirely offline.

```bash
az login                    # required by the Azure MCP server, and by T8
```

**T8 is the real deadline, and T7 is the last thing standing before it.** Nothing past T7 moves
without a resource group, a model deployment, a Speech resource, a storage account, and a
filled-in `.env`. T8's DoD deliberately demands a raw completion and a raw TTS call from the
command line *before* any adapter code, because a subscription with zero TPM quota fails silently
and looks like an adapter bug for hours.

## Known gaps and open questions

**New in T6:**

- **The fake and the real skill registry must agree on version ordering (D41). T7 owns it.**
- **The fakes may be stricter than the real Azure adapters** on the two enforced preconditions
  (D39). That is the cheap direction to be wrong in — a false failure at T11 is visible
  immediately — but if a real adapter legitimately accepts something `check_key` rejects, the
  fake is what changes, and the reasoning goes in the decision log.
- **No coverage gate exists (D42).** Coverage can decay between checkpoints without anything
  failing. `/checkpoint` re-runs the command; the resolver is the only module it is claimed for.
- **`test_signatures_match_the_contract_exactly` compares annotation objects.** Two constraints
  follow, and both produce confusing failures: no fake may use `from __future__ import
  annotations`, and a fake must import the contract's own `TypeVar` rather than declaring one.
- **`FakeRenderBackend.render` writes placeholder bytes, not a real MP4.** A valid MP4 needs
  ffmpeg and an offline fake must not shell out to a binary. **T18's mux work must run against
  the real local adapter** — this fake proves call plumbing, not media validity.

**Carried forward:**

- **`FRAME_BUDGET` is mistuned and cannot be fixed yet** (D32). 600 frames at 24fps buys 25s of
  Tier-2 animation against a 28s average segment, so Tier 2 lands on the *shortest* segments,
  not the most important — both `CRITICAL` segments demote. **Owned by T16**, once real measured
  durations exist. `/tiers` is the cheap tuning loop. Do not tune it against a fixture.
- **Below ~333ms at 24fps, Tier 2 is *cheaper* than Tier 1.** Left truthful on purpose; a floor
  would make `frame_cost` lie about the cost model. Now pinned by a test. Only live if TTS ever
  emits a sub-second clip.
- **`core/tier_resolver.py` is at 198 of 200 lines.** `/newintent` step 5 adds a line to
  `TIER_SUPPORT`, so **the seventh intent forces a split.** Split by responsibility.
- **The strict-mode keyword list is the conservative set.** **Check live behaviour at T8** before
  loosening it. Nothing has yet been validated against a real Azure call.
- **`Segment.slots` is an untyped dict** (D29). Discriminated union deferred; needs `const`.
  **Revisit at T24.**
- **Six intents may prove too few.** Only visible at T18. `/newintent`, not a redesign — but see
  the 198-line note.
- **No family for "our own code judged this invalid" errors.** `CompositionInvalid` inherits
  `Exception` directly (D23). **Decide at T17.**
- **`StructuredOutputError` cannot say "retry, but bounded."** **T14 owns this**, via
  `QueuedJob.attempt` — which now survives a requeue in the fake, so it is testable.
- **A wrong endpoint URL looks retryable** (D24). T8's command-line verification is the mitigation.
- **Scope: 35 tasks across 8 iterations.** Worth confirming with your manager whether RAG
  (iteration 6) or frontend polish (iteration 5) matters more *before* iteration 4.
- **HyperFrames is not installed.** Needed by T17. `npx hyperframes doctor` when we get there.

## Gotchas worth remembering

- **A validation rule tested on one method of six is tested nowhere.** `project-reviewer` caught
  `FakeStorage.exists` skipping `check_key` because the test only parametrised `put_bytes`. When
  a rule applies across an interface, parametrise the test across the interface.
- **`project-reviewer` reported a test count that was wrong** (172 against an actual 196). Its
  reasoning about the code was sound and its two findings were real, but **re-run the numbers
  yourself** rather than quoting an agent's.
- The boundary hook blocks vendor imports in `core/`. If it fires, move the code into an adapter.
- The hooks fire on `Write|Edit`, **not on Bash heredocs.** Use `Write` for `.py` files — it is
  what runs ruff, the 200-line check, and the boundary check. The 200-line hook caught
  `test_fake_services.py` at 236 and forced the split into `test_fake_storage.py` and
  `test_fake_execution.py`. **Let it.**
- **CLAUDE.md's boundary greps are plain text searches.** `core/tier_resolver.py` and
  `core/frame_budget.py` both name `FRAME_BUDGET` and `FPS` in prose to say they do *not* read
  them. Verify imports with AST, not text — which is what `tests/test_fakes.py` does.
- Coverage runs write a `.coverage` file to wherever they are run from. It is gitignored as of
  T6; before that it was not, and one nearly got committed.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
