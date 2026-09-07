# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

## What just happened

**All four T18M items are done, a live-reported waveform bug was fixed reactively, and the live
stack was fully redeployed to reflect all of it.** D191 diagnosed four defects from a real
15-segment cloud render and built nothing; this session built items 1-3 on `dev` (D192), pushed
further into T40's diagnosis at the user's request (D193), fixed and applied item 4 live (D194),
fixed a real user-reported "invisible waveform" frontend bug (D195), then ran a full production
redeploy at the user's explicit request — which hit and fixed a real, separate `az acr build`
crash on Windows along the way (D196). Full details: `tasks.md`'s T18M entry, `decisionlog.md`
D192-D196.

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

### T18M item 4 (Blob CORS — commit on `cloud`)
`VideoPlayer.tsx`'s `crossOrigin="use-credentials"` needed the Blob Storage SAS redirect target to
answer with CORS headers; the storage account had zero rules. Fixed: `scripts/deploy_cloud.sh`
step 7/7 (`az storage cors clear` + `add`). Verified with real HTTP requests. **Not verified by
pressing play in a real signed-in browser session** — needs the user's own sign-in, still true.

### D195 — waveform invisible during early job progress (commit `374b934` on `dev`, merged into `cloud`)
User reported live, mid-session: two jobs, same prompt, two accounts/browsers — one showed the
waveform, one showed a plain black box with only the playhead moving, zero console errors. Traced
to `WaveScope.tsx`'s `DIM_COLOR` (the "not yet reached" wave color) being effectively 4-14% opaque
against the near-black canvas background — invisible during a job's `outline` phase (no
per-segment progress signal, so `fillPct` sits near 0 and the ENTIRE canvas draws from this
near-invisible color). Not a browser bug — the two jobs were just at different points in their own
lifecycle. Raised `DIM_COLOR`'s alpha to 0.38; verified visually with a standalone canvas repro
screenshotted via Playwright before touching the real file. Also fixed a real, unrelated finding
the project's own design-quality hook surfaced while editing this file: the D172 fallback bar
animated `width` (layout property) instead of `transform: scaleX()` (compositor-only).

### D196 — full production redeploy, and a real `az acr build` bug found and fixed along the way
User asked for the full redeploy (container rebuild included), explicitly. `scripts/
deploy_cloud.sh` hit a real, reproducible `az acr build` crash on this Windows machine
(`UnicodeEncodeError` while displaying pip's own resolver output for `requirements.txt`) — **five
attempts** to fix it, four of which failed with real evidence each time (`PYTHONIOENCODING=utf-8`,
`PYTHONUTF8=1`, `--no-format`, `AZURE_CORE_NO_COLOR=true` — all confirmed NOT the fix, each ruling
out a specific layer). The actual fix: `--no-logs` on the build call — still queues and blocks
until the build finishes, just never prints the log content that was crashing the process trying
to display it. **Confirmed live the stack was never put in a broken state** by the four failed
attempts (the script's own `EXISTING_IMAGE` guard kept both Container Apps on their last good
image throughout).

**The full deploy succeeded and was verified live, not just by exit code:** both `ca-sbites-api`
and `ca-sbites-worker` on revision `rev1788757547`, API replica confirmed `Running`, `/docs`
returning `200`, frontend rebuilt and redeployed. **The deployed stack now genuinely reflects
everything from this session** — T18M items 1-3, item 4, and D195's waveform fix are all live.

## Environment state

- **Branch `cloud`** now holds T34/T35/T38A/T38B, all of T18M (items 1-4), D193's T40 diagnosis,
  the D195 waveform fix, and D196's deploy-script fix. `dev` and `cloud` are in sync (`dev` has no
  commits `cloud` lacks; `cloud` additionally holds infra-only commits, as intended by the
  branch-split rule). **Pushed to both `origin/cloud` and `origin/dev`** — confirm this is still
  true if picking up mid-session (`git log origin/cloud..cloud`, `git log origin/dev..dev`, both
  should be empty).
- The deployed stack: `https://lively-meadow-05448450f.6.azurestaticapps.net` (SWA) talking to
  `https://ca-sbites-api.politeforest-8877ab80.eastus.azurecontainerapps.io` (API). **Fully current
  as of this session's redeploy** — container image, frontend build, and CORS all reflect the
  latest `cloud` commit. No known gap between source and deployed state right now.
- `RUNTIME_ENV=azure`, `QUEUE_ENV=local`, `EVENTS_ENV=local`, `RUN_INPROC_WORKER=true` (local),
  `RENDER_ENV=local` — all unchanged.
- `RENDER_MAX_CONCURRENCY=1` — still unmeasured/untuned, still T39, still nobody's task.
- **`scripts/deploy_cloud.sh`'s own `az acr build` invocation now uses `--no-logs`** — a future
  redeploy on this same machine should not hit the Windows console encoding crash again. If it
  does anyway (a genuinely different crash, not this one), don't re-try the four approaches D196
  already ruled out — read that entry first.

## Known gaps / open questions, unresolved this session

- **Confirm playback in an actual signed-in browser session** — the one part of T18M item 4 this
  session could not verify itself (needs the user's own Microsoft/Entra sign-in). Now that the
  live stack is fully current, this is the most worthwhile thing to check next.
- **T40 (`graph_diagram` deep-chain layout capacity)** — diagnosed exactly, not built. See
  `tasks.md` and D193. Real scope: a new zigzag/serpentine layout mode in a heavily-shared,
  five-times-hardened template — budget real time and re-verification against other real
  `graph_diagram` jobs, not a quick patch.
- **T39 (Dockerfile `USER`, `RENDER_MAX_CONCURRENCY` tuning)** — still nobody's task, deferred
  three times now (T35, T38A, T38B) plus mentioned again this session without being scheduled.
- D141's `Copy Link` UI feature — still not redesigned, still not blocking anything.
