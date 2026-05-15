// =============================================================================
// Power Platform → Fabric telemetry lab — root deployment
// Scope: resourceGroup
//
// Architecture:
//   Function App (.NET 8, Flex Consumption) → Fabric Eventstream Custom Endpoint
//   Eventstream → Bronze Lakehouse + Eventhouse (KQL update policies → silver/gold)
//
// The Fabric Custom Endpoint connection string is stored in Key Vault
// and referenced by the Function App via a KV reference app setting.
// Fabric-side resources (Eventstream, Lakehouses, Eventhouse) are not
// Bicep-manageable and are provisioned via the Fabric REST API.
// =============================================================================
targetScope = 'resourceGroup'

@description('Short prefix used for all resource names. Lowercase letters/numbers, 3-8 chars.')
@minLength(3)
@maxLength(8)
param prefix string = 'pptel'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Object ID of the user/group to grant Key Vault Administrator + Storage Blob Data Owner for lab access.')
param adminPrincipalId string

@description('Tags applied to every resource.')
param tags object = {
  workload: 'powerplatform-telemetry-lab'
  env: 'lab'
  iac: 'bicep'
}

var suffix = uniqueString(resourceGroup().id)
var names = {
  law: 'law-${prefix}-${suffix}'
  ai: 'appi-${prefix}-${suffix}'
  storage: toLower('st${prefix}${suffix}')
  kv: 'kv-${prefix}-${suffix}'
  uami: 'id-${prefix}-${suffix}'
  func: 'func-${prefix}-${suffix}'
  funcPlan: 'plan-${prefix}-${suffix}'
}

// -----------------------------------------------------------------------------
// Identity
// -----------------------------------------------------------------------------
resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: names.uami
  location: location
  tags: tags
}

// -----------------------------------------------------------------------------
// Observability
// -----------------------------------------------------------------------------
resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: names.law
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 90
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
  }
}

resource ai 'Microsoft.Insights/components@2020-02-02' = {
  name: names.ai
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// -----------------------------------------------------------------------------
// Storage (Function App backing store)
// -----------------------------------------------------------------------------
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: names.storage
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    supportsHttpsTrafficOnly: true
    networkAcls: { defaultAction: 'Allow', bypass: 'AzureServices' }
  }
}

resource blobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

// -----------------------------------------------------------------------------
// Key Vault (RBAC)
// Stores the Fabric Eventstream Custom Endpoint connection string as secret
// 'fabric-eventstream-cs'. Set post-deployment via:
//   az keyvault secret set --vault-name <kv> --name fabric-eventstream-cs --value <cs>
// -----------------------------------------------------------------------------
resource kv 'Microsoft.KeyVault/vaults@2024-04-01-preview' = {
  name: names.kv
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

// -----------------------------------------------------------------------------
// Function App (Flex Consumption, .NET 8 isolated)
// Publishes PP telemetry events to Fabric Eventstream Custom Endpoint
// via EVENTHUB_CONNECTION_STRING (KV reference).
// -----------------------------------------------------------------------------
resource funcPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: names.funcPlan
  location: location
  tags: tags
  sku: { name: 'FC1', tier: 'FlexConsumption' }
  kind: 'functionapp,linux'
  properties: { reserved: true }
}

resource funcApp 'Microsoft.Web/sites@2024-04-01' = {
  name: names.func
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${uami.id}': {} }
  }
  properties: {
    serverFarmId: funcPlan.id
    httpsOnly: true
    keyVaultReferenceIdentity: uami.id
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storage.properties.primaryEndpoints.blob}deploy'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: uami.id
          }
        }
      }
      runtime: { name: 'dotnet-isolated', version: '8.0' }
      scaleAndConcurrency: { instanceMemoryMB: 2048, maximumInstanceCount: 40 }
    }
    siteConfig: {
      appSettings: [
        { name: 'AzureWebJobsStorage__accountName', value: storage.name }
        { name: 'AzureWebJobsStorage__credential', value: 'managedidentity' }
        { name: 'AzureWebJobsStorage__clientId', value: uami.properties.clientId }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: ai.properties.ConnectionString }
        {
          name: 'EVENTHUB_CONNECTION_STRING'
          value: '@Microsoft.KeyVault(SecretUri=${kv.properties.vaultUri}secrets/fabric-eventstream-cs/)'
        }
        { name: 'UAMI_CLIENT_ID', value: uami.properties.clientId }
      ]
    }
  }
}

// -----------------------------------------------------------------------------
// RBAC
// -----------------------------------------------------------------------------
var roles = {
  storageBlobDataOwner: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  keyVaultSecretsUser: '4633458b-17de-408a-b874-0445c86b69e6'
  keyVaultAdministrator: '00482a5a-887f-4fb3-b363-3b7fe8e74483'
}

resource adminKvAdmin 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, adminPrincipalId, roles.keyVaultAdministrator)
  properties: {
    principalId: adminPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultAdministrator)
    principalType: 'User'
  }
}

resource adminBlobOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, adminPrincipalId, roles.storageBlobDataOwner)
  properties: {
    principalId: adminPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataOwner)
    principalType: 'User'
  }
}

resource funcBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, uami.id, roles.storageBlobDataContributor)
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.storageBlobDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource funcKvSecrets 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: kv
  name: guid(kv.id, uami.id, roles.keyVaultSecretsUser)
  properties: {
    principalId: uami.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.keyVaultSecretsUser)
    principalType: 'ServicePrincipal'
  }
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------
output storageAccount string = storage.name
output functionAppName string = funcApp.name
output keyVaultName string = kv.name
output keyVaultUri string = kv.properties.vaultUri
output appInsightsName string = ai.name
output userAssignedIdentityClientId string = uami.properties.clientId
output userAssignedIdentityPrincipalId string = uami.properties.principalId
