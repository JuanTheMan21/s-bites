#!/usr/bin/env bash
# T35: provisions infra/main.bicep, builds the image in ACR (no local Docker needed -- this
# machine's Docker Desktop was not running when this was written), then points both Container
# Apps at the real image. Idempotent: safe to re-run after any partial failure.
# T38B added step 5/6: builds and deploys web/ to the Static Web App infra/main.bicep now
# provisions, and updates the Entra app registration's SPA redirect URIs to include it.
#
# Requires: az CLI logged in, .env populated (this script sources it directly -- never echoes
# secret values), a resource group name to deploy into. The Static Web App's own location is
# hardcoded in infra/main.bicep ('eastus2') independent of this script's own $LOCATION argument --
# confirmed live that Microsoft.Web/staticSites isn't available in 'eastus', where the resource
# group and everything else actually lives; don't pass 'eastus2' as $2 here, that would try to
# move the resource group's own (immutable) location instead.
set -euo pipefail

# Found live, four attempts deep before landing on the actual fix: `az acr build`'s own
# log-streaming crashes the CLI process with a UnicodeEncodeError -- specifically on pip's own
# resolver output for this project's `requirements.txt` (`Collecting langgraph...`, then whatever
# non-ASCII character pip's new resolver prints next), unrelated to whether the remote build
# itself is succeeding. In order, confirmed NOT the fix, each crashing at the identical byte
# offset regardless: `PYTHONIOENCODING=utf-8`; `PYTHONUTF8=1` (Python's own more forceful UTF-8
# mode); `--no-format` on the build call (only changes build LOG formatting, not this); az's own
# `AZURE_CORE_NO_COLOR=true` switch (disables color, but the crashing write path runs regardless
# of color being on). All four are variations on "make the write UTF-8-safe" and none of them are
# -- this is a known, longstanding class of Azure CLI issue writing to a Windows console (the
# tool's own error message links straight to github.com/Azure/azure-cli/issues over it).
# The two exports below are kept anyway (harmless, correct practice generally) but the actual fix
# is `--no-logs` on the build call: it still QUEUES the build and BLOCKS until it finishes
# (confirmed against `az acr build`'s own docs -- this is "don't stream/print the log", not
# "don't wait"), it just never prints the log content that was crashing the process to try to
# print. A failed build still surfaces as a real nonzero exit here; only the crash from trying to
# DISPLAY output found a bug in.
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

RESOURCE_GROUP="${1:?usage: deploy_cloud.sh <resource-group> [location]}"
LOCATION="${2:-eastus}"
DEPLOYMENT_NAME="sbites-t35-$(date +%s)"
PARAMS_FILE="$(mktemp)"
# T38B, found live: on this machine's Git-Bash/MSYS environment, `mktemp` creates the file under
# MSYS's own real temp mapping, but a native (non-MSYS) python.exe given that same POSIX-style
# path string resolves a leading `/` as "root of the current drive" instead -- a completely
# different location, one that happens to already exist (`C:\tmp`) on this machine, so the write
# silently "succeeds" into a file bash never reads, leaving the real PARAMS_FILE empty. `az` has
# the identical problem reading `--parameters "@<posix-path>"` back. `cygpath -w` is what makes
# both sides agree on one real path; used for every absolute temp-file path this script hands to
# a native executable, not just this one.
PARAMS_FILE_WIN="$(cygpath -w "$PARAMS_FILE")"
trap 'rm -f "$PARAMS_FILE"' EXIT

# T38B, found live the hard way: a Bicep deployment with no `containerImage` override resets BOTH
# Container Apps to `main.bicep`'s own placeholder default -- including on a re-run whose only
# actual purpose was something unrelated (adding an env var, say). That placeholder has no
# `uvicorn` at all, so both apps immediately crash-loop (`exec: "uvicorn": executable file not
# found`) until something re-points them at the real image again. The ORIGINAL three-step shape
# below (Bicep-with-placeholder, build, point-at-real-image) is safe for a first deploy; it is NOT
# safe for any *partial* re-run that only touches Bicep, and there is no way to guarantee this
# script is always run start-to-finish rather than adapted by hand later. So: if a real image
# already exists in this resource group's ACR, use it as the deployment's own `containerImage`
# parameter, rather than leaving that to Bicep's placeholder default. A genuinely first-time
# deploy (no ACR yet) still falls through to the placeholder correctly.
EXISTING_ACR="$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || true)"
EXISTING_IMAGE=""
if [ -n "$EXISTING_ACR" ]; then
  # Found by review: `az acr repository show-tags ... | -o tsv` exits 0 as soon as the
  # repository exists, even if the `[?@=='latest']` filter matches nothing -- an empty JMESPath
  # result is not a CLI error. Checking the exit code alone (as an earlier version of this did)
  # cannot tell "repo exists, latest tag present" from "repo exists, latest tag absent", which is
  # exactly the partial-failure state (a repo created but never finished pushing `latest`) this
  # guard exists to detect. Capture the actual output and test for content instead.
  LATEST_TAG="$(az acr repository show-tags --name "$EXISTING_ACR" --repository s-bites --query "[?@=='latest']" -o tsv 2>/dev/null || true)"
  if [ -n "$LATEST_TAG" ]; then
    EXISTING_IMAGE="$(az acr show --name "$EXISTING_ACR" --query loginServer -o tsv)/s-bites:latest"
    echo "found an existing built image ($EXISTING_IMAGE) -- using it instead of the placeholder default"
  fi
fi

# Found live, the hard way: `set -a; source .env` breaks on every value in this file containing a
# literal `;` (the Storage and Service Bus connection strings both do) -- bash's own parser treats
# each `;`-separated segment as a new command, silently truncating the variable at the FIRST
# semicolon with no error at all. python-dotenv (already a project dependency, config.py's own
# parser) handles this correctly; building the whole parameters file in Python sidesteps bash
# variable-substitution/quoting fragility entirely rather than patching it piecemeal.
EXISTING_IMAGE="$EXISTING_IMAGE" python -c "
import json
import os
from dotenv import dotenv_values

env = dotenv_values('.env')
params = {
    '\$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#',
    'contentVersion': '1.0.0.0',
    'parameters': {
        'azureOpenAiEndpoint': {'value': env['AZURE_OPENAI_ENDPOINT']},
        'azureOpenAiApiKey': {'value': env['AZURE_OPENAI_API_KEY']},
        'azureOpenAiDeployment': {'value': env['AZURE_OPENAI_DEPLOYMENT']},
        'azureOpenAiApiVersion': {'value': env['AZURE_OPENAI_API_VERSION']},
        'azureSpeechKey': {'value': env['AZURE_SPEECH_KEY']},
        'azureSpeechRegion': {'value': env['AZURE_SPEECH_REGION']},
        'azureSpeechVoice': {'value': env['AZURE_SPEECH_VOICE']},
        'azureStorageConnectionString': {'value': env['AZURE_STORAGE_CONNECTION_STRING']},
        'azureStorageContainer': {'value': env['AZURE_STORAGE_CONTAINER']},
        'azureSkillsContainer': {'value': env['AZURE_SKILLS_CONTAINER']},
        'azureServiceBusConnectionString': {'value': env['AZURE_SERVICE_BUS_CONNECTION_STRING']},
        'azureServiceBusQueue': {'value': env['AZURE_SERVICE_BUS_QUEUE']},
        'azureServiceBusTopic': {'value': env['AZURE_SERVICE_BUS_TOPIC']},
        'azureServiceBusSubscription': {'value': env['AZURE_SERVICE_BUS_SUBSCRIPTION']},
        'frameBudget': {'value': int(env['FRAME_BUDGET'])},
        'fps': {'value': int(env['FPS'])},
        # T38B: found live, the hard way -- omitting these from the first deploy left the real
        # Container App running AUTH_ENV=none (main.bicep's own default), meaning the whole T38A
        # auth chain was fully built but silently inactive: GET /jobs returned real job data with
        # no credentials. Always pass the real values, never rely on the template's defaults.
        'authEnv': {'value': env.get('AUTH_ENV', 'none')},
        'entraTenantId': {'value': env.get('ENTRA_TENANT_ID', 'common')},
        'entraClientId': {'value': env.get('ENTRA_CLIENT_ID', '')},
        'entraAllowedTenants': {'value': env.get('ENTRA_ALLOWED_TENANTS', '')},
        'entraRequiredScope': {'value': env.get('ENTRA_REQUIRED_SCOPE', 'Jobs.ReadWrite')},
        'entraRequiredAppRole': {'value': env.get('ENTRA_REQUIRED_APP_ROLE', '')},
    },
}
if os.environ.get('EXISTING_IMAGE'):
    params['parameters']['containerImage'] = {'value': os.environ['EXISTING_IMAGE']}
with open(r'$PARAMS_FILE_WIN', 'w', encoding='utf-8') as f:
    json.dump(params, f, indent=2)
"

echo "== 1/6: resource group =="
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" -o none

# Found by review, not live (this session never hit it, since it only ever deployed once): the
# Key Vault name is deterministic (`kv-sbites-${take(uniqueString(resourceGroup().id), 6)}` in
# main.bicep), so recovering from a partial failure by deleting and recreating the SAME resource
# group -- a completely normal recovery step -- computes the identical vault name again. Key
# Vault's soft-delete cannot be disabled, so that name is still reserved tenant-wide until purged,
# and the redeploy would fail on it with no obvious link back to "the RG was deleted." Purging any
# soft-deleted vault under this project's own naming prefix before every deploy is what actually
# makes "safe to re-run after a partial failure" true; harmless no-op when nothing matches.
for deleted in $(az keyvault list-deleted --query "[?starts_with(name, 'kv-sbites-')].name" -o tsv 2>/dev/null || true); do
  echo "purging soft-deleted Key Vault from a previous attempt: $deleted"
  az keyvault purge --name "$deleted" --location "$LOCATION" -o none 2>&1 || true
done

echo "== 2/6: Bicep (placeholder image on first run) =="
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/main.bicep \
  --parameters "@$PARAMS_FILE_WIN" \
  --name "$DEPLOYMENT_NAME" \
  -o none

ACR_NAME="$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.acrName.value -o tsv)"
ACR_LOGIN_SERVER="$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.acrLoginServer.value -o tsv)"

echo "== 3/6: build image in ACR ($ACR_NAME) -- no local Docker needed =="
# `az acr build .` against the full repo tree hung indefinitely on this project's own accumulated
# artifacts/ (30k+ files from past dev renders) -- found live, not assumed: az acr build's local
# tar-packing step walks the whole tree before .dockerignore ever gets a chance to prune it, and
# a 30k-entry directory makes that walk pathological. Staging a clean, minimal context with only
# what the Dockerfile actually COPYs is what avoids the walk entirely, not a workaround for
# anything the Dockerfile itself needs.
BUILD_CONTEXT="$(mktemp -d)"
trap 'rm -f "$PARAMS_FILE"; rm -rf "$BUILD_CONTEXT"' EXIT
cp Dockerfile package.json package-lock.json requirements.txt cli.py config.py config_events.py \
  config_queue.py config_render.py worker.py "$BUILD_CONTEXT/"
# Every top-level package api/main.py's own import graph actually reaches -- confirmed by
# grepping every `from X.` / `import X` in the app code, not guessed. scorm/ (api/scorm.py's
# SCORM export) was missed on the first pass here and only found live, as a real 504 from the
# deployed container's own crash log (ModuleNotFoundError: No module named 'scorm').
for d in api adapters core interfaces mux rendering runtime_skills scorm; do
  cp -r "$d" "$BUILD_CONTEXT/$d"
  find "$BUILD_CONTEXT/$d" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
done
az acr build --registry "$ACR_NAME" --image s-bites:latest --no-logs "$BUILD_CONTEXT" -o none

echo "== 4/6: point both Container Apps at the real image =="
# --revision-suffix forces a genuinely new revision -- found live: passing the same image string
# ("...:latest") twice in a row silently no-ops (Container Apps dedupes on the literal string, not
# the tag's actual digest), so a rebuilt image under the same tag never actually rolls out without
# this.
REVISION_SUFFIX="rev$(date +%s)"
az containerapp update --name ca-sbites-api --resource-group "$RESOURCE_GROUP" \
  --image "$ACR_LOGIN_SERVER/s-bites:latest" --revision-suffix "$REVISION_SUFFIX" -o none
az containerapp update --name ca-sbites-worker --resource-group "$RESOURCE_GROUP" \
  --image "$ACR_LOGIN_SERVER/s-bites:latest" --revision-suffix "$REVISION_SUFFIX" -o none

API_FQDN="$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.apiFqdn.value -o tsv)"
echo "Done. API: https://$API_FQDN"

echo "== 5/6: build and deploy the frontend to Static Web Apps =="
SWA_NAME="$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.staticWebAppName.value -o tsv)"
SWA_URL="$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.staticWebAppUrl.value -o tsv)"

# A dotenv file, not shell-exported VITE_* vars -- D180 already burned this project once on bash's
# own handling of values sourced from .env (the semicolon-truncation bug); writing a file through
# Vite's own documented `.env.production.local` mechanism is unambiguous where relying on shell
# env passthrough into `vite build` is not. Reuses the SAME .env values T38A already populated
# (ENTRA_CLIENT_ID/ENTRA_TENANT_ID/ENTRA_REQUIRED_SCOPE) rather than requiring a second,
# separately-maintained copy for the frontend -- one app registration, config selects tenancy,
# applied to how this script itself is built.
API_FQDN="$API_FQDN" python -c "
import os
from dotenv import dotenv_values

env = dotenv_values('.env')
with open('web/.env.production.local', 'w', encoding='utf-8') as f:
    f.write(f\"VITE_API_BASE=https://{os.environ['API_FQDN']}\n\")
    f.write(f\"VITE_ENTRA_CLIENT_ID={env['ENTRA_CLIENT_ID']}\n\")
    f.write(f\"VITE_ENTRA_AUTHORITY=https://login.microsoftonline.com/{env['ENTRA_TENANT_ID']}\n\")
    f.write(f\"VITE_ENTRA_SCOPE={env['ENTRA_REQUIRED_SCOPE']}\n\")
"
( cd web && npm ci && npm run build )
rm -f web/.env.production.local  # never committed (*.local is already gitignored); just tidies the working tree

SWA_TOKEN="$(az staticwebapp secrets list --name "$SWA_NAME" --resource-group "$RESOURCE_GROUP" --query "properties.apiKey" -o tsv)"
npx -y @azure/static-web-apps-cli@latest deploy web/dist --deployment-token "$SWA_TOKEN" --env production

echo "== 6/7: add the deployed frontend as a second SPA redirect URI =="
# `PATCH applications/{id}` on `spa.redirectUris` REPLACES the whole array rather than appending
# -- confirmed against Graph's own documented behaviour, not assumed. Read the app's current URIs
# first and union in the new one, so a re-run of this script (or an app registration that already
# has other redirect URIs for some other reason) never silently drops one that was already there.
ENTRA_CLIENT_ID="$(python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['ENTRA_CLIENT_ID'])")"
APP_OBJECT_ID="$(az ad app show --id "$ENTRA_CLIENT_ID" --query id -o tsv)"
# Read via os.environ, not embedded into the Python source as a string -- D180's own lesson
# (bash variable interpolation into an inline script is quoting fragility waiting to bite; env
# vars sidestep it entirely) applies here just as much as it did to .env values.
EXISTING_URIS_JSON="$(az ad app show --id "$ENTRA_CLIENT_ID" --query "spa.redirectUris" -o json)"
PATCH_BODY="$(EXISTING_URIS_JSON="$EXISTING_URIS_JSON" SWA_URL="$SWA_URL" python -c "
import json, os

# Found by review: Graph returns the literal JSON `null` here, not `[]`, for an app registration
# that has never had a SPA platform/redirect URI configured at all -- a real state for a genuinely
# fresh registration, just not this session's own (which already has localhost:5173 from local
# dev). `json.loads('null')` is `None`, and `url not in None` raises TypeError, aborting this
# script under `set -e` *after* step 5 already deployed the frontend -- leaving the new origin
# never added as a redirect URI, with no obvious link back to why sign-in then fails.
existing = json.loads(os.environ['EXISTING_URIS_JSON']) or []
url = os.environ['SWA_URL']
if url not in existing:
    existing.append(url)
print(json.dumps({'spa': {'redirectUris': existing}}))
")"
az rest --method PATCH \
  --url "https://graph.microsoft.com/v1.0/applications/$APP_OBJECT_ID" \
  --headers "Content-Type=application/json" \
  --body "$PATCH_BODY" \
  -o none

echo "== 7/7: CORS on the artifact storage account (T18M item 4 -- in-browser video playback) =="
# `VideoPlayer.tsx`'s `crossOrigin="use-credentials"` (T38A, needed to carry the session cookie on
# a <video> element, which has no way to set a header) requires the WHOLE redirect chain --
# including the Blob Storage SAS URL `/jobs/{id}/video` 307s to -- to answer with CORS headers,
# not just the API. Confirmed live before this fix: `az storage cors list` on this account
# returned `[]`, zero rules; downloads worked (a plain `<a download>` isn't subject to the same
# browser check) while playback silently failed, exactly the reported symptom.
#
# The storage account (`sbitesartifacts25817`) is deliberately NOT managed by infra/main.bicep --
# see that file's own header for why -- so this rule lives here instead, as an idempotent step
# that survives a full infra redeploy. `cors clear` + `cors add` (rather than `cors add` alone) is
# what makes a re-run of this script idempotent: `add` on its own would accumulate a duplicate
# rule on every re-run, since Storage has no "add if not present" primitive. Idempotent in
# END STATE, not atomic: if `add` fails for a transient reason right after `clear` succeeds, this
# account is left with zero CORS rules (the exact bug this step fixes) until the script is rerun
# -- caught by review, accepted as a narrow-window risk on a manually-run script, matching this
# same file's existing tolerance elsewhere (the Key Vault purge step above has the same shape).
#
# `--exposed-headers Content-Range/Accept-Ranges` isn't load-bearing for how a plain `<video src>`
# element seeks today (that's the browser's own media engine reading raw 206/Content-Range off the
# wire, not gated by CORS at all) -- it only matters if this response is ever read from JS
# (fetch/XHR/MSE) instead. Included now since it's free and future-proofs that path; if range-
# seeking ever breaks, look at Accept-Ranges support in api/byte_range.py, not this line.
#
# Read via a python one-liner into a bash variable, not `source .env` -- D180's own lesson (the
# connection string contains literal `;`, which bash's own `source`/`set -a` truncates at) applies
# here exactly as it does everywhere else in this script; a plain command-substitution capture of
# stdout is not subject to that parsing at all.
STORAGE_CONNECTION_STRING="$(python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['AZURE_STORAGE_CONNECTION_STRING'])")"
az storage cors clear --services b --connection-string "$STORAGE_CONNECTION_STRING" -o none
az storage cors add \
  --services b \
  --methods GET HEAD OPTIONS \
  --origins "$SWA_URL" "http://localhost:5173" \
  --allowed-headers "*" \
  --exposed-headers "Content-Range" "Accept-Ranges" \
  --max-age 3600 \
  --connection-string "$STORAGE_CONNECTION_STRING" \
  -o none

echo "Done. Frontend: $SWA_URL"

# Governance gap this project has flagged since the trial began (CLAUDE.md's own Environment
# section: "No budget alerts are configured -- spend is checked manually"). Subscription-scope
# (infra/budget.bicep's own targetScope), so a separate deployment from the resource-group-scope
# template above -- the `az consumption budget create` CLI command has no notification/threshold
# support at all, only the Bicep resource does.
BUDGET_ALERT_EMAIL="${3:?usage: deploy_cloud.sh <resource-group> <location> <alert-email>}"
# Found by review: Consumption budgets reject any update that changes `timePeriod.startDate`, and
# budget.bicep derives that date from `utcNow()` -- a re-run in a later calendar month than the
# original deploy would submit a different startDate for the same budget name and fail. Checking
# for an existing budget first (rather than letting that failure happen and get swallowed) is what
# makes a later re-run actually a no-op instead of a silent, easy-to-miss skip.
if az consumption budget show --budget-name sbites-cloud-monthly >/dev/null 2>&1; then
  echo "budget sbites-cloud-monthly already exists -- leaving it (startDate is immutable once set)"
else
  az deployment sub create \
    --location "$LOCATION" \
    --template-file infra/budget.bicep \
    --parameters alertEmail="$BUDGET_ALERT_EMAIL" \
    -o none
fi
