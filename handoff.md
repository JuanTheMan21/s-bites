# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

## What just happened

**All four T18M items are now done.** D191 diagnosed four defects from a real 15-segment cloud
render and built nothing; this session built items 1-3 on `dev` (D192), pushed further into T40's
diagnosis at the user's request (D193), then fixed and applied item 4 live (D194). Full details in
`tasks.md`'s T18M entry and `decisionlog.md` D192-D194.

### Items 1-3 (commit `5112f4a` on `dev`, merged into `cloud`)
1. `clipped_text` added to `rendering/geometry_findings.py::_CONTENT_SIZING_CODES`; an
   unrecognised finding code now logs a `WARNING` naming it. Failed attempts now preserve their own
   scene and full finding strings (`RenderOutcome.findings`, new `core/graph/nodes/
   render_diagnostics.py`) — this is the mechanism that made T40's diagnosis possible.
2. `rendering/renderable.py`'s single-block `entrance_start` capped at `_MAX_ANCHOR_ENTRANCE =
   2.0`s (multi-block untouched) — confirmed firing live (a 5.26s anchor capped to 2.00s).
3. `core/graph/nodes/scene_fallback.py`'s fallback title card now derives `key_terms`
   deterministically from the segment's own narration instead of hardcoded `[]`; subtitle
   truncated instead of the full `segment.summary`. Confirmed live: 4 chips staged over time.

**Measured result:** fallback rate on "teach me about differential and integral calculus" went
from 4/15 (27%, D191's baseline) to **1/15 (6.7%)**, job `24a8f261-d260-4e09-a08d-a7a8640c6245`.

### Item 4 (commit on `cloud` this session — Blob CORS)
`VideoPlayer.tsx`'s `crossOrigin="use-credentials"` needed the Blob Storage SAS redirect target to
answer with CORS headers; the storage account had zero rules. Fixed: `scripts/deploy_cloud.sh`
step 7/7 (`az storage cors clear` + `add`, origins = the SWA URL + `localhost:5173`). **Applied
live** against the real deployed storage account this session, not just committed — verified with
real HTTP requests (a preflight `OPTIONS` against an actual video SAS URL now returns the correct
`Access-Control-Allow-Origin`/`-Allow-Credentials`; a ranged `GET` returns
`Access-Control-Expose-Headers`). **Not verified by pressing play in a real signed-in browser
session** — that needs the user's own Microsoft/Entra sign-in, which the agent could not do on
their behalf. **The user should confirm playback directly next time they open the app.**

### T40 — new task, precisely diagnosed, not built
Segment 10's one remaining fallback (a 5-node `graph_diagram` chain) is a genuine **physical
capacity ceiling**, not a spacing constant to retune: reproduced locally (real `compose_scene` +
`PlaywrightHyperFramesRenderBackend.validate_geometry`, real `hyperframes check --json`), which
named the exact colliding elements. 4 gaps × ~250px/node needed = 1000px; the safe vertical band
before the caption zone is only ~335px. The real fix is a new serpentine/zigzag layout capability
in `computeLayeredLayout` (`rendering/templates/_block_graph_diagram.html`) — a template with a
five-round hardening history where every fix needed live re-verification against several other
diagram shapes. Deferred rather than rushed. Full math, the disproven first hypothesis
(caption-vs-caption — checked live, already correctly mitigated), and the exact repro method are
in `tasks.md`'s T40 entry and `decisionlog.md` D193 — read those before touching this file.

## Environment state

- **Branch `cloud`** now holds T34/T35/T38A/T38B, all of T18M (items 1-4), and D193's T40
  diagnosis. `dev` and `cloud` are in sync through the T18M merge (`dev` has no commits `cloud`
  lacks). **Pushed to `origin/cloud`** — confirm this actually happened if picking up mid-session;
  check `git log origin/cloud..cloud` for anything still local.
- The deployed stack: `https://lively-meadow-05448450f.6.azurestaticapps.net` (SWA) talking to
  `https://ca-sbites-api.politeforest-8877ab80.eastus.azurecontainerapps.io` (API). **CORS is now
  live-fixed on the storage account** (`sbitesartifacts25817`) — confirmed via direct HTTP tests.
  **The deployed container image still predates T18M's pipeline fixes (items 1-3)** — those were
  verified via local `cli.py`, not the deployed container; a redeploy (T35's image-build step) is
  needed before the *live* stack's video quality reflects items 1-3.
- `RUNTIME_ENV=azure`, `QUEUE_ENV=local`, `EVENTS_ENV=local`, `RUN_INPROC_WORKER=true` (local),
  `RENDER_ENV=local` — all unchanged.
- `RENDER_MAX_CONCURRENCY=1` — still unmeasured/untuned, still T39, still nobody's task. The user
  asked about this mid-session; told explicitly it's still just a tracked, undone task.

## Known gaps / open questions, unresolved this session

- **Confirm playback in an actual signed-in browser session** — the one part of T18M item 4 this
  session could not verify itself. Should be quick; the underlying mechanism is confirmed fixed.
- **T40 (`graph_diagram` deep-chain layout capacity)** — diagnosed exactly, not built. See
  `tasks.md` and D193. Real scope: a new zigzag/serpentine layout mode in a heavily-shared,
  five-times-hardened template — budget real time and re-verification against other real
  `graph_diagram` jobs, not a quick patch.
- **The deployed container image predates T18M's pipeline fixes.** A redeploy is needed if the
  next session's goal is the *live* stack's video quality, not just local runs.
- **T39 (Dockerfile `USER`, `RENDER_MAX_CONCURRENCY` tuning)** — still nobody's task, deferred
  three times now (T35, T38A, T38B) plus this session's own mention. If it comes up again, it may
  be time to actually schedule it rather than defer a fourth time.
- D141's `Copy Link` UI feature — still not redesigned, still not blocking anything.
