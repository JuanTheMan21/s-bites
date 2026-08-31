# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-08-31 · after T18E ran to completion (all seven sub-parts plus a bounded E2.4
compact-layout addition), one real bug found by review and fixed pre-render, one real gap in E5's
own logging found live and fixed in-session, three new findings from real renders recorded for a
future task, full suite green (D122)_

---

## Where we are

**T18E is done.** All seven planned sub-parts (E1-E7) shipped, plus E2.4 — an aspect-ratio-aware
fallback layout for `GRAPH_DIAGRAM`'s compact `SPLIT_HORIZONTAL` canvas, a bounded slice of the
larger layered-layout redesign D121 had deferred, pulled forward at the user's own request when
approving the plan because nothing else in E1-E7 actually fixed the confirmed node-overlap bug.
Full reasoning, evidence, and the complete list of what shipped: decisionlog **D122**.

**What actually changed, by area:**
- **E1** — annotation authoring moved out of `plan_visuals` into a new
  `core/graph/nodes/annotation_author.py`, called from `author_scene` once every block is filled.
  New `core/annotation_plan_schema.py`, `core/block_items.py`, runtime pack
  `annotation-authoring/1.0`. `ComposedAnnotation.target_item_index`/`anchor_phrase` are now
  required, not nullable; `rendering/annotations.py` drops (never guesses at) anything that
  doesn't resolve to a real item, block, or narration moment. `core/scene_plan_schema.py
  ::PlannedAnnotation` is gone; `visual-plan` is at `1.2` (no longer plans annotations),
  `scene-authoring` stayed at `1.3` for the fill call itself.
- **E2 / E2.4** — `rendering/templates/_block_graph_diagram.html`: edges anchor to the measured
  marker-circle center (not the node div's CSS center), gate on both endpoints' own entrance
  times, get arrowheads (also added to `_block_sequence_diagram.html`'s messages and the CHAIN
  rail). The GRAPH-mode fallback layout is aspect-ratio-aware: SPLIT_HORIZONTAL's compact canvas
  lays unauthored nodes on the wide axis instead of the circular formula SINGLE's canvas still
  uses.
- **E3** — `GraphEdge.label: str | None` (required-but-nullable), rendered at the edge midpoint.
  `scene-authoring` is at `1.4` for this.
- **E4** — new `core/block_triggers.py`; `plan_visuals` makes exactly one bounded re-ask when a
  segment's narration clearly calls for a block type the plan uses nowhere in the video. Real
  blind spot found this session, recorded below, not yet fixed.
- **E5** — new `core/graph/node_timing.py::timed()` wraps every node in
  `core/graph/pipeline.py`; a `before_sleep` callback logs Azure LLM retries. **A real gap found
  live and fixed in-session**: nothing configured Python's logging module, so the per-node
  `INFO`-level lines never reached the console in a real run (only the adapter's `WARNING`-level
  retry line did, by Python's own default last-resort-handler behavior) — fixed with one
  `logging.basicConfig(...)` call in `cli.py::main()`, smoke-tested directly.
- **E6** — `_annotations.html::hfAnnotationPlace`, used by all three `_annotation_*.html`
  partials, replacing three ad hoc fixed offsets with a container-bounded placement (clear of the
  target block's headline and the caption band).
- **E7** — `author_scene`'s per-block fills and `write_narration`'s per-segment calls now use
  `asyncio.gather`, reopening D47 on the user's own explicit instruction.

**One real bug found by this session's own `project-reviewer` review, before any render, and
fixed pre-render**: `_block_graph_diagram.html`'s edge-label lookup used a labelled-only counter
in the script against an overall-position id in the markup — the two only agreed when every
labelled edge preceded every unlabelled one. Fixed to share the same index both places;
`tests/test_graph_diagram_edges.py` was reordered specifically to catch this class of bug again.

**A real concurrency assumption broke, caught by the test suite, not reasoning about it.**
`author_scene`'s two per-segment LLM calls (fill, then annotate) can genuinely interleave across
*different* segments' concurrent `Send` tasks once a real checkpointer (`AsyncSqliteSaver`) is in
play — its I/O gives each task a real suspension point. `FakeLLMProvider`'s strict-FIFO queue
(deliberately tested, left untouched) can't handle two differently-typed calls under real
interleaving, so `tests/graph_pipeline_fixtures.py::PhaseQueueLLMProvider` (a narrowly-scoped
subclass matching by type, used only by the checkpointer-backed graph-level tests) exists now.

**Verified against three real `RUNTIME_ENV=azure` renders** (`t18e-array-grid`, `t18e-timeline`,
`t18e-graph-single` — T18D's own topics, for direct before/after comparison), Blob-synced first
(three packs were missing — `annotation-authoring/1.0`, `scene-authoring/1.4`, `visual-plan/1.2`
— the same recurring drift D107/T18D already hit; still no automated sync). Each watched via
targeted frame extraction. E1, E2, E2.4, E3, and E5's retry logging all confirmed working for
real, not just offline — full account in D122.

**Three new findings, recorded not fixed — the user's own explicit choice when offered a
three-way decision (record-only / fix the sharpest one / fix all three).** Read D122's full
account before assuming any of these are already covered:
1. Two annotations targeting nearby items in the same block can still collide with *each other*
   — E6 only keeps one annotation clear of the block's headline and the caption band.
2. E4's trigger-vocabulary scan misses a narration that signals chronology through
   domain-specific version numbers ("HTTP 1.0... HTTP 1.1... HTTP/2... HTTP/3...") rather than
   generic timeline words — `t18e-timeline`'s own topic never got `TIMELINE`.
3. E2.4 (node layout), E3 (edge labels), and E1/E6 (annotations) were each verified in
   isolation, not together — a dense compact-canvas graph with all three combined lets labels,
   captions, and an annotation collide with each other even though nodes themselves stay
   properly separated.

**Still on `feature/scene-composition`.** Branched from `dev` at `5b4d7ba`, never merged back —
unchanged standing note since T18B, still blocked on the user's own decision to merge (not
automatic as part of any checkpoint).

**Done:** T1-T18, T18A, T18B, T18C, T18D, T18E.
**Next:** not yet chosen. T18F ("vision critique/revision loop, full validation render,
rendering/pipeline speed") is still `todo` and still the next placeholder in sequence, but the
three new findings above are real, un-scoped work too — worth a real conversation with the user
about priority before assuming T18F is next by default.

## What T18E produced

**New:** `core/annotation_plan_schema.py`, `core/block_items.py`, `core/block_triggers.py`,
`core/graph/node_timing.py`, `core/graph/nodes/annotation_author.py`,
`runtime_skills/annotation-authoring/1.0.md`, `runtime_skills/scene-authoring/1.4.md`,
`runtime_skills/visual-plan/1.2.md`, plus `tests/test_block_triggers.py`,
`tests/test_graph_diagram_edges.py`, `tests/test_visual_plan_node.py`,
`tests/test_concurrent_llm_calls.py`, `tests/test_node_timing.py`,
`tests/graph_pipeline_live_fixtures.py`.

**Modified:** `cli.py` (logging config), `adapters/azure/llm_provider.py` (retry logging),
`core/block_schemas_graph.py` (`GraphEdge.label`), `core/graph/nodes/{scene_author,scripting,
visual_plan}.py`, `core/graph/pipeline.py`, `core/{scene_plan_schema,scene_schemas}.py`,
`rendering/annotations.py`, `rendering/templates/_annotation*.html`,
`rendering/templates/_block_graph_diagram.html`, `rendering/templates/_block_sequence_diagram.html`,
`rendering/templates/_layout_{single,split_horizontal}.html`, plus the test files these changes
touched (`tests/scene_author_fixtures.py`, `tests/graph_pipeline_fixtures.py`,
`tests/test_author_scene_node.py`, `tests/test_compose_annotations.py`,
`tests/test_array_grid_and_graph_modes.py`, `tests/test_azure_retry.py`,
`tests/test_graph_resume.py`, `tests/test_graph_pipeline_live.py`, `tests/block_examples.py`,
`tests/test_runtime_skills.py`).

**Real render artifacts** (gitignored, not committed): `artifacts/_cli_run/t18e-{array-grid,
timeline,graph-single}/`, verification frames under `artifacts/_frames/t18e-{array-grid,
graph-single}/`.

## Verify at any time

```bash
pytest                                    # offline, no network -- 633 passed, 1 skipped
ruff check . && ruff format --check .     # clean except one pre-existing, unrelated drift
                                           # (.claude/skills/python-pro/SKILL.md, not T18E's)
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # empty (one
                                           # docstring-text hit in node_timing.py, not a real import)
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # empty
git branch --show-current                                                    # feature/scene-composition

PYTHONPATH=. .venv/Scripts/python.exe cli.py                  # prompts for a topic, runs standalone
```

## Environment state

| | |
|---|---|
| Models | Session ended pinned to Sonnet (the user's own explicit `/model sonnet` mid-session, after this session's own planning phase ran on Opus). No standing default-model change was made this session beyond the earlier one already on record. **Check the model banner before the next session's build phase regardless** — same standing mandatory self-check `CLAUDE.md` requires every time. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100) — unchanged, still temporary until T35. |
| `FRAME_BUDGET` | `9500`, unchanged. Still not retuned — E5 (this session) is what a future measurement pass would use, but this session didn't do that measurement pass itself. |
| `RENDER_MAX_CONCURRENCY` | `2`, unchanged, still unmeasured under real concurrent load. |
| `AZURE_OPENAI_MAX_CONCURRENCY` | `4`, unchanged. E7's parallelization is safe against this cap regardless of caller pattern (the adapter's own semaphore bounds it) — this session didn't retune the cap itself, per plan. |
| Git | `feature/scene-composition`, branched from `dev` at `5b4d7ba`. Not yet pushed to `origin`. Not merged back yet. |
| Blob skill registry | **Synced this session** — `annotation-authoring/1.0.md`, `scene-authoring/1.4.md`, `visual-plan/1.2.md` uploaded to the `runtime-skills` container, verified via `az storage blob list`. Still no automated sync — will drift again the next time `runtime_skills/` changes and nobody syncs by hand. |
| Azure spend | Three real `RUNTIME_ENV=azure` renders this session (LLM + TTS + Blob), each ~90s target, elapsed 244-349s wall-clock each. Trivial against the $200/30-day credit. No render-backend Azure cost (`RENDER_ENV=local`). |

## Before the next session

1. **Decide what's next.** T18F is the next placeholder in `tasks.md`, but the three findings
   D122 recorded (inter-annotation collision, E4's version-number blind spot, the dense-scene
   E2.4/E3/E1 interaction) are real, currently-unscoped work competing for the same slot — worth
   discussing with the user rather than defaulting to T18F.
2. **Merge `feature/scene-composition` back to `dev`**, whenever the user decides — still not
   automatic as part of any checkpoint, per the standing note this file has carried since T18B.
   T18D and T18E together are now real shipped fixes against the block library, unlike T18D alone.

## Known gaps and open questions

**New this checkpoint (D122) — three real findings from T18E's own verification renders, not
covered by anything in E1-E7/E2.4:**
- Two annotations targeting nearby items in the same block can collide with each other — `E6`'s
  `hfAnnotationPlace` only accounts for one annotation's own container, headline, and caption
  band, never a sibling annotation.
- `E4`'s trigger-vocabulary scan (`core/block_triggers.py::TRIGGER_VOCABULARY`) misses a
  narration that signals chronology through domain-specific version numbers rather than generic
  words like "timeline"/"history"/"milestone" — a real, not hypothetical, miss on exactly the
  topic chosen to force `TIMELINE`.
- `E2.4`'s compact-canvas layout, `E3`'s edge labels, and `E1`'s annotations were each verified
  against a simpler scene in isolation — combined on one dense 5-node graph, node separation
  holds but labels/captions/annotation caption collide with each other.

**Carried forward, unchanged from prior checkpoints:**
- `rendering/block_timing.py`'s per-item anchor fallback (`_ITEM_FIELDS`:
  `graph_diagram.nodes`, `text_panel.items`, `code_diff.lines`) is still index-only —
  T18D's headline finding, explicitly **not** part of T18E's scope (E1 fixed *annotation*
  timing specifically, not this underlying block-item timing mechanism). Still open.
- The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open (D24/D67).
- No coverage gate exists (D42).
- `Segment.scene` is still untyped by design (D29's pattern) — revisit at T24 as previously
  planned.
- D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only — still open.
- T10 stays `in-progress`, unclaimed. Ollama/Kokoro still don't exist.
- `hyperframes check` is still non-deterministically flaky at times (D96) — re-run before
  trusting a single red result. Not hit this session.
- `pipeline-debugging`'s documented artifact layout is stale (no `script.json`/`scene.html`; the
  real layout is `segments/<n>/composition/index.html` + `clip.mp4` + `narration.wav` +
  `silent.mp4`) — flagged by T18D, not yet fixed, not part of T18E's scope either.

## Gotchas worth remembering

**New this session:**
- **`FakeLLMProvider`'s strict-FIFO queue breaks the moment a phase makes calls of more than one
  distinct schema type under real concurrency.** It worked for every case before T18E because
  every concurrent-fan-out phase only ever queued one homogeneous type. The moment `author_scene`
  started making two types per segment (fill, then annotate), a real checkpointer's I/O gave
  each segment's `Send` task a genuine suspension point, and strict positional FIFO could no
  longer guarantee a matching type at the head. Fix pattern:
  `tests/graph_pipeline_fixtures.py::PhaseQueueLLMProvider` — match by type anywhere in the
  queue, not position — used only where this specific problem exists, `FakeLLMProvider` itself
  untouched. Worth reaching for this pattern again if a future task adds a third differently-typed
  call to any existing concurrent fan-out.
- **Python's logging module drops `INFO` and below by default until something calls
  `logging.basicConfig` (or otherwise attaches a handler).** A `logger.info(...)` call anywhere
  in the codebase is silently a no-op in a real `cli.py` run unless something configures logging
  first — confirmed live, not assumed, when three real renders showed zero per-node timing lines
  despite the code being correct and offline-tested. `cli.py::main()` now does this once; nothing
  else in the codebase should need its own `basicConfig` call as a result.
- **A Jinja `loop.index0` inside one `{% for %}` block and a JS counter incremented only under a
  condition are NOT the same index**, even when a quick real-render sample makes them look like
  they agree. `_block_graph_diagram.html`'s edge-label bug (found by review, not a render) is the
  concrete instance: the markup's `loop.index0` runs over every edge, labelled or not; a
  same-named-feeling JS `labelIndex` that only increments for labelled edges silently desyncs the
  moment an unlabelled edge precedes a labelled one. Any future per-item id emitted conditionally
  from a Jinja loop needs the SAME index used on both the markup and script sides — never a
  separately-scoped counter, however natural it looks at the call site.
- **`hfAnnotationOffset`/`hfAnnotationPlace`'s scale-cancellation trick (dividing two
  same-viewport rects by the same `#root`-width-derived scale factor) works for any *ratio*
  computation, not just absolute-pixel deltas** — `_block_graph_diagram.html`'s marker-center
  measurement reuses this to convert a node's real screen position into viewBox units without
  ever touching `#root`'s own rect, because the canvas's own scale factor cancels out of the
  ratio. Worth remembering as the general technique, not just the two places it's now used.

**Carried from T18D, still true:**
- **A GRAPH_DIAGRAM node div's CSS center is not its visible marker circle's center** — this is
  now fixed for edges/traversal (T18E, E2), but the underlying fact (label/caption height shifts
  the div's true center) is still true of the div itself; any *new* code touching node geometry
  should measure the marker, never trust the div's own position.
- **`[await x() for i in xs]` inside a list comprehension is sequential, not concurrent** — fixed
  for both known instances this session (E7); worth grepping for the same pattern anywhere else
  before assuming it's now handled everywhere.
- **The Azure adapter's own `asyncio.Semaphore(max_concurrency)` already makes concurrent calls
  from any caller safe** — unchanged reasoning, now also covers E7's two new `asyncio.gather`
  sites.
- **`mcp__azure__storage`'s AAD-login path can't write blobs on this account; use `az storage blob
  upload` with the connection string instead.**
- **A real render's artifact layout does not match `pipeline-debugging`'s documented one** — see
  "Known gaps" above.

**Carried from T18C, still true:**
- **`getBoundingClientRect()` returns viewport pixels, not this project's own 1920x1080 CSS-pixel
  space** whenever the capture harness renders at a different effective scale — normalize against
  `#root`'s own known width first.
- **A `position: absolute` element with no explicit `top`/`left` does NOT default to its
  container's origin.**
- **A test that passes offline does not mean the code path it claims to cover actually ran.**
- **The Blob skill registry does not auto-sync with local disk, ever** — confirmed drifted a
  fourth time now (T18A, T18B, T18D, T18E).

**Carried from T18A/T18B, still true:**
- **The quality hook strips an import added before its first use** — add the import in the same
  tool call as its first real usage. Hit repeatedly this session across nearly every multi-edit
  file; worth treating as the default assumption for any edit that adds an import, not a
  surprise when it happens.
- **`hyperframes lint`'s severity levels are meaningful** — only `[error]` blocks a render.
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text —
  `core/graph/node_timing.py`'s own docstring mentioning `adapters/azure/llm_provider.py` by name
  is this session's own live example of a false positive.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
