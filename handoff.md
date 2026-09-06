# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

## What just happened

**No code changed this session beyond the T38B checkpoint already recorded.** After T38B shipped
and the user confirmed T38's actual DoD live (two real Microsoft accounts, `juanthemancr7@gmail.com`
and `skillbites911@gmail.com`, each submitting a job and correctly unable to see the other's — T38
is genuinely done, not just structurally verified), the user ran a real 15-segment job and reported
four real problems. This session **diagnosed all four with hard evidence and wrote a full plan
(T18M), but built nothing** — the user's own explicit instruction was to do the actual work in a
future session, on the right branch. Full plan, findings, and file:line citations:
`C:\Users\juant\.claude\plans\t38-final-stretch-of-serialized-pelican.md`. Short version:
`decisionlog.md` D191.

### The branch split for T18M is load-bearing — read this before starting it
**Items 1-3 (fallback rate, blank-stage timing, fallback card content) are video-pipeline work and
go on `dev`. Item 4 (in-browser playback / Blob CORS) needs the deployed stack and stays on
`cloud`, merged in only after 1-3 land on `dev`.** This was the user's own explicit correction
mid-session, after this session first planned all four as one unit on `cloud` — recorded as its
own memory (`branch-split-cloud-vs-dev.md` in the user's persistent memory directory) specifically
so it isn't relearned the hard way twice. `cloud` and `dev` have never been merged in either
direction and will have diverged — check that before starting T18M.

### The four findings (T18M), each with real evidence from a real job
Evidence job: `eaebea14d7484ef19a82fcd7881f94d3` ("teach me about differential and integral
calculus", 15 segments, 376s), owned by `juanthemancr7@gmail.com`. Its `job.json` is at
`jobs/9188040d-6c67-4c5b-b112-36a304b66dad.00000000-0000-0000-625c-98001dc531b1/eaebea14d7484ef19a82fcd7881f94d3/job.json`
in the `explainer-artifacts` blob container (owner-scoped path — T38A's design working exactly as
intended). Read it directly; every number below came from it.

1. **Fallback rate: 4 of 15 segments (27%) degraded.** One concrete, already-identified cause:
   `rendering/geometry_findings.py::_CONTENT_SIZING_CODES` is missing `clipped_text` — the third
   time a real content-sizing code has been omitted from that vocabulary (after `text_occluded` at
   T18I, `caption_zone_collision` at T18J). Two other failing segments exhausted all 3 retries on
   the same finding code every time and currently **cannot be diagnosed at all** — the failing
   scene and full finding text are discarded on fallback; `RenderOutcome` keeps only codes.
   **The user's stated target is a fallback rate close to zero, not merely improved** — recorded
   as its own memory (`fallback-rate-must-be-near-zero.md`) because it changes what "done" means
   for whoever builds T18M.
2. **A confirmed 10-second blank stage**, video seconds ~48-58 — the user had already reported
   this once before this session traced it. Root cause is exact:
   `rendering/renderable.py:70-74`'s `entrance_start` for a single-block scene is the resolved
   narration-anchor time with **no upper bound anywhere in the timing chain**. Segment 2's anchor
   resolved 49% into its own duration, so the whole block stayed invisible until then.
3. **Fallback title cards are a static wall of text for 21-31 seconds.**
   `core/graph/nodes/scene_fallback.py:23` hardcodes `key_terms=[]`, so the chip-staging animation
   T18G's F3 built (the "blue boxes popping up one by one" the user likes on real title cards) has
   nothing to stage. `render_scene.py`'s own comment justifies the fallback's tier downgrade as
   preserving "staggered chip entrances" — a rationale this same file makes impossible to satisfy.
4. **In-browser video playback is broken — a real T38A regression, not pre-existing.**
   `VideoPlayer.tsx`'s `crossOrigin="use-credentials"` (added in T38A for the cookie) requires the
   *entire* redirect chain, including the Blob Storage SAS target, to answer with CORS headers.
   Confirmed live: `az storage cors list --account-name sbitesartifacts25817 --services b` →
   `[]`, zero rules. Downloads work because they don't go through the same check — exactly the
   symptom reported (playback broken, download fine).

**T39 was also created this session** (in `tasks.md`, not built) to stop container hardening and
render-concurrency tuning from being an unnumbered handoff bullet a fourth time — deferred again
this session, the user's own explicit choice each time.

## Environment state

- **Branch `cloud`**, still holding T38A+T38B, checkpointed and — per the last checkpoint —
  **still not pushed**. Nothing changed this session, so this is unchanged from T38B's own handoff.
- The deployed stack is live and correctly enforcing auth: `https://lively-meadow-05448450f.6.
  azurestaticapps.net` (SWA) talking to
  `https://ca-sbites-api.politeforest-8877ab80.eastus.azurecontainerapps.io` (API). Two real users
  confirmed working, cross-isolated, this session.
- **In-browser video playback is still broken right now** (finding 4 above) — anyone opening the
  deployed frontend today can watch the sign-in/job-list/download flow work but will hit a blank
  player. Not fixed this session; T18M item 4 is the fix, gated behind items 1-3 landing on `dev`
  first per the branch-split rule.
- `RUNTIME_ENV=azure`, `QUEUE_ENV=local`, `EVENTS_ENV=local`, `RUN_INPROC_WORKER=true` (local),
  `RENDER_ENV=local` — all unchanged.
- `RENDER_MAX_CONCURRENCY=1` — still unmeasured/untuned, now T39, still not this session's job.

## Known gaps / open questions, unresolved this session

- **T18M is planned, not built.** The next session on it should read the plan file directly
  (`t38-final-stretch-of-serialized-pelican.md`) rather than re-deriving from this summary — it has
  the exact file:line citations, the chosen fix approach for each item, and what NOT to guess at
  (segments 4/12's repeated same-code failures need the preserved-findings fix built first, not a
  blind content-authoring change).
- Whether to merge `cloud` into `dev` — this is now actually load-bearing for T18M's own branch
  plan (items 1-3 on `dev`, merge into `cloud` for item 4), not just a standing open question.
  Check the real divergence between the two branches before starting.
- D141's `Copy Link` UI feature — still not redesigned, still not blocking anything.
- The Dockerfile's `USER` directive and `RENDER_MAX_CONCURRENCY` — now T39, still nobody's task.
