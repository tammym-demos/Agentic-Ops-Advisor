// Azure SQL Server + Database
// Hosts production telemetry data for the Agentic Ops Advisor.
//
// Auth: Azure AD-only authentication via the user-assigned managed identity.
// MCAPS policy requires azureADOnlyAuthentication = true (no SQL auth).

param serverName string
param databaseName string

param databaseSku string = 'Basic'
param managedIdentityPrincipalId string
param managedIdentityName string = 'agentops-identity'
param location string
param tags object = {}

// ---- SQL Server (Azure AD-only auth) --------------------------

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: serverName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    administrators: {
      administratorType: 'ActiveDirectory'
      principalType: 'Application'
      login: managedIdentityName
      sid: managedIdentityPrincipalId
      tenantId: subscription().tenantId
      azureADOnlyAuthentication: true
    }
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

// Allow Azure services to connect (required for managed identity auth from AI Foundry)
resource allowAzureServices 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sqlServer
  name: 'AllowAllAzureIPs'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// ---- SQL Database ---------------------------------------------

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: databaseName
  location: location
  tags: tags
  sku: {
    name: databaseSku
    tier: databaseSku
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 2147483648
    readScale: 'Disabled'
    zoneRedundant: false
  }
}

// ---- Role assignment: managed identity → SQL Server contributor
// Grants the user-assigned identity the ability to connect to the SQL server.

var sqlContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '6d8ee4ec-f05a-4a1d-8b00-a9b17e38b437' // SQL DB Contributor
)

resource sqlRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: sqlServer
  name: guid(sqlServer.id, managedIdentityPrincipalId, sqlContributorRoleId)
  properties: {
    roleDefinitionId: sqlContributorRoleId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ---- Outputs --------------------------------------------------

output serverFqdn string = sqlServer.properties.fullyQualifiedDomainName
output connectionString string = 'Driver={ODBC Driver 18 for SQL Server};Server=${sqlServer.properties.fullyQualifiedDomainName};Database=${databaseName};Authentication=ActiveDirectoryDefault;'
output serverId string = sqlServer.id
output databaseId string = sqlDatabase.id
