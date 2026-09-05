# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

_Last updated: 2026-09-04 · T37 (frontend visual redesign) built, reviewed, and closed out this
session · reviewed by `project-reviewer` (three passes) and `impeccable-finish-reviewer` (a
two-round fix loop) · about to be committed and pushed to `origin/dev`_

---

## Where we are

**T37 is done.** Session arc: merged in `8ebda33`/`7e1a192` (T24-T28+T36, the React frontend +
SCORM export, built on another machine in a prior session — not re-reviewed here, already
reviewed then), then built T37 against D144's gate, then extended it with a second round of
user-driven polish after the first round was reviewed and approved.

**Part 1 — the gated redesign (D144's actual scope):**
1. Ran Impeccable's real direction workflow for real this time (`PRODUCT.md`/`DESIGN.md` written,
   `init`/`document`/`critique` all run). The live catalog roll came back degraded (Node's own
   `fetch` couldn't reach `impeccable.style`'s API even though `curl` could — an unresolved
   Node-only proxy/cert quirk on this machine, not a sandbox network block) — built a grounded
   7-candidate list by hand instead, per the skill's documented fallback. D145.
2. Presented the tool's anti-rut assignment (a subtitle/caption-editor world) alongside the
   top-ranked grounded candidate as an "Impeccable's Pick" card. **User picked the Pick**, not the
   assignment — a broadcast/production-timeline direction (Premiere/Descript-style). D145.
3. Built it: `ClipTrack.tsx` (new) — a horizontal timeline rail with a real waveform (deterministic
   per-bar heights keyed to real segment count, never fabricated audio data), a sweeping playhead,
   and real per-phase timecodes read off actual SSE event timestamps. Replaces the old
   `ProductionStrip.tsx`/`FrameBudgetMeter.tsx` (both deleted). Fixed a real, pre-existing bug in
   the same pass: `domain/tier.ts` referenced CSS vars (`--tier-0`) that don't exist under Tailwind
   v4's `@theme` (actual name: `--color-tier-0`) — tier badges/meters had been rendering colorless.
4. A two-round `impeccable-finish-reviewer` loop (spawned fresh each time, no forked context) found
   and fixed: the segment display broke the direction contract's explicit "not a card grid" promise
   (fixed by a new `ClipStrip.tsx` — a horizontal snap-scroll strip — used only in the live-progress
   view; `SegmentGrid`'s card grid is kept, scoped to `JobResult.tsx`'s finished/browse view only,
   D146); the chosen world's own "waveform" device was missing (added); no scroll-affordance cue
   on the new strip (added a fade mask). Final verdict: everything `web/`-owned resolved and ships
   clean. One open item — `StageTicker` sometimes shows a repeated generic label instead of a real
   segment title — was traced to `api/events.py`/`core/graph/pipeline.py` not always populating
   `segment_title`, confirmed out of a frontend task's territory, deliberately not fixed. Still
   open; see "Known gaps" below.
5. `project-reviewer` (first pass, scoped to the above): found and fixed a timecode-formatting bug
   in `SegmentCard.tsx` (didn't carry seconds into minutes — `"0:75.0"` instead of `"1:15.0"`) and
   a dead `truncate` CSS class in `PlayfulCaption.tsx` (missing `min-w-0` in a flex row).

**Part 2 — user-driven follow-up, after Part 1 shipped and was reviewed:**
6. User asked for the whole UI to be extended beyond the loading screen, and flagged the app was
   "too small at 100% zoom." Widened every page container (`max-w-4xl`→`max-w-6xl` or similar),
   bumped headings/stats/padding across `JobHeader`, `WrapReport`, `FailureCard`, `JobCard`, and
   the shared `Card`/`Pill`/`EmptyState` primitives, amplified `JobCard`'s hover to an accent-glow
   shadow matching `Button`'s. `project-reviewer` (second pass) caught a real WCAG contrast
   regression this introduced (accent-colored hover text measured 3.13-3.50:1, below the 4.5:1
   floor, in some cases *worse* than the resting state it replaced) and a disproportionately wide
   `EmptyState` on `NotFoundPage` (fixed by capping `EmptyState`'s own width, not just that one
   page's container). Both fixed.
7. User asked for four more things directly: a dark/light toggle (built — `theme-store.ts` +
   `ThemeToggle.tsx`, Zustand + `persist`, defaults to `'light'`, never derived from
   `prefers-color-scheme`, D148), an animated example-prompt typewriter in the composer's
   placeholder (built — `use-placeholder-cycle.ts`, cycles 4 example topics, only active while the
   topic field is empty), the milestone pills labeled/iconed instead of bare text (`MilestoneRow`
   now has an "Achievements" label + a new `IconTrophy`), and the hero copy rewritten to mention AI
   and explain what "render it while you watch" actually means.
8. Building the toggle surfaced that `--color-accent` used as literal text color was broken in
   *more* places than pass-2 caught — including `Button.tsx`'s primary variant (white text on solid
   accent, 3.50:1, **pre-existing from before this session**, not introduced by it). Fixed with two
   new tokens, `--color-accent-ink` (text on light/tinted backgrounds) and `--color-accent-solid`
   (solid-fill button backgrounds) — D147. `project-reviewer`'s third/final pass then caught two
   more real bugs in the *new* theme-toggle code itself: `useEffect` (not `useLayoutEffect`) meant
   a returning dark-mode visitor saw one frame of light tokens on every load, and
   `html { color-scheme: light }` was never overridden inside the dark token block, so the toggle
   would have left native browser chrome (scrollbars, form controls) light-themed against a
   near-black page. Both fixed — see D148.

**Verified:** `pytest` full suite green, `ruff check .` clean, `web`'s `tsc -b --noEmit`/
`eslint .` clean, `vitest run` 40/40, `npm run build` succeeds (511-516 KB JS / ~165-167 KB
gzipped — grew slightly from T24-T28's 503/163, still the same `motion`+Radix+Query+Router cost,
code-splitting still the lever if it ever matters, still not done). Both boundary greps empty (one
docstring-text hit in `core/graph/node_timing.py`, not a real import, unchanged from before).

## Known gaps and open questions

**New, found this session:**
- **`Pill`/`StatusPill`'s `run`/`ok`/`warn`/`bad` tones fail WCAG AA in light mode** (2.82-4.43:1
  against a 4.5:1 floor) — the exact same "saturated color as literal text on its own light tint"
  defect this session fixed for `accent` (D147), but pre-existing and untouched, since T37's scope
  was a visual-direction redesign, not a full accessibility audit of every existing token pairing.
  Drives the "Running"/"Succeeded"/"Failed" badge on every job card and job header — real,
  constantly-visible UI. Worth a dedicated quick pass: same fix pattern as `--color-accent-ink`
  (derive a darker per-tone "-ink" shade), four tones this time instead of one.
- **`StageTicker` sometimes shows a repeated generic label** ("Recording narration" three times
  with no distinguishing segment title) instead of the real segment title. Traced to
  `api/events.py`'s `_stage_summary` / `core/graph/pipeline.py`'s `Send("synthesize_segment", ...)`
  not always carrying `segment_title` through — investigated this session, not fixed (`core/graph`/
  `api/` territory, correctly out of a frontend task's scope per CLAUDE.md's T18/frontend seam).
  Worth a `core/graph` session picking this up specifically.
- **`web/`'s production bundle is ~516 KB JS / ~167 KB gzipped**, up slightly again. Still not
  code-split. Still not urgent, still the lever if it ever becomes one.
- **No new automated tests for this session's new components** (`ClipTrack`'s waveform/timecode
  math, `ClipStrip`, `use-placeholder-cycle.ts`, `theme-store.ts`). All 40 pre-existing frontend
  tests still pass unchanged (none of them touch anything this session added), but the new logic
  itself has zero direct coverage. Worth a follow-up pass, especially `ClipTrack`'s
  `phaseStartOffsets`/`barHeightPct`/`formatTimecode` — pure functions, cheap to test.

**Carried forward, unchanged from before this session:**
- T18F and T18E's three findings — still untouched (no `rendering/`/`core/block_types.py` work
  this session either, consistent with CLAUDE.md's invariant 5).
- No coverage gate exists (D42). T10 (`RUNTIME_ENV=local`'s Ollama/Kokoro) still unclaimed.
- `RENDER_MAX_CONCURRENCY=2` still unmeasured under real concurrent load.
- `hyperframes check` still non-deterministically flaky at times (D96).
- `pipeline-debugging`'s documented artifact layout still stale (T18D flagged it).
- `api/runner.py::WORKING_ROOT` still has no cleanup.
- `feature/scene-composition` still unmerged into `dev` — still the user's own call, unchanged
  standing note since T18B.
- Scope: 38 tasks across 8 iterations, plus T18A-F. T37 is now `done`.

## Before the next session

**T37 is closed.** Nothing is blocking the next task. Candidates, in backlog order: **T34/T35**
(Iteration 5.5, cloud execution — Service Bus job queue + Container Apps render backend, both
currently stubbed) or **T29-T33** (Iteration 6, RAG — scheduled last per the backlog's own
ordering, and a prior session's explicit recommendation was to finish frontend polish before
opening RAG's larger surface, which T37 now has). No explicit user direction on which yet — ask,
or default to T34/T35 as the next backlog item.

If more frontend polish comes up first: the `Pill`/`StatusPill` contrast gap above is the most
concrete, ready-to-pick-up item — same fix pattern already proven this session (`D147`), just
applied to four more tones.

**`feature/scene-composition` is still unmerged into `dev`** — same standing note as every
checkpoint since T18B, still the user's own decision, not automatic.

## Environment state

| | |
|---|---|
| Models | This session ran on **Opus** for part of the conversation before the user caught it and ran `/model sonnet` explicitly, mid-session — confirmed via CLAUDE.md's mandatory self-check before the build phase began. Worth checking again at the start of any session; this has now been the wrong-model failure mode four times running (T18A, T18B, and twice this session's own preamble). |
| Browser automation | Still no browser MCP connected (`playwright` MCP unavailable this session too). All live-browser verification used Python Playwright directly via `scripts/shoot_ui.py` (new this session — a screenshot harness, `--url`/`--dark`/`--mobile`/`--skip-submit` flags, writes to whatever `--out` dir is given; not committed test infra, a manual iteration tool). |
| `RUNTIME_ENV` | `azure`, unchanged. |
| `RENDER_ENV` | `local` (D100), unchanged. |
| `QUEUE_ENV` | `local`, now also present in this machine's own `.env` (was already in `.env.example`; this session's `.env` had drifted from it — D139 explains why it's needed). |
| `WEB_ORIGINS` | `http://localhost:5173` default, unchanged. |
| `FRAME_BUDGET` / `FPS` | `9500` / `24`, unchanged. |
| Git | `dev`, fast-forwarded this session from `5fa267a` to `7e1a192` (pulling in another machine's T24-T28+T36 work), then this session's own T37 work on top — about to be committed and pushed. `feature/scene-composition` still unmerged, unchanged. |
| Disk space | **This machine's C: drive was completely full (0 bytes free) at session start** — blocked `npm install` outright. User freed some space; this session also cleared the npm cache and user `%TEMP%` (recovering to ~1-2 GB free, enough to complete the session). Worth checking `Get-PSDrive C` at the start of any session on this machine before assuming disk operations will succeed — this was not a one-off. |
| Azure spend | None this session — all verification used `scripts/serve_fake.py` (free, no real credentials touched) plus static screenshots. No real Azure render was run. |
| Node | v26.6.0 (this machine) vs. v24.16.0 (the other laptop that built T24-T28+T36) — `npm install`/build worked fine here, but this version mismatch is worth remembering if something Node-specific misbehaves that didn't on the other machine. **Node's own `fetch` could not reach an external HTTPS API this session while `curl` on the same machine could** — an unresolved, unexplained network quirk specific to this machine's Node runtime, not a harness sandbox restriction. Affected Impeccable's `concept-seed.mjs` catalog roll (D145); may affect anything else that shells out to Node and expects real network access. |
| `web/node_modules` | Was missing at session start (never installed on this machine before); installed this session, ~1.2 GB free afterward. |

## Gotchas worth remembering

**New this session:**
- **`useEffect` vs `useLayoutEffect` matters for anything that writes to the DOM outside React's
  own tree** (here: `document.documentElement.dataset.theme`, which CSS selectors key off
  directly). `useEffect` fires after the browser's first paint — a value that's already correct in
  application state (Zustand's `persist` rehydrates `localStorage` synchronously, confirmed by
  reading the middleware source) can still cause a visible one-frame flash if the DOM write that
  actually matters happens in the wrong hook. `useLayoutEffect` runs before paint; use it for this
  class of problem, not `useEffect`.
- **A dark-mode/theme override block needs `color-scheme: dark` inside it, not just re-themed CSS
  custom properties.** `color-scheme` is what tells the browser to theme its *own* chrome
  (scrollbars, `<select>`/date-picker defaults, form controls) — omitting it left those surfaces
  light-themed against an otherwise-complete dark page, invisible while the token was dead CSS
  (dark mode unreachable) and only became a live bug once a real toggle shipped.
- **A color used as literal text needs its own contrast check against every background it actually
  sits on — an accent/highlight color that looks fine as a border or icon fill routinely fails as
  text color on the same background**, because WCAG's text-contrast floor (4.5:1) is higher than
  its non-text/graphics floor (3:1) that borders and icons are held to instead. Compute the actual
  ratio (`(L1+0.05)/(L2+0.05)` on relative luminance) rather than eyeballing "the accent is
  vibrant, it'll pop" — this session found the same defect in five separate places by actually
  computing it, including one pre-existing bug (`Button.tsx`'s primary variant) that had shipped
  and passed two prior review rounds because nobody had checked the number.
- **A Bash `cd` into a subdirectory (e.g. `web/`) persists across tool calls in the same session and
  leaks into the next `PreToolUse` hook invocation**, even for an unrelated `Write`/`Edit` call —
  `hook_boundary.py` gets invoked with the wrong relative path and fails with a confusing
  `can't open file '...\web\scripts\hook_boundary.py'` error. `cd` back to the repo root (or use a
  subshell / absolute paths) after any Bash command that changes directory, not just before Bash
  calls — this bit the session twice despite already being a known gotcha from a prior session.
- **Impeccable's `concept-seed.mjs`/direction-roll machinery assumes real network egress to
  `impeccable.style`**; when that fails (see "Node's own `fetch`" above), the documented fallback
  (build a grounded candidate list by hand, disclose the substitution, still honor the anti-rut
  assignment mechanism) works and is sanctioned by the skill's own text — don't skip the direction
  round entirely just because the roll degraded.
- **`serve-question.mjs`'s browser-based decision page needs to bind a local port**, which the
  skill's own docs flag as a common sandboxed-shell failure point. This session used
  `AskUserQuestion` (with ASCII-art `preview` blocks standing in for wireframe cards) as the
  structured-question-tool fallback instead, rather than fighting the port bind — also sanctioned
  by the skill's own text ("the structured question tool remains the no-browser fallback").

**Carried from earlier sessions, still true:**
- The frontend's own client-side routes can collide with backend API routes proxied from the same
  origin — namespace API calls under a distinct prefix (`/api`), not in the backend's own paths.
- `npx --no-install X` resolves `node_modules/.bin` from cwd upward, never downward.
- A pydantic model's prompt-embedded requirement is a legitimate signal a test fixture can read
  back, rather than needing the count told out-of-band.
- `AsyncSqliteSaver.from_conn_string(path)` creates `path` on disk the instant it connects.
- Every real invocation of this graph must pass `durability="sync"` explicitly.
- `Storage.url()`'s scheme is the only safe way to branch redirect-vs-stream at the API layer.
- `FakeLLMProvider`'s strict-FIFO queue breaks under real concurrency with mixed schema types —
  `PhaseQueueLLMProvider` is the fix pattern.
- The quality hook strips an import added before its first use — add the import in the same tool
  call as its first real usage.
- 200-line ceiling, enforced on write. Split by responsibility, don't compress.
- `artifacts/` is gitignored. Nothing you need to keep goes there.
- A graph's checkpointed state can have a field on more than one channel that looks related but
  isn't kept in sync until one specific node runs (D142) — check before assuming a mid-run snapshot
  reflects "live" progress.
- A React key built from a timestamp is not safe under real concurrency (D143) — use the item's
  stable position or a real unique id.

---

## Merge note (this session, T18I kickoff)

Merged `feature/scene-composition` (T18G/T18H, plus a WIP slice of T18I) into `dev`, curated:

- **Taken wholesale:** the geometric-correctness gate (`validate_geometry`), its finding
  parsing (`rendering/geometry_findings.py`), all template fixes (arrowheads, caption-band drop,
  graph layout, text-panel shrink), `AnnotationTargetKind` (ITEM/LINK) groundwork for
  edge-parallel annotation placement, and the branch's own test suite.
- **Re-homed, not dropped:** `VideoJob`/`JobStatus` stay in `core/models.py` rather than moving to
  `core/video_job.py` as the branch had it — actually moved to `core/video_job.py` after all, once
  `Segment.render_outcome` pushed `core/models.py` over the 200-line ceiling; `api/`'s six
  importers and `cli.py` now import both from `core.video_job`. No behavioural change, no API
  contract change — confirmed via `dump_openapi` diff.
- **Treated as a starting point, not finished work:** `core/graph/nodes/scene_reauthor.py`,
  `scene_fallback.py`, `core/render_outcome.py`, and `render_scene.py`'s retry rewrite were
  committed WIP on the branch, never reviewed or checkpointed. This session's Phase 1 reviews and
  finishes that logic rather than merging it as-is.

Full task scope for this session: see `tasks.md`'s T18I entry, rewritten to cover geometry-gap
closure, per-segment resilience, variety enforcement in code, and annotation placement/density —
all from the user's own direct feedback on real rendered output.
