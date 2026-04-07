// Azure AI Foundry — Hub + Project (CognitiveServices architecture)
//
// The Hub is a CognitiveServices/accounts resource (kind: AIServices) that
// hosts the GPT-4.1 deployment directly. The Project is a child resource
// (CognitiveServices/accounts/projects) that provides the agent runtime.
//
// This architecture matches the live Azure infrastructure:
//   Hub: Microsoft.CognitiveServices/accounts (kind: AIServices)
//   Model: Microsoft.CognitiveServices/accounts/deployments (child of Hub)
//   Project: Microsoft.CognitiveServices/accounts/projects (child of Hub)

param hubName string
param projectName string
param location string
param managedIdentityId string
param managedIdentityPrincipalId string = ''
param deploymentName string = 'gpt-4.1'
param modelName string = 'gpt-4.1'
param modelVersion string = '2025-04-14'
param capacity int = 10
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

// ---- AI Foundry Hub (CognitiveServices AIServices) ------------

resource aiHub 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: hubName
  location: location
  kind: 'AIServices'
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: hubName
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// ---- GPT-4.1 deployment (native to Hub) -----------------------

resource gpt41Deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiHub
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

// ---- AI Foundry Project (CognitiveServices project) -----------

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2024-10-01' = {
  parent: aiHub
  name: projectName
  location: location
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
  }
}

// ---- Outputs --------------------------------------------------

// The connection string format expected by the Azure AI Projects SDK:
//   <endpoint>;<subscription>;<resource-group>;<project-name>
var subscriptionId = subscription().subscriptionId
var resourceGroupName = resourceGroup().name
var hubEndpoint = aiHub.properties.endpoint

output hubId string = aiHub.id
output hubEndpoint string = hubEndpoint
output projectId string = aiProject.id
output projectConnectionString string = '${hubEndpoint};${subscriptionId};${resourceGroupName};${projectName}'
output modelDeploymentName string = gpt41Deployment.name
output keyVaultId string = keyVault.id
output storageId string = storage.id

@description('Container Registry login server URL.')
output acrLoginServer string = containerRegistry.properties.loginServer

@description('Container Registry name.')
output acrName string = containerRegistry.name
