# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

## What just happened

**T18K and T18L both shipped in one combined session** (backend + frontend, by explicit user
request), then verified against two real end-to-end renders through the live UI — not just the
offline test suite. Both are marked `done` in `tasks.md`. Full reasoning for every non-obvious
choice: `decisionlog.md` D165-D171.

### T18K (backend)
- **K1** — Tier-1 stills now sample at caption-cue boundaries and block reveal times
  (`rendering/still_plan.py`, a JSON sidecar `compose_scene` writes and `rendering/reveal.py`
  reads back — D165), with a hard cut across any transition where the caption text changes
  (`mux/frames_to_clip.py::crossfade` gained optional `at_seconds`/`xfade_s`). Tier 0 suppresses
  the in-frame caption band entirely (one still cannot show N captions). The last caption cue now
  hides at the segment's measured `duration_ms`, not its own `end_ms`, so trailing silence no
  longer shows a blank band.
- **K2** — `core/graph/nodes/finalize.py` logs real per-step timing; `mux/concat_segments.py` has
  explicit `-preset veryfast -crf 20` (previously absent everywhere in the repo). **Measured: a
  comparable 6-segment job's finalize dropped from 3m41s (D162's baseline) to 14.06s** (D171) —
  but see the logging gap below, without which this number would never have been visible at all.
- **K3** — `rendering/block_timing.py`/`rendering/timing_math.py::clamp_non_decreasing` forces a
  non-sortable item field's (graph_diagram, code_diff) or any step field's resolved time to
  never fall before its predecessor's — a running-max clamp, never a re-sort (`graph_diagram`
  must stay in `_SORTABLE_ITEM_FIELDS`'s exclusion list; do not add it back).
- **K4** — `rendering/templates/_annotations.html` gained a second registry
  (`window.__hfAvoidRects`, separate from `__hfPlacedRects`) populated by scanning
  `[data-anno-avoid]` elements; 8 block partials now mark their own text-bearing elements with it.
- **K5** — `_block_text_panel.html`'s `.blk-text-copy` items got the same outlined-chip treatment
  `_block_title.html`'s `key_terms` already have (16px radius, not a pill — items are sentences).

### T18L (frontend)
- **L1** — `StageTicker.tsx` deleted (the jittery per-event ticker). **`StageLog.tsx` also
  deleted** — not in the original task text, added mid-session on the user's own direct
  instruction after watching a real render ("the stage log and shit needs to be fixed... needs to
  be clean apple esque," D170). `use-job-stream.ts` now batches SSE arrivals into one `setEvents`
  per animation frame instead of one per message; nothing is dropped, only coalesced (flushes
  immediately on the terminal status event and on unmount).
- **L2** — the waveform is real now: `wave-shape.ts` (deterministic harmonics from a seed, pure),
  `use-smooth-progress.ts` (eases toward real progress, creeps toward the next phase's boundary
  when idle, respects `prefers-reduced-motion` — pure tick function `nextProgressValue` is
  separately unit-tested), `WaveScope.tsx` (canvas: a dark scope panel, 3 layered wave copies,
  bright-with-glow left of the playhead / dim ghost right of it). `ClipTrack.tsx`'s playhead
  position is now set via plain `style.left`, not a Motion `animate` tween — kept pixel-synced
  with what the canvas draws every frame, deliberately not double-smoothed.
- **L3** — `Segment.render_outcome` (already a real per-segment field on the API schema) is
  destructured directly in `job-adapter.ts` into `SegmentView.degraded` — simpler than the
  original plan's job-level-array-joined-by-index design, since the per-segment field already
  existed (D169). `SegmentCard.tsx` shows a small amber "Degraded" badge with a tooltip; confirmed
  live against two real re-authored segments across two different jobs.

## Two real bugs found only by watching real renders (not by the offline suite)

Both are now fixed, with regression tests — the same "toolchain-only checks miss real defects"
lesson this project's history keeps re-learning (D89/D106/D109/D119/D124), so read both before
assuming "tests pass" means "the video is right."

1. **The caption band was never marked exempt from `hyperframes check --caption-zone`** (D166).
   K1's own fix (extending the last cue's visible window to `duration_ms`) made a real render fail
   `caption_zone_collision` on a segment's own caption words — it only ever passed before because
   the last cue used to hide (opacity 0) before the geometry checker's end-of-timeline sample
   landed. Fixed: `_captions.html`'s caption layer now carries
   `data-layout-allow-caption-zone`. Test: `tests/test_caption_zone_exemption.py`.
2. **Nothing in this app has ever configured Python's logging level** (D167). Every `logger.info`
   call anywhere in the codebase — including `core/graph/node_timing.py`'s per-node timing logs,
   shipped in T18E — was silently swallowed by the interpreter's default WARNING threshold, since
   startup. Confirmed directly: a real server's stdout showed zero `logger.info` lines from
   anywhere in the app across two full job runs, until `logging.basicConfig(level=logging.INFO,
   ...)` was added to `api/main.py`. **This means T18E's own timing/retry-visibility feature has
   been invisible for its entire life until this session.** If you're debugging something and
   expect to see INFO logs, they now actually work — they didn't before.

## Also fixed this session
- Two `project-reviewer` nits from the first review pass: `mux/frames_to_clip.py::crossfade` now
  raises if `xfade_s` is given without `at_seconds` (was a silent mis-timing footgun); `use-job-
  stream.ts`'s unmount cleanup now flushes pending events before closing.
- `rendering/compose.py` was split: `RenderableBlock`/`build_renderable` moved to new
  `rendering/renderable.py` to stay under the 200-line ceiling once still-plan wiring was added.
- `rendering/block_timing.py`'s two pure array-math helpers moved to new
  `rendering/timing_math.py`, same reason.
- **A real 200-line-ceiling violation slipped past the quality hook**, found in this checkpoint's
  own final review pass: a test appended via a raw Bash heredoc (`cat >>`) bypasses the
  `PostToolUse` hook entirely, since it only fires on Edit/Write tool calls. Caught at 205 lines
  on `tests/test_compose_scene.py`, fixed by moving the test to its own file
  (`tests/test_caption_zone_exemption.py`). **Worth remembering going forward: a raw shell append
  to a `.py` file gets none of the automatic `ruff check --fix`/`ruff format`/line-count
  enforcement Edit/Write gets — prefer Write for new files and Edit for existing ones, even when
  a shell heredoc feels faster.**

## Environment state

- `RUNTIME_ENV=azure`. Backend (`uvicorn api.main:app`, **no** `--reload`, restarted twice this
  session to pick up the caption fix and then the logging fix) and frontend (`npm run dev` in
  `web/`, also restarted once for a clean module graph after two file deletions) are both running
  for the user as of this checkpoint — confirm they're still up before assuming a fresh render
  will work.
- Two real jobs from this session's own verification remain on disk under `artifacts/_api_run/`:
  `a662bdf1881743c1a2b830f9f4bbb56c` (DNS resolution, 6 segments, one real degraded/re-authored
  segment) and `a2365c0bc4534e0f960cf62f8382e937` (TCP handshake, 6 segments, also one real
  degraded segment) — both succeeded end to end, both are what D171's finalize timing numbers
  came from.

## Gotchas carried forward, still true

- **Never run `uvicorn --reload` on Windows for this app** — documented in `api/main.py`'s own
  docstring; breaks every subprocess-shelling call non-deterministically.
- **A backend started without `--reload` gives no signal that it's serving stale code.** Restart
  it by hand after any pipeline-relevant edit, every time.
- **The `PostToolUse` quality hook only fires on Edit/Write, never on a raw Bash file write** —
  see "Also fixed this session" above. This is now a demonstrated real failure mode, not a
  theoretical one.
- **Opus plans, Sonnet builds — this is not self-enforcing.** Check the current-model line after a
  plan is approved and before the first `Write`/`Edit`/`Bash` of a build.
- `graph_diagram` is deliberately excluded from `_SORTABLE_ITEM_FIELDS` and must stay that way —
  K3's fix is a clamp, not a re-sort.
- **`logging.basicConfig` is now called in `api/main.py`.** If a future session adds its own
  logging configuration elsewhere (a test fixture, a script), remember `basicConfig` is a no-op
  once root handlers exist — order of configuration now matters in a way it didn't before this
  session, in the unlikely case something else tries to configure logging first.

## Known gaps / open questions, unresolved this session

- **K2's `.srt`-timing anomaly did not reproduce** on this session's own verification runs (D171)
  — consistent with D162's Blob-upload-latency guess being real but intermittent, not with the
  guess being wrong. Not confirmed either way, and no longer worth chasing now that finalize is
  ~14s instead of the dominant cost.
- T18F (vision critique/revision loop, full validation render, pipeline speed) is still `todo`,
  unchanged this session — its own entry in `tasks.md` has the full scope and history.
- T18I is still marked `in progress` in `tasks.md`, unchanged this session — not touched, not
  investigated. Read its own entry before assuming it's either safe to ignore or ready to resume.
- T18I's own two older open items (the `SceneLayout.SINGLE` combined-height constraint, a true
  parallel-to-a-line annotation candidate geometry) remain untouched, not part of this session.
- Cloud deployment (T34/T35) remains deliberately parked behind video quality, unchanged.
