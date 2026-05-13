targetScope = 'resourceGroup'

// SRE Agent managed identity RBAC for Agentic Ops Advisor telemetry access.
// The SRE Agent resource is created in the Azure portal, so its managed identity
// principal ID must be supplied as a parameter when this module is enabled.
//
// IMPORTANT: The opposite cross-resource assignment (our managed identity -> SRE Agent)
// cannot be modeled here because the SRE Agent resource is not managed by this Bicep.
// Grant that role separately after the SRE Agent exists:
//   az role assignment create --assignee {our-identity-principal-id} --role "SRE Agent Standard User" --scope /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.App/{sre-agent-resource-id}

@description('Principal ID of the portal-created SRE Agent managed identity.')
param principalId string

@description('Resource group that the SRE Agent should be able to read for telemetry and diagnostics. This module deploys at that resource-group scope.')
param resourceGroupName string = resourceGroup().name

var readerRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'acdd72a7-3385-48ef-bd42-f606fba81ae7' // Reader
)
var monitoringReaderRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '43d0d8ad-25c7-4714-9337-8ba259a9fe05' // Monitoring Reader
)
var logAnalyticsReaderRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '73c42c96-874c-492b-b04d-ab87d138a893' // Log Analytics Reader
)

// Reader: baseline read-only access to resource metadata across the resource group.
resource readerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().subscriptionId, resourceGroupName, principalId, readerRoleDefinitionId)
  properties: {
    roleDefinitionId: readerRoleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// Monitoring Reader: allows the SRE Agent to inspect Azure Monitor metrics and alerts.
resource monitoringReaderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().subscriptionId, resourceGroupName, principalId, monitoringReaderRoleDefinitionId)
  properties: {
    roleDefinitionId: monitoringReaderRoleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// Log Analytics Reader: allows KQL/query access to Log Analytics data for investigations.
resource logAnalyticsReaderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().subscriptionId, resourceGroupName, principalId, logAnalyticsReaderRoleDefinitionId)
  properties: {
    roleDefinitionId: logAnalyticsReaderRoleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
