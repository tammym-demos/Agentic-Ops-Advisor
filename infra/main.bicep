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

@description('Azure OpenAI GPT-4.1 model deployment capacity (1 000 TPM units).')
param openAiCapacity int = 10

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
var openAiName = 'oai-${suffix}'
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

// ---- Azure SQL Server + Database ------------------------------

module sql 'modules/sql.bicep' = {
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

// ---- Azure OpenAI ---------------------------------------------

module openAi 'modules/openai.bicep' = {
  name: 'openai'
  scope: rg
  params: {
    name: openAiName
    location: location
    deploymentName: openAiDeploymentName
    capacity: openAiCapacity
    managedIdentityId: identity.outputs.resourceId
    tags: tags
  }
}

// ---- Azure AI Foundry Hub + Project ---------------------------

module aiFoundry 'modules/aifoundry.bicep' = {
  name: 'aifoundry'
  scope: rg
  dependsOn: [logAnalytics, appInsights, openAi]
  params: {
    hubName: aiHubName
    projectName: aiProjectName
    location: location
    appInsightsId: appInsights.outputs.resourceId
    openAiAccountId: openAi.outputs.resourceId
    openAiEndpoint: openAi.outputs.endpoint
    managedIdentityId: identity.outputs.resourceId
    managedIdentityPrincipalId: identity.outputs.principalId
    tags: tags
  }
}

// ---- Outputs (used by deploy.sh to populate .env) -------------

@description('Azure AI Foundry project connection string.')
output aiProjectConnectionString string = aiFoundry.outputs.projectConnectionString

@description('Azure OpenAI endpoint URL.')
output openAiEndpoint string = openAi.outputs.endpoint

@description('Azure OpenAI GPT-4.1 deployment name.')
output openAiDeployment string = openAiDeploymentName

@description('Application Insights connection string.')
output appInsightsConnectionString string = appInsights.outputs.connectionString

@description('Azure SQL ODBC connection string (ActiveDirectoryDefault — no password).')
output sqlConnectionString string = sql.outputs.connectionString

@description('Resource group name.')
output resourceGroupName string = rg.name

@description('Managed identity client ID.')
output managedIdentityClientId string = identity.outputs.clientId

@description('Container Registry login server URL (e.g., crhubagentopsprod.azurecr.io).')
output acrLoginServer string = aiFoundry.outputs.acrLoginServer

@description('Container Registry name.')
output acrName string = aiFoundry.outputs.acrName
