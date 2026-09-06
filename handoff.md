# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

## What just happened

**T18M items 1-3 were built, verified against a real re-render, and merged into `cloud`.** D191
diagnosed four defects from a real 15-segment cloud render and built nothing; this session built
items 1-3 on `dev` (per D191's own branch-split rule), verified them end-to-end against a second
real render of the same topic, then merged `dev` into `cloud`. Full details: `tasks.md`'s T18M
entry, `decisionlog.md` D192.

**Measured result:** fallback rate on "teach me about differential and integral calculus" went
from 4/15 (27%, the D191 baseline) to **1/15 (6.7%)**, job `24a8f261-d260-4e09-a08d-a7a8640c6245`.
The one remaining fallback (segment 10, a dense `graph_diagram`) is now diagnosable — a genuinely
different problem than the vocabulary-gap fix that closed the other three — and was scoped as its
own task, **T40**, rather than guessed at this session.

### What shipped (T18M items 1-3, commit `5112f4a` on `dev`, merged into `cloud`)
1. `clipped_text` added to `rendering/geometry_findings.py::_CONTENT_SIZING_CODES`; an
   unrecognised finding code now logs a `WARNING` naming it, so the next vocabulary gap surfaces
   in one render instead of three sessions later. Failed attempts now preserve their own scene and
   full finding strings (`RenderOutcome.findings`, new `core/graph/nodes/render_diagnostics.py`) —
   this is the mechanism that made segment 10's real diagnosis (see T40) possible.
2. `rendering/renderable.py`'s single-block `entrance_start` capped at `_MAX_ANCHOR_ENTRANCE =
   2.0`s (multi-block untouched) — confirmed firing live (a 5.26s anchor capped to 2.00s).
3. `core/graph/nodes/scene_fallback.py`'s fallback title card now derives `key_terms`
   deterministically from the segment's own narration (verbatim fragments, capped at 4 chips, no
   LLM call) instead of hardcoded `[]`; subtitle truncated instead of the full `segment.summary`.
   Confirmed live: segment 10's fallback card showed 4 chips staged at
   0.09s/5.26s/8.41s/13.6s.

`web/openapi.json`/`web/src/api/schema.d.ts` were regenerated for the new `RenderOutcome.findings`
field — no `web/` logic change needed (`job-adapter.ts` destructures only what it uses, the
frontend-insulation guarantee working as designed). `project-reviewer` ran clean before commit;
full pytest/ruff/boundary/web gates all green both on `dev` before merge and on `cloud` after.

### T18M item 4 — still open, on `cloud`
**In-browser video playback is still broken right now.** `VideoPlayer.tsx`'s
`crossOrigin="use-credentials"` requires the whole redirect chain, including the Blob Storage SAS
target, to answer with CORS headers; the storage account (`sbitesartifacts25817`) has zero CORS
rules configured. Downloads work (not subject to the same check); playback doesn't. Fix: a CORS
rule on the existing, Bicep-unmanaged storage account, added as an idempotent
`scripts/deploy_cloud.sh` step. Not attempted this session — D191's own ordering said item 4 only
after items 1-3 land, which they now have, so this is unblocked for a future session.

### T40 — new task, not built
The one remaining fallback (segment 10 of the verification job) is a 6-node `graph_diagram` that
still overlapped after the LLM's own one re-author attempt shrank it to 5 nodes — a real capacity
question (how many node+caption pairs the `graph_diagram` "graph" layout can place without
overlap), not a vocabulary gap. Both failed attempts' full scenes and findings are preserved on
`Storage` at `{job_id}/segments/10/failed_scene_attempt{1,2}.json` for
`24a8f261-d260-4e09-a08d-a7a8640c6245` — read them directly rather than re-deriving. Full scope in
`tasks.md`'s T40 entry.

## Environment state

- **Branch `cloud`**, now holding T34/T35/T38A/T38B **and** T18M items 1-3 (merged from `dev`).
  `dev` and `cloud` are back in sync on everything through this merge — `dev` has no commits
  `cloud` lacks. Not pushed to `origin/cloud` yet (was already 1 commit ahead before this session's
  merge; now further ahead).
- The deployed stack is live and auth-correct: `https://lively-meadow-05448450f.6.
  azurestaticapps.net` (SWA) talking to
  `https://ca-sbites-api.politeforest-8877ab80.eastus.azurecontainerapps.io` (API). Unchanged this
  session — the merged pipeline fixes have not yet been deployed to this live stack (T35's deploy
  step wasn't re-run); the container image there still predates T18M.
- **In-browser video playback is still broken on the live deployed stack** (T18M item 4, above) —
  unrelated to and unfixed by this session's pipeline work.
- `RUNTIME_ENV=azure`, `QUEUE_ENV=local`, `EVENTS_ENV=local`, `RUN_INPROC_WORKER=true` (local),
  `RENDER_ENV=local` — all unchanged. This session's verification render ran locally via `cli.py`,
  not against the deployed container.
- `RENDER_MAX_CONCURRENCY=1` — still unmeasured/untuned, still T39, still nobody's task.

## Known gaps / open questions, unresolved this session

- **T18M item 4 (Blob CORS / in-browser playback)** is the next piece of this task — on `cloud`,
  unblocked now that items 1-3 are merged in. See "T18M item 4" above for the exact fix.
- **T40 (`graph_diagram` capacity)** — diagnosed with real preserved evidence, not built. See
  above and `tasks.md`.
- **The deployed container image predates this session's pipeline fixes.** If the next session's
  goal involves the *live* deployed video quality (not just local `cli.py` runs), a redeploy
  (T35's image-build step) is needed first — not assumed to have happened automatically.
- `cloud` has local commits not yet pushed to `origin/cloud` — confirm before assuming the remote
  reflects this state.
- D141's `Copy Link` UI feature — still not redesigned, still not blocking anything.
- The Dockerfile's `USER` directive and `RENDER_MAX_CONCURRENCY` — still T39, still nobody's task.
