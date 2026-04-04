// Azure OpenAI account with GPT-4.1 deployment

param name string
param location string
param deploymentName string = 'gpt-4.1'
param modelName string = 'gpt-4.1'
param modelVersion string = '2025-04-14'
param capacity int = 10
param managedIdentityId string
param tags object = {}

// ---- Cognitive Services account (OpenAI kind) -----------------

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  kind: 'OpenAI'
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
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// ---- GPT-4.1 deployment --------------------------------------

resource gpt41Deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
  name: deploymentName
  sku: {
    name: 'Standard'
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

// ---- Outputs --------------------------------------------------

output resourceId string = openAiAccount.id
output endpoint string = openAiAccount.properties.endpoint
output deploymentName string = gpt41Deployment.name
