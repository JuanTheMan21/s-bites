// T35 — resource-group-scope IaC for the cloud-deployed worker/API split.
// T38B added the Static Web App resource below. Entra app registrations still aren't here --
// `az ad app` isn't a Bicep-managed resource type, so that stays in scripts/deploy_cloud.sh
// (T38A already created the registration by hand; T38B's own new redirect URI is a script step).
//
// Deliberately NOT here: a subscription budget (a short `az consumption budget create`
// step in scripts/deploy_cloud.sh instead -- that's a subscription-scope resource, a separate
// `targetScope` from everything below, and not worth the split for one resource).
//
// Existing resources (Azure OpenAI, Speech, Storage, Service Bus, all in `resource-skill-bites`)
// are referenced by VALUE (their keys/connection strings, passed in as secure parameters) rather
// than declared here as `existing` -- this template never touches them, so there is nothing for
// Bicep to manage or risk drifting.
//
// `containerImage` defaults to a public placeholder because the real image cannot exist in an
// ACR that this same deployment is creating. First deploy uses the placeholder; the deploy
// script then runs `az acr build` and `az containerapp update --image ...` for both apps.

@description('Azure OpenAI endpoint URL')
@secure()
param azureOpenAiEndpoint string

@description('Azure OpenAI API key')
@secure()
param azureOpenAiApiKey string

param azureOpenAiDeployment string
param azureOpenAiApiVersion string

@description('Azure AI Speech key')
@secure()
param azureSpeechKey string

param azureSpeechRegion string
param azureSpeechVoice string

@description('Azure Blob Storage connection string')
@secure()
param azureStorageConnectionString string

param azureStorageContainer string
param azureSkillsContainer string

@description('Service Bus namespace connection string')
@secure()
param azureServiceBusConnectionString string

param azureServiceBusQueue string = 'video-jobs'
param azureServiceBusTopic string = 'job-events'
param azureServiceBusSubscription string = 'api'

param frameBudget int = 9500
param fps int = 24

// T38B: identity. `authEnv` defaults to 'none' so this template still deploys a working (if
// unauthenticated) stack if these are left unset -- but this project's own deploy script always
// passes 'entra' plus the four values below, sourced from the same .env T38A populated. None of
// these are secret: a SPA client id and a tenant id are public by design (the app registration's
// own redirect-URI allowlist is what actually constrains use, not keeping the id private).
param authEnv string = 'none'
param entraTenantId string = 'common'
param entraClientId string = ''
param entraAllowedTenants string = ''
param entraRequiredScope string = 'Jobs.ReadWrite'
param entraRequiredAppRole string = ''

@description('Full image reference, e.g. myacr.azurecr.io/s-bites:latest. Placeholder until the real image is built and pushed.')
param containerImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

param location string = resourceGroup().location

var suffix = take(uniqueString(resourceGroup().id), 6)
var acrName = 'sbitescloud${suffix}'
var keyVaultName = 'kv-sbites-${suffix}'

// -- Well-known built-in role definition IDs (RBAC, not admin credentials/access policies) -----
var acrPullRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)
var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-sbites-cloud'
  location: location
}

resource acr 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false // pulled via the managed identity's AcrPull role, not admin credentials
  }
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, identity.id, acrPullRoleId)
  scope: acr
  properties: {
    roleDefinitionId: acrPullRoleId
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
  }
}

resource keyVaultSecretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identity.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleId
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// One secret per sensitive value the containers read via `_env()` today (config.py) -- names
// match what Container Apps' own `secrets` array below references by `keyVaultUrl`.
resource secretOpenAiKey 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = {
  parent: keyVault
  name: 'azure-openai-api-key'
  properties: { value: azureOpenAiApiKey }
}
resource secretSpeechKey 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = {
  parent: keyVault
  name: 'azure-speech-key'
  properties: { value: azureSpeechKey }
}
resource secretStorageConn 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = {
  parent: keyVault
  name: 'azure-storage-connection-string'
  properties: { value: azureStorageConnectionString }
}
resource secretServiceBusConn 'Microsoft.KeyVault/vaults/secrets@2024-11-01' = {
  parent: keyVault
  name: 'azure-service-bus-connection-string'
  properties: { value: azureServiceBusConnectionString }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: 'log-sbites-cloud'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: 'cae-sbites-cloud'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    // Explicit Workload profiles (v2) environment with the default Consumption profile --
    // found by a real deployment failure, not assumed: omitting this makes the environment fall
    // back to the legacy "Consumption-only (v1)" behaviour, which caps a single container at 2
    // vCPU / 4Gi regardless of what's requested. The architecture writeup's whole §V argument
    // (4 vCPU / 8GiB Consumption is not the bottleneck) only holds under the real v2 Consumption
    // profile, which is what this declares.
    workloadProfiles: [
      { name: 'Consumption', workloadProfileType: 'Consumption' }
    ]
  }
}

// Env vars every container needs, whether it's the api or the worker role -- both actually run
// GraphContext/the render backend (D173: the worker containerises the renderer, so RENDER_ENV
// stays 'local' here to resolve the real PlaywrightHyperFramesRenderBackend). QUEUE_ENV/
// EVENTS_ENV are deliberately left unset -- both resolve from RUNTIME_ENV=azure, exercising the
// real cross-process path T34 verified by hand, not the fast-local-iteration bridge.
var sharedEnv = [
  { name: 'RUNTIME_ENV', value: 'azure' }
  { name: 'RENDER_ENV', value: 'local' }
  { name: 'FRAME_BUDGET', value: string(frameBudget) }
  { name: 'FPS', value: string(fps) }
  { name: 'RENDER_MAX_CONCURRENCY', value: '1' } // conservative first number -- T35's own DoD is to measure and revisit
  { name: 'RENDER_WORKERS', value: 'auto' }
  { name: 'RENDER_QUALITY', value: 'standard' }
  { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAiEndpoint }
  { name: 'AZURE_OPENAI_DEPLOYMENT', value: azureOpenAiDeployment }
  { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAiApiVersion }
  { name: 'AZURE_SPEECH_REGION', value: azureSpeechRegion }
  { name: 'AZURE_SPEECH_VOICE', value: azureSpeechVoice }
  { name: 'AZURE_STORAGE_CONTAINER', value: azureStorageContainer }
  { name: 'AZURE_SKILLS_CONTAINER', value: azureSkillsContainer }
  { name: 'AZURE_SERVICE_BUS_QUEUE', value: azureServiceBusQueue }
  { name: 'AZURE_SERVICE_BUS_TOPIC', value: azureServiceBusTopic }
  { name: 'AZURE_SERVICE_BUS_SUBSCRIPTION', value: azureServiceBusSubscription }
  { name: 'AUTH_ENV', value: authEnv }
  { name: 'ENTRA_TENANT_ID', value: entraTenantId }
  { name: 'ENTRA_CLIENT_ID', value: entraClientId }
  { name: 'ENTRA_ALLOWED_TENANTS', value: entraAllowedTenants }
  { name: 'ENTRA_REQUIRED_SCOPE', value: entraRequiredScope }
  { name: 'ENTRA_REQUIRED_APP_ROLE', value: entraRequiredAppRole }
  { name: 'AZURE_OPENAI_API_KEY', secretRef: 'openai-key' }
  { name: 'AZURE_SPEECH_KEY', secretRef: 'speech-key' }
  { name: 'AZURE_STORAGE_CONNECTION_STRING', secretRef: 'storage-conn' }
  { name: 'AZURE_SERVICE_BUS_CONNECTION_STRING', secretRef: 'servicebus-conn' }
]

var sharedSecrets = [
  { name: 'openai-key', keyVaultUrl: secretOpenAiKey.properties.secretUri, identity: identity.id }
  { name: 'speech-key', keyVaultUrl: secretSpeechKey.properties.secretUri, identity: identity.id }
  {
    name: 'storage-conn'
    keyVaultUrl: secretStorageConn.properties.secretUri
    identity: identity.id
  }
  {
    name: 'servicebus-conn'
    keyVaultUrl: secretServiceBusConn.properties.secretUri
    identity: identity.id
  }
]

resource apiApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-sbites-api'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    environmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
      }
      registries: [{ server: acr.properties.loginServer, identity: identity.id }]
      secrets: sharedSecrets
    }
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          command: ['uvicorn', 'api.main:app', '--host', '0.0.0.0', '--port', '8000']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: union(sharedEnv, [
            { name: 'RUN_INPROC_WORKER', value: 'false' }
            // T38B: wired to the Static Web App resource's own output in this same deployment,
            // so there's no manual "come back and set this once you know the URL" step. Local
            // dev against a deployed backend stays possible alongside it.
            { name: 'WEB_ORIGINS', value: 'https://${staticSite.properties.defaultHostname},http://localhost:5173' }
          ])
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 1 } // must never scale to zero -- SSE depends on it
    }
  }
  dependsOn: [acrPullAssignment, keyVaultSecretsUserAssignment]
}

resource workerApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: 'ca-sbites-worker'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    environmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [{ server: acr.properties.loginServer, identity: identity.id }]
      secrets: union(sharedSecrets, [
        { name: 'servicebus-conn-scaler', keyVaultUrl: secretServiceBusConn.properties.secretUri, identity: identity.id }
      ])
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: containerImage
          command: ['python', 'worker.py']
          resources: { cpu: json('4.0'), memory: '8Gi' }
          env: sharedEnv
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3 // bounds spend and Azure OpenAI TPM pressure (architecture writeup §V)
        rules: [
          {
            name: 'servicebus-queue-length'
            custom: {
              type: 'azure-servicebus'
              metadata: { queueName: azureServiceBusQueue, messageCount: '1' }
              auth: [{ secretRef: 'servicebus-conn-scaler', triggerParameter: 'connection' }]
            }
          }
        ]
      }
    }
  }
  dependsOn: [acrPullAssignment, keyVaultSecretsUserAssignment]
}

// T38B: the deployed frontend. Free tier, no linked backend -- the SPA calls the Container Apps
// API cross-origin via its own build-time VITE_API_BASE (web/src/api/base-url.ts), so none of the
// Standard-tier "bring your own Functions API" integration applies here. No repositoryUrl/branch
// either: this project deploys via `scripts/deploy_cloud.sh` + the SWA CLI, not GitHub Actions
// (there's no .github/workflows/ and nothing else here has one).
//
// `location` is NOT the shared `location` param -- confirmed live against this subscription
// (`az provider show --namespace Microsoft.Web`) that Microsoft.Web/staticSites is only available
// in Central US, East US 2, West US 2, West Europe, and East Asia. eastus is not on that list,
// despite every other resource in this file living there. East US 2 is the same physical metro
// area (Virginia) as the rest of this deployment, and static content itself is served from a
// global CDN regardless of which region the resource is created in, so this is a region
// parameter, not an architecture decision -- a resource group's own location doesn't constrain
// where its children live.
resource staticSite 'Microsoft.Web/staticSites@2024-11-01' = {
  name: 'swa-sbites-${suffix}'
  location: 'eastus2'
  sku: { name: 'Free', tier: 'Free' }
  properties: {}
}

output acrLoginServer string = acr.properties.loginServer
output acrName string = acr.name
output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
output keyVaultName string = keyVault.name
output staticWebAppName string = staticSite.name
output staticWebAppUrl string = 'https://${staticSite.properties.defaultHostname}'
