// Azure Key Vault module
// Used as a pre-flight resource to hold deployment secrets (e.g. SQL admin password)
// before the main Bicep deployment runs.
//
// The vault is configured with:
//  - RBAC-based access control (no legacy access policies)
//  - Soft-delete enabled (90-day retention) — cannot be disabled
//  - Purge protection disabled so the vault can be fully deleted in dev/test
//  - Public network access enabled (restrict in production with allowedIpRules)

param name string
param location string
param tags object = {}

@description('Object ID of the principal (user/SP) that will be granted Key Vault Secrets Officer.')
param secretsOfficerObjectId string = ''

@description('Principal type for the role assignment (User, ServicePrincipal, or Group).')
@allowed(['User', 'ServicePrincipal', 'Group'])
param secretsOfficerPrincipalType string = 'User'

@description('Tenant ID for the vault. Defaults to the subscription tenant.')
param tenantId string = subscription().tenantId

// ---- Key Vault ------------------------------------------------

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// ---- Role assignment: Secrets Officer -------------------------
// Grants the deploying principal the ability to read/write secrets
// so that deploy.sh can store sql-admin-password immediately after
// the vault is created.

var secretsOfficerRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'b86a8fe4-44ce-4948-aee5-eccb2c155cd7' // Key Vault Secrets Officer
)

resource secretsOfficerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(secretsOfficerObjectId)) {
  scope: keyVault
  name: guid(keyVault.id, secretsOfficerObjectId, secretsOfficerRoleId)
  properties: {
    roleDefinitionId: secretsOfficerRoleId
    principalId: secretsOfficerObjectId
    principalType: secretsOfficerPrincipalType
  }
}

// ---- Outputs --------------------------------------------------

output keyVaultId string = keyVault.id
output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
