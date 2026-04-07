// ============================================================
// Agentic Ops Advisor — Subscription-scoped Bicep template
// Deploys all Azure resources required to run the agent in
// Azure AI Foundry Agent Service (production).
//
// Deploy with:
//   az deployment sub create \
//     --location eastus \
//     --template-file infra/main.bicep \
//     --parameters @infra/parameters.json
// ============================================================

targetScope = 'subscription'

// ---- Parameters -----------------------------------------------

@description('Azure region for all resources.')
param location string = 'eastus'

@description('Name of the resource group to create.')
param resourceGroupName string = 'rg-agentic-ops-advisor'

@description('Short environment tag used as a name suffix (e.g. dev, prod).')
@maxLength(8)
param environmentName string = 'prod'

@description('Name prefix applied to every resource.')
@maxLength(16)
param projectName string = 'agentops'

@description('Azure SQL Database name.')
param sqlDatabaseName string = 'agentops-telemetry'

@description('Azure SQL Database SKU.')
param sqlDatabaseSku string = 'Basic'

@description('Override location for Azure SQL (use when primary region has capacity constraints).')
param sqlLocation string = location

@description('Enable Azure SQL deployment. Set to false when MCAPS policy blocks SQL or for SQLite-only demos.')
param enableSql bool = false

@description('Azure OpenAI GPT-4.1 model deployment capacity (1 000 TPM units).')
param openAiCapacity int = 10

@description('GPT-4.1 model name.')
param modelName string = 'gpt-4.1'

@description('GPT-4.1 model version.')
param modelVersion string = '2025-04-14'

@description('Tags applied to every resource.')
param tags object = {
  project: 'agentic-ops-advisor'
  environment: environmentName
  managedBy: 'bicep'
}

// ---- Variable helpers -----------------------------------------

var suffix = '${projectName}-${environmentName}'
var identityName = 'id-${suffix}'
var logAnalyticsName = 'log-${suffix}'
var appInsightsName = 'appi-${suffix}'
var sqlServerName = 'sql-${suffix}'
var aiHubName = 'hub-${suffix}'
var aiProjectName = 'proj-${suffix}'
var openAiDeploymentName = 'gpt-4.1'

// ---- Resource Group -------------------------------------------

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// ---- Managed Identity (passwordless auth) ---------------------

module identity 'modules/identity.bicep' = {
  name: 'identity'
  scope: rg
  params: {
    name: identityName
    location: location
    tags: tags
  }
}

// ---- Log Analytics Workspace ----------------------------------

module logAnalytics 'modules/loganalytics.bicep' = {
  name: 'loganalytics'
  scope: rg
  params: {
    name: logAnalyticsName
    location: location
    tags: tags
  }
}

// ---- Application Insights -------------------------------------

module appInsights 'modules/appinsights.bicep' = {
  name: 'appinsights'
  scope: rg
  dependsOn: [logAnalytics]
  params: {
    name: appInsightsName
    location: location
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}

// ---- Azure SQL Server + Database (conditional) -----------------

module sql 'modules/sql.bicep' = if (enableSql) {
  name: 'sql'
  scope: rg
  params: {
    serverName: sqlServerName
    databaseName: sqlDatabaseName
    databaseSku: sqlDatabaseSku
    managedIdentityPrincipalId: identity.outputs.principalId
    managedIdentityName: identityName
    location: sqlLocation
    tags: tags
  }
}

// ---- Azure AI Foundry Hub + Project + Model -------------------
// The Hub is a CognitiveServices AIServices account that hosts the
// GPT-4.1 deployment directly. No separate OpenAI module needed.

module aiFoundry 'modules/aifoundry.bicep' = {
  name: 'aifoundry'
  scope: rg
  params: {
    hubName: aiHubName
    projectName: aiProjectName
    location: location
    managedIdentityId: identity.outputs.resourceId
    managedIdentityPrincipalId: identity.outputs.principalId
    deploymentName: openAiDeploymentName
    modelName: modelName
    modelVersion: modelVersion
    capacity: openAiCapacity
    tags: tags
  }
}

// ---- Outputs (used by deploy.sh to populate .env) -------------

@description('Azure AI Foundry project connection string.')
output aiProjectConnectionString string = aiFoundry.outputs.projectConnectionString

@description('Azure OpenAI endpoint URL (from AI Hub).')
output openAiEndpoint string = aiFoundry.outputs.hubEndpoint

@description('Azure OpenAI GPT-4.1 deployment name.')
output openAiDeployment string = aiFoundry.outputs.modelDeploymentName

@description('Application Insights connection string.')
output appInsightsConnectionString string = appInsights.outputs.connectionString

@description('Azure SQL ODBC connection string (empty when SQL is disabled).')
output sqlConnectionString string = enableSql ? sql.outputs.connectionString : ''

@description('Resource group name.')
output resourceGroupName string = rg.name

@description('Managed identity client ID.')
output managedIdentityClientId string = identity.outputs.clientId

@description('Container Registry login server URL (e.g., crhubagentopsprod.azurecr.io).')
output acrLoginServer string = aiFoundry.outputs.acrLoginServer

@description('Container Registry name.')
output acrName string = aiFoundry.outputs.acrName
