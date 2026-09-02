# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`.

_Last updated: 2026-09-03 · after T18H built and wired a real geometric-correctness gate into every
render, the gate caught four real bugs on its very first live use (all fixed and re-verified), a
fifth different-in-kind bug was found and explicitly deferred at the user's own request, and no
closing render completed this session — the showcase video the user asked for was not produced_

---

## Where we are

**T18H is done, T18I is scoped and next.** Full reasoning, the exact iteration order (including
what was tried and confirmed *not* to work), and every real bug's own account: decisionlog **D124**.

### What T18H shipped

**The gate itself.** `interfaces/render_backend.py::RenderBackend` gained
`validate_geometry(composition: Path) -> list[str]` — a second, equally-fatal check
`rendering/render_segment.py` now runs right after `lint`, before tier dispatch, raising the same
`CompositionInvalid` path. Implemented in `adapters/local/render_backend.py` by calling the CLI's
own `check` subcommand (`hyperframes_check.py`, in this project's toolchain since T18A as a
manual/test-only diagnostic, never previously wired into the actual render path), folding both its
`layout` and `runtime` finding categories into the result, sharing the class's own concurrency
semaphore. Stubbed in `adapters/azure/render_backend.py` (T35). Runs with `at_transitions=False,
frame_check=False, contrast=False` — measured, not guessed: `--at-transitions` cost ~56s vs. ~15s
per real segment for the *same* result on the one dense composition measured (a sustained crowding
bug, not a one-frame transition artifact).

**Two bugs fixed as the gate's opening proof** (already root-caused from T18G's own prior render):
`_block_graph_diagram.html::computeLayeredLayout`'s same-rank node crowding in a compact canvas;
CURSOR annotations on `GRAPH_DIAGRAM` nodes now target the marker's own id
(`{prefix}-node-marker-{index}`), not the whole node div, via `rendering/annotations.py
::_ANNOTATION_TARGET_SUFFIX_OVERRIDE` (keyed by block type AND annotation type).

**`project-reviewer` found two real gaps in the gate itself**, both fixed before the first
checkpoint attempt: `validate_geometry` was reading only `layout` findings (a browser-check crash
reports under `runtime` instead, and would have silently passed as "no findings" — the exact "tool
didn't run" vs. "tool found nothing" conflation `lint()` already guards against); it was not
sharing the adapter's own concurrency semaphore, risking per-segment resource starvation on a job
that fans out one `validate_geometry` call per segment with no other cap.

**Four more real bugs, found by the gate's own closing render attempt, not by the plan** — every
one a genuine geometry defect the gate exists to catch, each independently reproduced and fixed:

1. `CODE_PANEL`/`CODE_DIFF`'s trailing caption has no per-item height to shrink (F7's technique
   doesn't apply to a single word-wrapping paragraph). Fixed: `_annotations.html` gained
   `hfDropIfPastCaptionBand(elId)` — real DOM measurement against the caption band's own documented
   fraction (0.8574) — used by both templates to drop the caption rather than leave it colliding.
2. An LLM-authored `GRAPH_DIAGRAM` position (`payload.positions`) bypassed every safety margin the
   fallback algorithm respects. **A per-node clamp was tried first and confirmed live to make it
   worse** — trading a caption-band collision for a different node-vs-node one. Fixed instead: if
   ANY node's authored position is unsafe, the WHOLE authored set for that diagram is discarded in
   favor of the algorithm's own (already-proven-safe) fallback for every node.
3. Even the fallback algorithm could still produce an adjacent-rank collision in a fully-captioned
   3-rank non-compact diagram — `rankStep` is a function of rank count, not of real node footprint.
   Partially fixed by widening `Y_MIN_FRAC` (0.14→0.08, reclaiming real headroom; `Y_MAX_FRAC` stays
   at 0.62, the caption-band margin), and fully closed for the case actually hit by a new check:
   each node's own optional caption is measured against every other node's essential content
   (marker+label, via `hfRectsOverlap`) and hidden if it would collide.
4. `TEXT_PANEL`'s own item list reached the caption band — a different problem, since every item is
   essential narrated content, never droppable. Fixed: the real measured overflow shrinks the CSS
   `gap` between items (never the text itself), floored at 8px.

**A second `project-reviewer` pass, after all four fixes above, found two more real issues, both
fixed:** the authored-position safety check's own duplicate `Y_MIN_FRAC` copy (necessarily
duplicated across two JS closures) was never updated when the real one was lowered to 0.08 earlier
in the same edit — a fully-authored-and-safe set containing `y=0.10` would have been wrongly
discarded wholesale; and `_block_text_panel.html` had hand-copied the caption-band fraction a third
time rather than referencing `_annotations.html`'s own shared constant. Both fixed and re-verified
live. Full account: D124.

**A fifth bug, genuinely different in kind, explicitly deferred — the user's own call**, made after
watching four consecutive find-fix-reproduce cycles run in one session and asking to stop rather
than chase a fifth live: `SceneLayout.SINGLE` can compose multiple large blocks stacked vertically
(not just one), with nothing constraining their combined height. Confirmed live: a full
`GRAPH_DIAGRAM` (headline + 620px canvas) stacked above a `TEXT_PANEL` produced 42
`canvas_overflow` findings — a capacity problem, not a positioning one, untouched by fixes 1-4.
Carried into **T18I**, along with two things the user named directly at checkpoint time: annotation
placement needs a parallel-to-a-line option (not just above/below/on-point) for line-shaped
targets, and a genuine full ~7-minute render must be T18I's own closing proof. Full scope: T18I's
own `tasks.md` entry.

**No closing render completed this session.** The showcase video the user asked for was not
produced — every attempt hit a real bug (proving the gate works) before finishing. This is
explicitly not swept under the rug: T18I's own DoD requires landing one.

**Not merged to `dev` yet, not pushed.** Still on `feature/scene-composition`, matching this
project's standing pattern (every T18-series checkpoint lands there first). Ask before pushing.

**Done:** T1-T18, T18A-T18H.
**Next:** T18I — close the multi-block-stacking capacity gap, add parallel-to-a-line annotation
placement, re-verify (not re-assume) whether "random" annotation timing is a real separate defect
or a symptom of bad placement, land a genuine full 7-minute render as the closing proof. Full scope
in `tasks.md`'s T18I entry — read it before starting; it is not a re-scoping exercise, it is
finishing exactly what T18H's own gate already found.

## What T18H produced

**New:** `tests/test_graph_diagram_authored_positions_live.py`, `tests/test_code_caption_band_live.py`,
`tests/fixtures/render_backend/overlapping/` (a real, deliberately-overlapping fixture with its own
vendored `gsap.min.js`, proving `validate_geometry` catches what `lint` structurally cannot).

**Modified:** `interfaces/render_backend.py`, `adapters/local/render_backend.py`,
`adapters/local/hyperframes_check.py`, `adapters/azure/render_backend.py`,
`rendering/render_segment.py`, `rendering/annotations.py`, `rendering/templates/_annotations.html`,
`rendering/templates/_block_graph_diagram.html`, `rendering/templates/_block_code_panel.html`,
`rendering/templates/_block_code_diff.html`, `rendering/templates/_block_text_panel.html`, plus the
test files these changes touched (`tests/fakes/render_backend.py`, `tests/test_adapter_stubs.py`,
`tests/test_compose_annotations.py`, `tests/test_graph_diagram_layout_live.py`,
`tests/test_interfaces.py`, `tests/test_render_backend_parity.py`, `tests/test_render_segment.py`).

**Real render artifacts** (gitignored, not committed): `artifacts/_cli_run/
t18h-showcase-binary-search/` — six partial attempts, none completed to a final MP4. Left in place;
each attempt's `segments/N/composition/` is what every reproduction this checkpoint's own D124
account references was built from. Safe to delete once T18I lands its own closing render, not
before (they are the ground truth for the bugs D124 documents).

## Verify at any time

```bash
pytest -m "not local_live"                # offline, no network -- all passing, one unrelated skip
pytest -m local_live tests/test_render_segment_live.py tests/test_graph_diagram_layout_live.py \
  tests/test_graph_diagram_edges.py tests/test_graph_diagram_authored_positions_live.py \
  tests/test_code_caption_band_live.py tests/test_render_backend_parity.py
                                           # real toolchain -- every T18H fix's own regression test
ruff check . && ruff format --check .     # clean except one pre-existing, unrelated drift
                                           # (.claude/skills/python-pro/SKILL.md, carried since T18E)
grep -rE "azure|openai|huggingface|ollama|playwright" core/ --include=*.py   # empty (one
                                           # docstring-text hit in node_timing.py, not a real import)
grep -rE "langgraph" core/ --include=*.py | grep -v "^core/graph/"           # empty

PYTHONPATH=. .venv/Scripts/python.exe cli.py "how binary search works" --job-id t18h-showcase-binary-search
                                           # resumes the unfinished showcase job from its own
                                           # checkpoint sqlite -- LLM/TTS stages will likely re-run
                                           # (observed non-deterministic re-execution of author_scene
                                           # on resume, not a clean skip-ahead -- see Gotchas below)
```

## Environment state

| | |
|---|---|
| Models | Session ran entirely on Sonnet, confirmed via the mandatory self-check before every build phase (including after two plan-mode re-entries this session). Re-check at the next session's own build phase regardless — the standing rule, not assumed to hold across a session boundary. |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100) — unchanged, still temporary until T35. |
| `FRAME_BUDGET` | `9500`, unchanged. |
| `RENDER_MAX_CONCURRENCY` | `2`, unchanged. |
| `AZURE_OPENAI_MAX_CONCURRENCY` | `4`, unchanged. |
| Git | `feature/scene-composition`, NOT pushed this checkpoint (pending user confirmation). `dev`/`master` unchanged from T18G's own `4f10ae7`. |
| Azure spend | Six partial render attempts this session (each re-running outline/scripting/TTS on resume, per the Gotcha below) — all short-lived (killed or failed within 1-25 minutes), trivial against the $200/30-day credit, but real spend nonetheless from repeated LLM/TTS calls on the same content. No completed render, so no Tier-2 render-backend Azure cost (`RENDER_ENV=local` anyway). |

## Before the next session

1. **Read D124 in full before starting T18I** — it has the exact order fixes were tried, including
   the one (a per-node authored-position clamp) that was tried and confirmed to make things worse.
   Do not re-attempt that approach without re-reading why it failed.
2. **Confirm whether to push `feature/scene-composition`** — not done yet this checkpoint, waiting
   on the user.
3. Nothing else environment-side is outstanding.

## Known gaps and open questions

**New this checkpoint (T18I's own scope, not re-derived — see `tasks.md`'s T18I entry for the full
account):**
- `SceneLayout.SINGLE` stacking multiple large blocks has no combined-height constraint (42
  `canvas_overflow` findings, confirmed live).
- `hfAnnotationPlace` has no parallel-to-a-line candidate — an annotation on a line-shaped target
  (a graph edge, a sequence-diagram message) is placed the same way as one on a point-shaped
  target.
- Whether "annotations appear at random times" (the user's own words) is a real, separate timing
  defect or a symptom of the placement gap above is not yet confirmed either way.
- No closing real render this session — T18I's own DoD requires landing one.

**Carried forward from T18G's own checkpoint, now resolved by this task (kept here only so a future
reader doesn't wonder why it's missing):**
- `GRAPH_DIAGRAM`'s layered layout not accounting for node size when spacing same-rank nodes in a
  compact canvas — fixed (T18H fix set, opening proof).
- CURSOR targeting a `GRAPH_DIAGRAM` node's whole div instead of its marker — fixed (T18H fix set,
  opening proof).

**Carried forward, unchanged from prior checkpoints:**
- The shrink-to-fit height floor (T18G's F7 + review fix) stops a single row/cell from collapsing,
  but total content height can still exceed the caption-band budget once item count is far enough
  past the advisory schema range that `floor * count` alone exceeds it. Same root-cause family as
  T18I's own multi-block-stacking item — worth reading together when T18I is scoped in detail.
- The cross-requeue `StructuredOutputError` cap (`QueuedJob.attempt`) is still open (D24/D67).
- No coverage gate exists (D42).
- `Segment.scene` is still untyped by design (D29's pattern) — revisit at T24 as previously planned.
- D47's disk-I/O-under-concurrency measurement (D69) used small WAV files only — still open.
- T10 stays `in-progress`, unclaimed. Ollama/Kokoro still don't exist.
- `hyperframes check` is documented as non-deterministically flaky at times (D96) — not clearly hit
  this session (every failure this session reproduced consistently when re-checked directly), but
  still worth re-running before trusting a single red result in general.
- `pipeline-debugging`'s documented artifact layout is stale — flagged by T18D, still not fixed.
- A real photo/logo image-sourcing pipeline and the general payload-driven block-*variants* system
  (D121's analysis item 8 proper) both remain deliberately out of scope.

## Gotchas worth remembering

**New this session:**
- **A killed background render job resumed with the SAME `--job-id` does not cleanly skip ahead
  from its last completed stage** — observed live, repeatedly: `author_scene` (and the LLM calls
  behind it) re-ran on resume even though outline/scripting/TTS synthesis had already completed and
  were not re-run, suggesting the checkpoint granularity around scene authoring/visual planning
  does not persist as far as expected. Each resume attempt therefore costs real LLM spend, and (via
  LLM non-determinism) can produce *different* scene content on each attempt — a bug reproduced
  against one attempt's composition may not reproduce identically against the next attempt's.
- **Long-running background render jobs got killed mid-run repeatedly this session, apparently
  externally** (not a tool timeout — confirmed by checking elapsed wall-clock time against the
  configured timeout, which did not match; not a deliberate user interrupt either, confirmed
  directly with the user). Cause not identified. If this recurs, treat "killed" (not "failed") as
  inconclusive about the code itself — check whether the same composition reproduces the same
  result via a direct, foreground `hyperframes check` call before assuming a regression.
- **A per-node fix that clamps one unsafe value into range can create a NEW collision with a
  different, already-safe value nearby** — confirmed live (D124, GRAPH_DIAGRAM authored positions).
  When one part of a set is unsafe, prefer discarding that whole set for an already-verified-safe
  alternative over patching the one bad value in place, unless you can also re-verify the patched
  value against every OTHER value in the same set.
- **`hyperframes check`'s `layout` category can be empty even when something real broke** — if the
  browser check itself crashes or throws mid-composition, the failure is recorded under `runtime`
  instead, with `layout: {findings: [], ...}` looking identical to a genuinely clean composition.
  Any code parsing `check`'s JSON for correctness must read `runtime` too, not just `layout`.
- **`SceneLayout.SINGLE` is not always exactly one block** — `_layout_single.html`'s own `{% for
  block in blocks %}` loop was assumed (incorrectly, until this session) to only ever iterate once.
  It can stack multiple blocks vertically; nothing in this codebase currently limits how many or
  how tall.

**Carried from T18G, still true:**
- **A GRAPH_DIAGRAM node div's CSS center is not its visible marker circle's center.**
- **`[await x() for i in xs]` inside a list comprehension is sequential, not concurrent.**
- **The Azure adapter's own `asyncio.Semaphore(max_concurrency)` already makes concurrent calls
  from any caller safe** — but only for callers that actually acquire it; a new method on the same
  class does not get this for free (see `validate_geometry`'s own review finding above).
- **`mcp__azure__storage`'s AAD-login path can't write blobs on this account; use `az storage blob
  upload` with the connection string instead** (via `dotenv_values`, not bash `source`).
- **Python's logging module drops `INFO` and below by default until something calls
  `logging.basicConfig`.** `cli.py::main()` already does this.
- **A Jinja `loop.index0` inside one `{% for %}` block and a JS counter incremented only under a
  condition are NOT the same index.**
- **`hfAnnotationOffset`/`hfAnnotationPlace`'s scale-cancellation trick works for any ratio
  computation, not just absolute-pixel deltas** — reused this session for `hfDropIfPastCaptionBand`
  and the graph-diagram caption-collision check.

**Carried from T18C, still true:**
- **`getBoundingClientRect()` returns viewport pixels, not this project's own 1920x1080 CSS-pixel
  space** whenever the capture harness renders at a different effective scale.
- **A `position: absolute` element with no explicit `top`/`left` does NOT default to its
  container's origin.**
- **A test that passes offline does not mean the code path it claims to cover actually ran.**
- **The Blob skill registry does not auto-sync with local disk, ever.**

**Carried from T18A/T18B, still true:**
- **The quality hook strips an import added before its first use** — add the import in the same
  tool call as its first real usage.
- **`hyperframes lint`'s severity levels are meaningful** — only `[error]` blocks a render.
- **The hooks fire on `Write|Edit`, not on Bash heredocs.** Use `Write` for `.py` files.
- **CLAUDE.md's boundary greps are plain text searches.** Verify imports with AST, not text.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
