#!/usr/bin/env bash
# T35: provisions infra/main.bicep, builds the image in ACR (no local Docker needed -- this
# machine's Docker Desktop was not running when this was written), then points both Container
# Apps at the real image. Idempotent: safe to re-run after any partial failure.
#
# Requires: az CLI logged in, .env populated (this script sources it directly -- never echoes
# secret values), a resource group name to deploy into.
set -euo pipefail

# Found live: `az acr build`'s own log-streaming crashes the CLI process (a UnicodeEncodeError
# against Windows' cp1252 console codepage, unrelated to whether the remote build itself is
# succeeding) the moment any dependency's install output contains a character cp1252 can't
# represent -- this project's own requirements.txt (langgraph et al) reliably triggers it. Forcing
# UTF-8 here is what prevents that crash rather than a workaround for anything wrong with the build.
export PYTHONIOENCODING=utf-8

RESOURCE_GROUP="${1:?usage: deploy_cloud.sh <resource-group> [location]}"
LOCATION="${2:-eastus}"
DEPLOYMENT_NAME="sbites-t35-$(date +%s)"
PARAMS_FILE="$(mktemp)"
trap 'rm -f "$PARAMS_FILE"' EXIT

# Found live, the hard way: `set -a; source .env` breaks on every value in this file containing a
# literal `;` (the Storage and Service Bus connection strings both do) -- bash's own parser treats
# each `;`-separated segment as a new command, silently truncating the variable at the FIRST
# semicolon with no error at all. python-dotenv (already a project dependency, config.py's own
# parser) handles this correctly; building the whole parameters file in Python sidesteps bash
# variable-substitution/quoting fragility entirely rather than patching it piecemeal.
python -c "
import json
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
    },
}
with open('$PARAMS_FILE', 'w', encoding='utf-8') as f:
    json.dump(params, f, indent=2)
"

echo "== 1/4: resource group =="
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

echo "== 2/4: Bicep (placeholder image on first run) =="
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/main.bicep \
  --parameters "@$PARAMS_FILE" \
  --name "$DEPLOYMENT_NAME" \
  -o none

ACR_NAME="$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.acrName.value -o tsv)"
ACR_LOGIN_SERVER="$(az deployment group show -g "$RESOURCE_GROUP" -n "$DEPLOYMENT_NAME" --query properties.outputs.acrLoginServer.value -o tsv)"

echo "== 3/4: build image in ACR ($ACR_NAME) -- no local Docker needed =="
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
az acr build --registry "$ACR_NAME" --image s-bites:latest "$BUILD_CONTEXT" -o none

echo "== 4/4: point both Container Apps at the real image =="
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
