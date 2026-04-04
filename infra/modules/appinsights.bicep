// Application Insights (workspace-based)
// Provides distributed tracing and telemetry for the agent service.

param name string
param location string
param logAnalyticsWorkspaceId string
param tags object = {}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: name
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceId
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    RetentionInDays: 90
  }
}

output resourceId string = appInsights.id
output instrumentationKey string = appInsights.properties.InstrumentationKey
output connectionString string = appInsights.properties.ConnectionString
