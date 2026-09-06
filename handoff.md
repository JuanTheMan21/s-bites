# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

## What just happened

**T38A shipped and is checkpointed on branch `cloud`** (not yet pushed — see below).
`project-reviewer` ran during the build itself (not re-run at checkpoint, by the user's explicit
choice) and reported no findings after reading every changed file and running `pytest`/`ruff`
independently. Full reasoning for every non-obvious choice: `decisionlog.md` D183-D187.

### The premise T38's own task text stated turned out to be false, and was reopened
`tasks.md` said "Microsoft Entra ID sign-in (workforce/single-tenant — the company tenant, per user
decision)". Checked live this session: the Azure account (`skillbites911@gmail.com`) is a personal
Microsoft account, its tenant (`skillbites911gmail.onmicrosoft.com`, "Default Directory") has
**exactly one user in it**, and the signed-in user is Global Administrator of it. Single-tenant
sign-in is meaningless against a directory of one. A search of the entire decisionlog at the time
found no D-record for the "company tenant" choice — it was one unexamined line of task prose.

**Resolution (D184), reached with the user, not around them:** tenancy is a runtime config value,
not a code fork. `ENTRA_TENANT_ID=common` (this deployment's actual setting) accepts any Microsoft
identity; `ENTRA_TENANT_ID=<tenant-guid>` + `ENTRA_ALLOWED_TENANTS=<same-guid>` is an ordinary
single-tenant enterprise app — the shape the user's actual employer (`@ust.com`-style, an AD group
gating access) would use. **The validation code is identical either way** — Microsoft's
tenant-independent validation is a documented strict superset of single-tenant validation, verified
against Microsoft Learn this session rather than assumed. Nothing about this needs revisiting; it
is a config change away from a real company deployment whenever one exists to test against.

### What shipped
- **`api/token_verifier.py` + `api/entra_keys.py`** — the full nine-step Microsoft-documented
  token-validation algorithm (signing-key issuer check, `tid`/`iss` cross-check, `alg` pinning,
  audience/scope/app-role checks), tested against real RS256 tokens minted locally
  (`tests/entra_fixtures.py`, `tests/test_token_verifier.py`, 17 tests) and confirmed live against
  Microsoft's real `/common` keys endpoint this session — it published 8 keys, 5 templated-issuer
  and 3 with a literal issuer scoped to `9188040d-6c67-4c5b-b112-36a304b66dad` (the personal-account
  tenant), so the "literal issuer" branch is a real path this deployment's own users take, not a
  hypothetical.
- **`api/auth.py`** — the `Principal` FastAPI dependency (the first `Depends` anywhere in this
  codebase), plus `POST/DELETE /auth/session` for the cookie the header-less browser-native URLs
  need. **`current_principal`** (reads: bearer or cookie) is split from **`mutating_principal`**
  (writes: bearer only) — see the CSRF finding below for why the split exists.
- **`core/video_job.py`** — `owner_id: str | None = None` added to `VideoJob`. Nullable so
  pre-existing job records and LangGraph checkpoints still deserialize under `extra="forbid"`.
- **`api/job_store.py`** — ownership is now the storage key itself
  (`jobs/{owner_id}/{job_id}/job.json`, index likewise per-owner), per D185. There is no
  `if job.owner_id != principal.owner_id` anywhere in the codebase — a wrong owner cannot address
  another owner's record at all, so it hits the same `ObjectNotFound` → 404 path a genuinely
  absent job does. This is what makes the "wrong owner gets 404, never 403" DoD structural rather
  than a check eleven routes each have to remember.
- **`QueuedJob.payload`** (`interfaces/job_queue.py`, existed since T34, always `{}` until now)
  carries `owner_id` from `api/jobs.py` to `api/runner.py`. Zero interface change, zero
  adapter-parity work — confirmed by `project-reviewer`'s own `git diff --stat -- adapters/` that
  neither queue adapter was touched.
- **SAS expiry** (D186): split by consumption pattern rather than one flat value. Streamed media
  (`/video`, segment `/clip`, segment `/audio`) gets 900s; one-shot downloads (`/subtitles`,
  `/scorm`, `/segments/.../scene`) get 300s. The task text's literal "minutes" would have broken
  mid-playback scrubbing on a real `<video>` element — Azure's own 5-minute `CLOCK_SKEW`
  back-dating eats most of a shorter window before it even starts.
- **Frontend**: `@azure/msal-browser`/`@azure/msal-react`, a new top-level `web/src/auth/`
  (config + token acquisition — deliberately outside `features/`/`components/`/`routes/` so it can
  legally import `src/api/*` under the ESLint seam), `web/src/adapters/auth-adapter.ts` as the
  UI's one legal door to it, `SignInGate`/`AccountMenu` in `features/auth/`. `client.ts` attaches
  the bearer via `openapi-fetch` middleware; `events-source.ts` uses
  `withCredentials: true` for the cookie; the one raw-`fetch` bypass (`endpoints.ts`'s
  `getSegmentScene`) got its own explicit credentials. Both `<video>` elements
  (`VideoPlayer.tsx`, `SegmentInspector.tsx`) gained `crossOrigin="use-credentials"` — without it
  the cookie is not sent cross-origin and the clip 401s. `seen-store.ts`'s persist key is now
  namespaced per account (`s-bites-milestones:${accountId}`), retiring the "no auth/user model in
  this backend at all yet" comment T38 exists to close.

### One real bug found and fixed during the build itself, not by review or live testing
`POST /jobs/{id}/resume` takes **no request body**. The session cookie has to be `SameSite=None`
(the deployed frontend and API are different origins), so the browser attaches it to cross-site
requests too — and a bodyless POST has no CORS preflight to stop a plain cross-site HTML form from
triggering it with a victim's cookie, re-running their job on their own credit. Fixed (D187) by
requiring the bearer header specifically on every state-changing route
(`mutating_principal`/`MutatingPrincipal`) and refusing the cookie there, even though reads still
accept it. Pinned by `tests/test_api_session.py::test_state_changing_routes_refuse_the_cookie`.
`project-reviewer` independently re-verified this fix (it first mis-read a stale file and thought
the hole was still open, then re-checked against `git diff` and confirmed it is closed) — so this
one has real double coverage.

### Verified live this session (not just by pytest)
- All 12 real API routes (11 job-scoped + `/auth/me`) return 401 with no credentials, against a
  running `uvicorn` process.
- An `alg: none` forged token is rejected; the client sees only `"invalid token"`, the real reason
  goes to the server log (`api/auth.py`'s deliberate non-disclosure).
- Clicking "Sign in with Microsoft" in the real browser (Playwright) reaches an actual Microsoft
  login page, not an `AADSTS` error — validating client id, redirect URI, sign-in audience, PKCE,
  and the custom `api://<client-id>/Jobs.ReadWrite` scope end to end. **Completing an actual
  sign-in with real credentials was not done this session** — that is the one part of the DoD
  ("two different signed-in users each submit a job and can only ever see, list, or download their
  own") still to be exercised by a human. Structurally verified via fakes
  (`tests/test_api_ownership.py`); not yet watched happen for real.

### Azure app registration created this session (irreversible choice, made correctly)
- Name: **s-bites Studio**, App (client) ID `45c92561-f5ed-4785-8d82-3ab76be1465c`, object id
  `9adbb26e-d813-4b32-9972-2b1eee7fc806`, service principal
  `866c93a6-0ded-449d-9512-347a9bad873e`.
- `signInAudience=AzureADandPersonalMicrosoftAccount` — **this cannot be changed after creation**;
  if it is ever wrong, the fix is deleting and re-registering, not patching.
- SPA redirect URI: `http://localhost:5173` only. **T38B must add the deployed Static Web Apps
  origin as a second SPA redirect URI** — query parameters are not allowed in redirect URIs for
  this sign-in audience, so keep any deep-linking scheme in the SPA route, not the URI.
  `identifierUris: ["api://45c92561-f5ed-4785-8d82-3ab76be1465c"]`, one exposed scope
  (`Jobs.ReadWrite`, `requestedAccessTokenVersion: 2`), pre-authorized for its own app id so
  sign-in raises no separate admin-consent prompt.

## Environment state

- Branch `cloud`, checkpointed but **not yet pushed** — same open question T34/T35 also left, now
  with T38A added to what's sitting on it. Push offered, not yet executed as of this checkpoint.
- **Local `.env` now has `AUTH_ENV=entra`** (not `none`) with the four `ENTRA_*` keys pointing at
  the app registration above, `ENTRA_ALLOWED_TENANTS` empty (any Microsoft account may sign in).
  This is a real change from every prior session's local default — a fresh session's `cli.py`/test
  runs are unaffected (neither touches `api/auth.py` at all), but anyone starting the API by hand
  will hit real Entra sign-in, not the `dev.local` principal, unless `AUTH_ENV` is set back to
  `none`.
- **`web/.env.local` exists** (gitignored via `*.local`) with the matching `VITE_ENTRA_*` values.
  `web/.env.example` documents the shape for anyone re-creating it.
- **Two dev processes may still be running from this session's live verification**: `uvicorn
  api.main:app` on :8000 and `npm run dev` (Vite) on :5173, both started for the Playwright
  sign-in-page check. Check with `netstat -ano | grep ":8000\|:5173"` before assuming either is
  fresh; kill and restart rather than trusting a long-lived one, especially the API — this project
  already knows `--reload` is unusable on Windows, so any code edit needs a manual restart anyway.
- **The deployed cloud API is still wide open** — re-confirmed this session,
  `GET https://ca-sbites-api.politeforest-8877ab80.eastus.azurecontainerapps.io/jobs` returns real
  job data with no credentials. T38A does not touch the deployed image; that is T38B's job. If the
  live deployment isn't being actively used, tearing down `rg-sbites-cloud` stops both the exposure
  and the spend simultaneously — still nobody's call but the user's.
- `RUNTIME_ENV=azure`, `QUEUE_ENV=local`, `EVENTS_ENV=local`, `RUN_INPROC_WORKER=true`,
  `RENDER_ENV=local` — all unchanged from prior sessions, still the fast local-iteration defaults.

## Next: T38B — Static Web Apps deploy and the public link

Scope was split at planning time specifically so T38A (identity, ownership, local verification)
and T38B (getting a real frontend on a real URL) could each be a normal-sized session. Read
`decisionlog.md` D183-D187 before touching anything here — the tenancy-as-config design in
particular constrains how the deployed frontend's own `VITE_ENTRA_*` values get set.

**What T38B actually is, concretely:**
- Add an Azure Static Web Apps resource to `infra/main.bicep`. The file already has two explicit
  placeholder comments naming this task (`main.bicep:3-5` and the `WEB_ORIGINS` line) — read those
  before assuming the shape from scratch.
- Build `web/` for production (`npm run build`, already wired in `package.json`) and deploy it —
  either via the SWA GitHub Actions integration (none exists yet; no `.github/workflows/`
  directory in this repo) or `scripts/deploy_cloud.sh`, which currently has **no frontend step at
  all** and deliberately never copies `web/` into its build context.
- Once the SWA hostname is known: add it to `WEB_ORIGINS` in the deployed API's Container App env
  (`main.bicep`'s `WEB_ORIGINS` placeholder), and **add it as a second SPA redirect URI** on the
  `s-bites Studio` app registration created this session (`az ad app update`, not a new
  registration — query parameters still aren't allowed in the URI).
- Set the deployed frontend's build-time `VITE_ENTRA_*` values (`VITE_ENTRA_CLIENT_ID`,
  `VITE_ENTRA_AUTHORITY`, `VITE_ENTRA_SCOPE`) to match what T38A already put in `.env`/
  `web/.env.local` locally — same app registration, same tenant setting.
- **The container still runs as root** (no `USER` directive in `Dockerfile`) — `handoff.md` has
  flagged this since T35 as "the natural time to add it" once auth makes the deployment genuinely
  public-facing. T38B is that time; not fixing it is a decision to make explicitly, not by default.
- D141's `Copy Link` UI feature now shares a `/jobs/:jobId` URL that correctly 404s for anyone but
  the owner — worth deciding whether that UI still makes sense post-auth, or should become
  "request access" / a real multi-tenant share, before the frontend goes public.

**Not this task, and not implied by "the public link" either:** retuning
`RENDER_MAX_CONCURRENCY=1` against real multi-user concurrent load (still flagged since T35,
still unmeasured) — worth doing once the deployed frontend actually makes concurrent access
plausible, but it is a measurement task, not a deploy-mechanics one, and should not be squeezed in.

## Known gaps / open questions, unresolved this session

- **The DoD's live two-user check was not completed with real credentials** — see above. The next
  session (or the user, right now) should actually sign in as two different Microsoft accounts
  against the running local stack before trusting this fully, even though every mechanical piece
  is verified.
- Whether to merge `cloud` into `dev`, tear down `rg-sbites-cloud`, or leave both running into
  T38B — still open, still the user's call, unchanged from T34/T35's handoff.
- T18F, T18I: untouched again this session, exactly as left before.
