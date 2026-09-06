# Handoff — current state

**Overwritten completely at every `/checkpoint`.** This file describes *now*, never history.
History lives in `decisionlog.md`. **Written to be self-contained for a fresh session with zero
memory of how this state was reached.**

## What just happened

**T35 shipped and is checkpointed on branch `cloud`** (not yet merged into `dev` — see "Before the
next session" below). Iteration 5.5 is now fully built except T38. Full reasoning for every
non-obvious choice: `decisionlog.md` D178-D182.

**A real cloud deployment exists right now and is live**, not a diagram: resource group
`rg-sbites-cloud` in `eastus`, Container Apps environment `cae-sbites-cloud`, two running
Container Apps (`ca-sbites-api`, public FQDN
`https://ca-sbites-api.politeforest-8877ab80.eastus.azurecontainerapps.io`; `ca-sbites-worker`,
scales 0→3 on Service Bus queue depth), ACR `sbitescloudgixkvw`, Key Vault `kv-sbites-gixkvw`. A
real job (`how a hash table works`) was submitted through the public API, processed entirely by
the worker (scaled up from zero), and completed in ~5 minutes with a real video — confirmed by the
artifact endpoint's real 307 redirect to a live Blob SAS URL. **This deployment costs real money
while it exists** — the API's `minReplicas: 1` means it never scales to zero.

### What shipped
- **Fixed the Linux portability bug** T34 flagged: `adapters/local/hyperframes_process.py::
  _kill_tree` now branches on `sys.platform` — Windows unchanged, POSIX kills the whole process
  group via `os.killpg`, which only works because `run()` now isolates the child into its own
  group first (`start_new_session=True`). **This exact coupling is the one thing to never
  "simplify" without re-reading `decisionlog.md` D182** — dropping that kwarg would make a stalled
  render's timeout kill the container's own process, not just the orphan.
- `Dockerfile`, `.dockerignore` — one image, both roles (`api`/`worker`) selected by each Container
  App's own `command`, not baked in.
- `infra/main.bicep` (resource-group scope) + `infra/budget.bicep` (subscription scope, separate
  because the scopes can't mix in one template) — see the file headers for what each resource is
  and why. **`ContainerAppsRenderBackend` stays a stub permanently** (D173, T34's decision) —
  `RENDER_ENV=local` in both Container Apps' env resolves the real
  `PlaywrightHyperFramesRenderBackend`, which is genuinely local *to that container*.
- `scripts/deploy_cloud.sh` — the repeatable version of everything done by hand this session.
  Re-run it (same resource group name) to redeploy; it's now actually idempotent against the two
  real re-run gaps `project-reviewer` found (a Key Vault soft-delete collision, the budget's
  immutable start date) — see D181.

### Six real bugs found live during this session's own deployment, all fixed
In rough order hit, full reasoning in `decisionlog.md` D178-D182:
1. A wrong `AcrPull` role-definition GUID, recalled from memory instead of looked up — caught
   immediately by the first deployment attempt.
2. The Container Apps environment silently caps every container at 2 vCPU/4GiB unless
   `workloadProfiles` is explicitly declared. **Real trap:** an environment created without one
   can't have it added after the fact — had to delete and recreate the whole environment.
3. `az acr build`'s local tar-packing hung indefinitely walking this project's own 34,000+-file
   `artifacts/` directory before `.dockerignore` ever got a chance to prune it. Fixed by staging a
   minimal build context (just what the Dockerfile actually `COPY`s) instead of pointing at the
   repo root.
4. HyperFrames' Chrome Headless Shell install needs `unzip`, which `python:3.11-slim` doesn't ship.
5. The staged build context missed the top-level `scorm/` package (`api/scorm.py`'s own import) —
   found as a real `ModuleNotFoundError` crash in the deployed container's logs.
6. **The most subtle one:** bash `source .env` silently truncates any value containing a literal
   `;` at the first one — both the Storage and Service Bus connection strings are exactly that
   shape, so both arrived at Key Vault as ~30-character garbage with no error anywhere until a real
   container crashed with `ValueError: Connection string missing required connection details`.
   Fixed by building the deployment parameters via `python-dotenv` instead of bash `source`.
7. `az containerapp update --image <tag>` silently no-ops when the image *string* is unchanged,
   even though the tag now points at a genuinely different, rebuilt image — Container Apps dedupes
   on the string, not the resolved digest. Fixed with `--revision-suffix` on every update.

**One more thing worth knowing if you ever run `az acr build` yourself on this machine:** its own
log-streaming crashes the CLI with a `UnicodeEncodeError` (Windows console codepage vs. some
dependency's install output) — cosmetic, not a real build failure; `export PYTHONIOENCODING=utf-8`
prevents it, and either way, always confirm the real build status via
`az acr task list-runs --registry <name>` rather than trusting the crashed CLI's own exit code.

## Environment state

- Branch `cloud`, not yet merged into `dev` or pushed — same open question as after T34, now with
  T35 added to what's sitting on it.
- **Real Azure resources now exist and cost money while running:** `rg-sbites-cloud` (the whole
  T35 deployment) plus everything from T34 (`sbites-servicebus` namespace in
  `resource-skill-bites`). Nothing has been torn down. If a future session doesn't need the live
  deployment anymore, tearing down `rg-sbites-cloud` (`az group delete`) is the way to stop paying
  for it — nothing else in the project depends on it existing continuously.
- Local `.env`/dev loop is completely unaffected by any of this — `QUEUE_ENV=local`,
  `EVENTS_ENV=local`, `RUN_INPROC_WORKER=true`, `RENDER_ENV=local` are all still the fast
  local-iteration defaults from T34's own checkpoint, untouched this session.
- No local processes were started for T35 — everything this session touched was cloud-only
  (`az` CLI calls), so there's nothing to check for stray local servers this time.

## Gotchas carried forward, still true

- Everything in T34's own handoff about the model-switch discipline, the quality hook's stripped-
  import pitfall, and "an SDK's documented behavior is a claim, not a fact" — all still true, all
  hit again in some form this session (the wrong role GUID, the workload-profile requirement, and
  the `source .env` bug are all instances of "verify against the real thing, not memory/docs").
- **`az deployment group create`/`az acr build`/`az containerapp update` are all genuinely
  idempotent and safe to re-run *once the fixes above are in place*** — but a partial failure
  midway through a hand-run sequence (not via the script) can still leave things in a state the
  script's own recovery logic doesn't anticipate (e.g., a container app created with the
  placeholder image, mid-way through manually re-running steps out of order). Prefer
  `scripts/deploy_cloud.sh` end to end over hand-running individual `az` commands, now that it
  exists.
- **Never run `uvicorn --reload` on Windows** — unrelated to this session, still true, still
  documented in `api/main.py`.

## Known gaps / open questions, unresolved this session

- **The deployed image runs as root** (no `USER` directive in the `Dockerfile`) — acceptable for a
  POC/trial, not for anything long-lived. A hardening pass before T38 makes this public-facing
  (real user auth) would be the natural time to add it.
- **`RENDER_MAX_CONCURRENCY=1`** in the container env vars is a conservative starting number, not
  tuned against real sustained load — the one real job run this session doesn't tell you much
  about concurrent-job behavior. Worth measuring before T38's frontend makes this reachable by
  more than one person testing by hand.
- **The budget's $50/month amount and its single alert email are placeholders** — `infra/
  budget.bicep`'s own parameters, easy to adjust, just not tuned against any real usage data yet.
- **Static Web Apps was deliberately moved out of T35 into T38** (nothing in T35 needed a deployed
  frontend) — T38's own planning session should read this file plus `decisionlog.md` D178-D182
  before assuming anything about how the backend is reachable.
- T18F, T18I: still exactly as T34's handoff left them, untouched this session.
- Whether to merge `cloud` into `dev` now, tear down `rg-sbites-cloud` between sessions to stop
  paying for it, or leave both running into T38 — all open questions for the user, not decided
  here.
