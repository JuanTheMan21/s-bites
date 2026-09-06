# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

## What just happened

**All four T18M items are done, plus a live-reported waveform bug fixed reactively mid-session.**
D191 diagnosed four defects from a real 15-segment cloud render and built nothing; this session
built items 1-3 on `dev` (D192), pushed further into T40's diagnosis at the user's request (D193),
fixed and applied item 4 live (D194), then fixed a real user-reported "invisible waveform"
frontend bug found while two live jobs were running (D195). Full details: `tasks.md`'s T18M entry,
`decisionlog.md` D192-D195.

### T18M items 1-3 (commit `5112f4a` on `dev`, merged into `cloud`)
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

### T18M item 4 (commit on `cloud` — Blob CORS)
`VideoPlayer.tsx`'s `crossOrigin="use-credentials"` needed the Blob Storage SAS redirect target to
answer with CORS headers; the storage account had zero rules. Fixed: `scripts/deploy_cloud.sh`
step 7/7 (`az storage cors clear` + `add`). **Applied live** against the real deployed storage
account, verified with real HTTP requests (correct `Access-Control-Allow-Origin`/`-Allow-
Credentials` on preflight; `Access-Control-Expose-Headers` on a ranged GET). **Not verified by
pressing play in a real signed-in browser session** — needs the user's own sign-in.

### D195 — waveform invisible during early job progress (commit `374b934` on `dev`, merged into `cloud`)
User reported live, mid-session: two jobs, same prompt, two accounts/browsers — one showed the
waveform, one showed a plain black box with only the playhead moving, zero console errors. Traced
to `WaveScope.tsx`'s `DIM_COLOR` (the "not yet reached" wave color) being effectively 4-14% opaque
against the near-black canvas background — invisible during a job's `outline` phase (which has no
per-segment progress signal, so `fillPct` sits near 0 and the ENTIRE canvas draws from this
near-invisible color). Not a browser bug — the two jobs were just at different points in their own
lifecycle. Raised `DIM_COLOR`'s alpha from 0.14 to 0.38; verified visually (not just by the
numbers) with a standalone canvas repro screenshotted via Playwright before touching the real file.
Also fixed a real, unrelated finding the project's own design-quality hook surfaced while editing
this file: the D172 fallback bar animated `width` (layout property) instead of `transform:
scaleX()` (compositor-only) — fixed alongside, tests updated to match.

**⚠️ This frontend fix is NOT yet visible on the live deployed site.** It's committed and pushed
to both `dev` and `cloud`, but the deployed Static Web App still serves whatever `web/dist` build
`scripts/deploy_cloud.sh`'s step 5/6 last produced — this session did NOT re-run that build/deploy
step (only the CORS-only commands from step 7 were run directly against Storage, deliberately, to
avoid an unnecessary container rebuild). **A frontend redeploy is needed before a user watching a
live job actually sees the brighter waveform** — either re-run `scripts/deploy_cloud.sh` in full,
or manually redo just its step 5 (`cd web && npm run build` + `npx @azure/static-web-apps-cli
deploy`).

## Environment state

- **Branch `cloud`** now holds T34/T35/T38A/T38B, all of T18M (items 1-4), D193's T40 diagnosis,
  and the D195 waveform fix. `dev` and `cloud` are in sync (no commits either lacks from the
  other). **Pushed to `origin/cloud` and `origin/dev`** — confirm this actually happened if picking
  up mid-session (`git log origin/cloud..cloud`, `git log origin/dev..dev`, both should be empty).
- The deployed stack: `https://lively-meadow-05448450f.6.azurestaticapps.net` (SWA) talking to
  `https://ca-sbites-api.politeforest-8877ab80.eastus.azurecontainerapps.io` (API).
  - **CORS is live-fixed** on the storage account (`sbitesartifacts25817`) — confirmed via direct
    HTTP tests, no redeploy needed for this part.
  - **The deployed container image predates T18M's pipeline fixes (items 1-3).** Those were
    verified via local `cli.py` only.
  - **The deployed frontend predates the D195 waveform fix.** See the warning above.
  - A full `scripts/deploy_cloud.sh` re-run would pick up all three of these at once (new container
    image with items 1-3, rebuilt frontend with D195) — worth doing together rather than
    separately, next time either is needed live.
- `RUNTIME_ENV=azure`, `QUEUE_ENV=local`, `EVENTS_ENV=local`, `RUN_INPROC_WORKER=true` (local),
  `RENDER_ENV=local` — all unchanged.
- `RENDER_MAX_CONCURRENCY=1` — still unmeasured/untuned, still T39, still nobody's task.

## Known gaps / open questions, unresolved this session

- **A full redeploy is needed for the live stack to reflect this session's fixes** — see above.
  Nothing in this session ran `scripts/deploy_cloud.sh` end-to-end.
- **Confirm playback in an actual signed-in browser session** — the one part of T18M item 4 this
  session could not verify itself.
- **T40 (`graph_diagram` deep-chain layout capacity)** — diagnosed exactly, not built. See
  `tasks.md` and D193. Real scope: a new zigzag/serpentine layout mode in a heavily-shared,
  five-times-hardened template — budget real time and re-verification against other real
  `graph_diagram` jobs, not a quick patch.
- **T39 (Dockerfile `USER`, `RENDER_MAX_CONCURRENCY` tuning)** — still nobody's task, deferred
  three times now (T35, T38A, T38B) plus mentioned again this session without being scheduled.
- D141's `Copy Link` UI feature — still not redesigned, still not blocking anything.
