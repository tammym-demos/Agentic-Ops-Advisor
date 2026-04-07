// ============================================================
// Agentic Ops Advisor — Resource-group-scoped Bicep template
//
// This is the RG-scoped variant of main.bicep, used when the
// deploy SP has Contributor only at resource-group scope (not
// subscription). The resource group must already exist — create
// it via `az group create` before running this template.
//
// Deploy with:
//   az group create --name rg-agentic-ops-advisor --location eastus
//   az deployment group create \
//     --resource-group rg-agentic-ops-advisor \
//     --template-file infra/main-rg.bicep \
//     --parameters @infra/parameters.json
//
// To use the subscription-scoped main.bicep instead, grant
// subscription Contributor:
//   scripts/grant-sp-permissions.sh
// ============================================================

targetScope = 'resourceGroup'

// ---- Parameters -----------------------------------------------
// Kept identical to main.bicep for parameter-file compatibility.

@description('Azure region for all resources.')
param location string = 'eastus'

@description('Name of the resource group (kept for parameter-file compatibility; ignored at RG scope).')
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

// ---- Managed Identity (passwordless auth) ---------------------

module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    name: identityName
    location: location
    tags: tags
  }
}

// ---- Log Analytics Workspace ----------------------------------

module logAnalytics 'modules/loganalytics.bicep' = {
  name: 'loganalytics'
  params: {
    name: logAnalyticsName
    location: location
    tags: tags
  }
}

// ---- Application Insights -------------------------------------

module appInsights 'modules/appinsights.bicep' = {
  name: 'appinsights'
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

module aiFoundry 'modules/aifoundry.bicep' = {
  name: 'aifoundry'
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

// ---- Outputs (identical to main.bicep) ------------------------

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

@description('Resource group name (from parameter, for deploy script compatibility).')
output resourceGroupName string = resourceGroupName

@description('Managed identity client ID.')
output managedIdentityClientId string = identity.outputs.clientId

@description('Container Registry login server URL (e.g., crhubagentopsprod.azurecr.io).')
output acrLoginServer string = aiFoundry.outputs.acrLoginServer

@description('Container Registry name.')
output acrName string = aiFoundry.outputs.acrName
