// Azure AI Foundry — Hub + Project
//
// The Hub is the top-level Azure AI resource that groups projects together.
// The Project is where the agent is deployed and conversations are tracked.
// Both are represented as Microsoft.MachineLearningServices/workspaces,
// differentiated by the `kind` property ('Hub' vs 'Project').

param hubName string
param projectName string
param location string
param appInsightsId string
param openAiAccountId string
param openAiEndpoint string
param managedIdentityId string
param managedIdentityPrincipalId string = ''
param tags object = {}

// ---- Storage Account (required by AI Foundry Hub) -------------

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: toLower(replace('st${hubName}', '-', ''))
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// ---- Key Vault (required by AI Foundry Hub) -------------------

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  // Key Vault names: max 24 chars, alphanumeric + hyphens.
  // 'kv-' prefix = 3 chars, leaving 21 chars for the hub name suffix.
  // We take 18 chars to stay well within the 24-char global limit.
  name: 'kv-${take(hubName, 18)}'
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

// ---- Key Vault Reader role for managed identity ---------------
// AI Foundry project creation requires the identity to read the hub Key Vault.

var keyVaultReaderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '21090545-7ca7-4776-b22c-e363652d74d2' // Key Vault Reader
)

resource kvReaderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(managedIdentityPrincipalId)) {
  scope: keyVault
  name: guid(keyVault.id, managedIdentityPrincipalId, keyVaultReaderRoleId)
  properties: {
    roleDefinitionId: keyVaultReaderRoleId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---- Container Registry (optional but recommended for Hub) ----

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: toLower(replace('cr${hubName}', '-', ''))
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// ---- AI Foundry Hub -------------------------------------------

resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: hubName
  location: location
  kind: 'Hub'
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    friendlyName: hubName
    description: 'Agentic Ops Advisor — AI Foundry Hub'
    storageAccount: storage.id
    keyVault: keyVault.id
    applicationInsights: appInsightsId
    containerRegistry: containerRegistry.id
    primaryUserAssignedIdentity: managedIdentityId
  }
}

// ---- OpenAI connection on the Hub ----------------------------

resource openAiConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-10-01' = {
  parent: aiHub
  name: 'azure-openai'
  properties: {
    category: 'AzureOpenAI'
    target: openAiEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiVersion: '2025-01-01-preview'
      ApiType: 'azure'
      ResourceId: openAiAccountId
    }
  }
}

// ---- AI Foundry Project ---------------------------------------

resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: projectName
  location: location
  kind: 'Project'
  tags: tags
  dependsOn: [kvReaderAssignment]
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    friendlyName: projectName
    description: 'Agentic Ops Advisor — AI Foundry Project'
    hubResourceId: aiHub.id
    primaryUserAssignedIdentity: managedIdentityId
  }
}

// ---- Outputs --------------------------------------------------

// The connection string format expected by the Azure AI Projects SDK:
//   <endpoint>;<subscription>;<resource-group>;<project-name>
var subscriptionId = subscription().subscriptionId
var resourceGroupName = resourceGroup().name

output hubId string = aiHub.id
output projectId string = aiProject.id
output projectConnectionString string = '${aiHub.properties.discoveryUrl};${subscriptionId};${resourceGroupName};${projectName}'
output keyVaultId string = keyVault.id
output storageId string = storage.id

@description('Container Registry login server URL.')
output acrLoginServer string = containerRegistry.properties.loginServer

@description('Container Registry name.')
output acrName string = containerRegistry.name
