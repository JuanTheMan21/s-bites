# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-24 · after T16_

---

## Where we are

**The graph is complete from a topic to a fully-planned video.** A job now goes in as a string and
comes out as segments that are outlined, narrated, *measured*, tiered, and scene-authored -- every
field on `core.models.Segment` is populated except by the renderer. Nothing renders yet; that is
T17.

```
START
  → plan_segments                  (T15: outline call + one scripting call per segment)
  → [Send ×N] synthesize_segment   (T14: TTS, sets measured duration_ms)
  → assign_tiers                   (T16: join -- needs ALL durations)
  → [Send ×N] author_scene         (T16: one LLM call per segment, fills slots)
  → finalize
  → END
```

**Done:** T1-T9, T11-T16 (T10 stays `in-progress`, unclaimed -- see below).
**Next:** **T17 — The three renderers.** Depends on T16 (done).

## What T16 produced

| File | Holds |
|---|---|
| `core/graph/nodes/tiering.py` | `assign_tiers` -- the join node. Scales the base budget to the job's length via `scale_frame_budget`, then calls `resolve_tiers`, then writes `tier` back onto every segment. **The first caller either of those two modules has ever had** -- both were built whole at T5/T6 and sat uncalled. |
| `core/graph/nodes/scene_author.py` | `fill_slots(llm, skills, segment, *, duration_ms)` and the `author_scene` node. `duration_ms` is a **required** parameter, which is Invariant 1's structural enforcement -- a caller who has not measured cannot satisfy the signature. |
| `core/graph/pipeline.py` | The second fan-out and the join. `author_scene` registered with `build_transient_retry_policy()` (D73's trap, avoided); `assign_tiers` with **no** retry policy, since its only failure is a `ValueError` a retry cannot fix. |
| `core/graph/context.py` | Gained `frame_budget: int` and `fps: int`, no defaults. The edge-read config `core/frame_budget.py` always anticipated (D77). |
| `scripts/tier_dry_run.py` | **`/tiers`, executable.** Topic → outline → narration → real TTS → tier assignment, then stops. Prints the table, the spread, and every demotion. This is the cheap loop for any future budget or importance tuning. |
| `tests/graph_pipeline_fixtures.py` | Shared setup, split out of `test_graph_pipeline.py` when the resume cases outgrew 200 lines. |
| `tests/test_graph_resume.py` | Both resume cases, including a **new** one for a kill inside the second fan-out. |

Plus `tests/test_tiering_node.py`, `tests/test_scene_author.py`, `tests/test_live_scene_authoring.py`
(`pytest -m live`), and small edits to `core/graph/state.py`, `core/graph/nodes/__init__.py`,
`tests/plan_segments_fixtures.py`, and `scripts/measure_segment_concurrency.py` (which had been
broken since T15 -- it seeded an empty `FakeSkillRegistry`, and `plan_segments` now loads packs).

## What the live runs actually showed

**`FRAME_BUDGET` is now 1400, up from 600 (D78).** D32 predicted Tier 2 would buy *shortness*
rather than importance. The measurement was worse: at 600, real narration produced **T0=0 T1=15
T2=0** -- zero animated scenes, 480 of 600 frames unspent, because no single segment could afford
the ~600-frame step to Tier 2. Real narration runs a **uniform 19-29 seconds per segment**; there
are no short segments, not even title cards. 1400 buys 2 animated scenes (~8-13 min of render at
D16's measured throughput). The curve, measured: 900→1, 1400→2, 2000→3.

**Tier 0 is empty on a typical run, and that is accepted (D79).** A reveal costs 8 frames, so any
budget large enough to animate anything is far more than enough to reveal everything -- Tier 0 is
reachable only when the outline rates a segment `ASIDE`, which the model never did. **The user
decided Tier 0 is a rendering floor, not a target**, so the DoD's "tier spread covers all three
tiers" is recorded as met for Tier 1 and Tier 2 only, not silently claimed in full.

**The `scene-authoring` pack works at `1.0`** -- live-tested for the two intents most likely to leak
markup (`code_walkthrough`, `bullet_list`). No `1.1` needed, same result T15 got for the other packs.

**An `outline` `1.1` was written, measured, and deleted (D80).** It tried to fix the model rating
9 of 15 segments 4-5 and nothing 1. It did not work, so it was not shipped. **The finding is real
and carried forward unfixed:** the outline model rates on merit rather than ranking.

## Next task: T17 — The three renderers

Three capture strategies (static screenshot · multi-state reveal with crossfade · full HyperFrames
animation) plus **six Jinja templates, one per visual intent** (D30). Depends on T16 (done).

**What T17 should know going in:**

- **`Segment.slots` is now really populated**, by `author_scene`, and validated against
  `core.slot_schemas.slot_schema_for(segment.visual_intent)` on the way in. It is stored as an
  untyped `dict[str, Any]` (D29), so validate it back through `slot_schema_for` at the point of
  use. `tests/slot_examples.py` has a realistic payload per intent to render against, and
  `tests/test_scene_author.py` shows the round-trip.
- **Every template still needs its Tier 0 form, and Tier 0 is now *less* likely to be exercised by
  a real run** (D79). That makes it easier to ship a template with a broken static form and not
  notice. Render each template at all three tiers in tests explicitly rather than relying on a
  realistic job to cover them.
- **A typical run is now roughly 2 animated · 13 reveal · 0 static.** Budget render-time
  expectations accordingly: the two Tier-2 scenes are where essentially all the frames go.
- **The composition-directory-layout assumption is still unverified.**
  `adapters/local/hyperframes_cli.py` assumes one composition per directory, named `index.html`.
  **T17 is the first task that generates composition files and picks a real layout** -- check that
  assumption now rather than inheriting it.
- **`FakeRenderBackend.render` writes placeholder bytes, not a real MP4.** T17/T18 work that cares
  about real output must run against `PlaywrightHyperFramesRenderBackend`, which exists and is
  installed.
- **`core/tier_resolver.py` is at 198 of 200 lines.** If T17 registers an intent with no meaningful
  reveal form in `TIER_SUPPORT`, that edit forces a split first.
- **No family exists for "our own code judged this invalid" errors** beyond `CompositionInvalid`
  itself (D23). T17's "invalid compositions are caught before rendering" DoD is where that gets
  decided.

**Verify at any time:**

```bash
pytest                                    # offline, no network -- 501 passed, 1 skipped, 35 deselected
pytest -m live                            # opt-in, needs .env credentials, costs real money
ruff check . && ruff format --check .
PYTHONPATH=. .venv/Scripts/python.exe scripts/tier_dry_run.py "<topic>"   # /tiers, ~$0.05 + 2 min
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # must be empty
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # must be empty
```

> The previous handoff claimed "505 passed". That figure did not reconcile and was wrong when
> written -- nothing was lost. Verified directly this session: every T15 test file still collects
> (`test_plan_segments` 4, `test_plan_segments_retry` 2, `test_skill_prompt` 2,
> `test_structured_retry` 5). 537 tests collected in total. **The numbers above are measured.**

## Environment state

| | |
|---|---|
| Models | Opus plans, Sonnet builds and reviews |
| `RUNTIME_ENV` | **`azure`** in both `.env` and `.env.example` (D25) — unchanged this task |
| `FRAME_BUDGET` | **1400** (was 600) in both `.env` and `.env.example` — see D78 |
| `FPS` | 24, unchanged |
| `.env` | Exists and is filled in. Gitignored. Never commit it. |
| Azure sub | `d4a261bd-760c-41bd-9e22-ef58e2329ce0`, `az login` done |
| Azure OpenAI | `skill-bites` (eastus) · deployment `gpt-5.4-mini` 2026-03-17, DataZoneStandard (D49) · api-version `2024-10-21` |
| Azure Speech | `skill-bites-tts` (eastus), S0 (D48) · voice `en-US-AvaMultilingualNeural` |
| Azure Storage | `sbitesartifacts25817` (eastus) · containers `explainer-artifacts`, `runtime-skills` |
| Python | 3.11.0, venv at `.venv/`. Use `.venv/Scripts/python.exe` explicitly |
| Node | 24.16.0 · npm 11.13.0 · ffmpeg/ffprobe 8.1.1 on PATH |
| `langgraph` | `langgraph==1.2.11`, `langgraph-checkpoint-sqlite==3.1.1`, installed in `.venv` |
| HyperFrames CLI | Installed — 0.8.10, via `npx hyperframes`. Chrome Headless Shell cached at `~/.cache/hyperframes` |
| Playwright browsers | Installed — both `chromium-1234` *and* `chromium_headless_shell-1234` at `%LOCALAPPDATA%\ms-playwright` |
| Ollama, Kokoro | **Still not installed. Deliberately deferred (D59, reaffirmed D64)**, not forgotten |
| Git | on `master`. T1-T14 are committed (4 commits, `dabaccf` latest). **T15 and T16 are uncommitted working-tree state.** There is **no git remote configured**, so nothing has been pushed anywhere and `/push` has nowhere to go until one is added |
| Azure spend | Two live tuning runs plus the live tests this session — roughly $0.15 total. Still no budget alerts configured; check with `/costs` |

## Before the next session

Nothing blocking. T17 is `rendering/` and template work against the real local
`PlaywrightHyperFramesRenderBackend` and the HyperFrames CLI, both installed. It needs
`RUNTIME_ENV=azure` only if you want real slot payloads rather than `tests/slot_examples.py`.

**Worth deciding soon:** two tasks' worth of work (T15 and T16) is uncommitted, and the repo has no
remote, so none of it exists anywhere but this disk. Adding a remote and pushing is a five-minute
job that has been deferred since T1.

## Known gaps and open questions

**New in T16:**

- **The outline model rates importance on merit rather than ranking** (D80). Roughly 60% of
  segments ask for Tier 2 when the budget can afford 2. Not harmful — the resolver demotes
  correctly — but the "ideal" tier is fiction for most segments, and `TierPlan.demoted` is
  correspondingly noisy. A future pack iteration needs a better hypothesis than "ask harder";
  `scripts/tier_dry_run.py` tests one for a few cents.
- **`FRAME_BUDGET=1400` was tuned on exactly one topic.** "SQL injection" produced very uniform
  segment durations. A topic with genuinely short segments would spend the budget differently.
  Re-run `/tiers` on a second topic before treating 1400 as settled.
- **Tier 0 will be empty on most real runs** (D79), which makes it the least-exercised path in
  T17's templates. See the T17 notes above.

**Carried forward, unchanged:**

- **The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open** (D24/D67) —
  owned by whichever future task builds the runner that calls `JobQueue.fail(..., requeue=True)`.
- **The composition-directory-layout assumption is unverified** — T17 owns it now.
- **`core/tier_resolver.py` is at 198 of 200 lines.** The seventh intent forces a split.
- **No coverage gate exists (D42).**
- **`Segment.slots` is an untyped dict** (D29). Revisit at T24.
- **No family for "our own code judged this invalid" errors** beyond `CompositionInvalid` (D23).
  Decide at T17.
- **Scope: 35 tasks across 8 iterations**, and the local stack's priority is still unsettled (T12's
  rescoping, T13's D64) — worth confirming with your manager before iteration 4.
- **T10 stays `in-progress`, unclaimed.** Ollama/Kokoro still don't exist; no task builds them.
- **D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only** — re-measure
  once T18 moves real rendered MP4 segments through `Storage.put_file`.

## Gotchas worth remembering

**New in T16:**

- **A tuning tool that is silently wrong exactly when its own knob is changed is worse than no
  tool.** `scripts/tier_dry_run.py` divided animated frames by a literal `24` instead of the
  configured `fps` — correct at the default, 2.5x wrong at `FPS=60`, in the one line someone reads
  to pick a budget (D81). Caught by the second review pass.
- **A speculative change and the test edit that accommodates it should be separate steps.** The
  `outline` `1.1` was deleted (D80) but the test loosening it required was left behind, where the
  next review correctly showed it had become tautological (D82).
- **A number that lives in `.env` must not also live in a default argument.** `FRAME_BUDGET` had a
  hardcoded `"600"` fallback that survived the retune to 1400. Read it, or fail — do not default.

**Carried forward:**

- **A node-level `RetryPolicy` that also matches an error a node isolates locally defeats that
  isolation, silently** (D73). Any node using `structured_retry.py` registers with
  `build_transient_retry_policy()`. `author_scene` is the second node this applied to.
- **The "quality hook autofixes on write" gotcha: adding an import and its first use in separate
  `Edit` calls lets the hook strip the "unused" import in between.** Bit again this session, on
  `Adapters` in `tier_dry_run.py`. **Always add an import in the same edit as its first use** —
  five sessions running; treat it as a hard rule.
- **`project-reviewer` is worth running, and the *second* fresh full pass is the one that finds the
  bug** — D57, D62, D67, D73, now D82. Ask for a fresh full read, never a check of named fixes.
- **A confident claim about LangGraph's semantics is a claim until checked against the installed
  source.**
- **Check the *SKU's* quota, not the model's availability** (D49).
- **An SDK that "reports failures as results" can still raise** (D57).
- **Windows path semantics**: a trailing dot is stripped on existence checks but not on directory
  enumeration (D46).
- **A generator raises where it is iterated, not where it is called.**
- **A validation rule tested on one method of six is tested nowhere** (D39).
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
