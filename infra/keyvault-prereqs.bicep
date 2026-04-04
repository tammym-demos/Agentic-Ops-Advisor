// ============================================================
// infra/keyvault-prereqs.bicep
//
// Pre-flight Bicep template that creates the secrets resource
// group and the Key Vault that holds deployment secrets (e.g.
// sql-admin-password).  This template MUST be deployed before
// infra/main.bicep because the ARM parameter reference in
// parameters.json requires the vault to exist at deploy time.
//
// Deploy with:
//   az deployment sub create \
//     --location eastus2 \
//     --template-file infra/keyvault-prereqs.bicep \
//     --parameters keyVaultName=kv-agentic-ops-secrets \
//                  secretsRgName=rg-secrets \
//                  secretsOfficerObjectId=$(az ad signed-in-user show --query id -o tsv)
// ============================================================

targetScope = 'subscription'

// ---- Parameters -----------------------------------------------

@description('Azure region for the secrets resource group and vault.')
param location string = 'eastus2'

@description('Name of the resource group that will hold the Key Vault.')
param secretsRgName string = 'rg-secrets'

@description('Name of the Key Vault to create.')
param keyVaultName string = 'kv-agentic-ops-secrets'

@description('Object ID of the principal (user/SP) to grant Key Vault Secrets Officer.')
param secretsOfficerObjectId string = ''

@description('Principal type for the Secrets Officer role assignment (User, ServicePrincipal, or Group).')
@allowed(['User', 'ServicePrincipal', 'Group'])
param secretsOfficerPrincipalType string = 'User'

@description('Tags applied to the resource group and vault.')
param tags object = {
  project: 'agentic-ops-advisor'
  purpose: 'deployment-secrets'
  managedBy: 'bicep'
}

// ---- Secrets Resource Group -----------------------------------

resource secretsRg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: secretsRgName
  location: location
  tags: tags
}

// ---- Key Vault ------------------------------------------------

module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault-prereqs'
  scope: secretsRg
  params: {
    name: keyVaultName
    location: location
    tags: tags
    secretsOfficerObjectId: secretsOfficerObjectId
    secretsOfficerPrincipalType: secretsOfficerPrincipalType
  }
}

// ---- Outputs --------------------------------------------------

@description('Resource ID of the Key Vault (used in parameters.json reference).')
output keyVaultId string = keyVault.outputs.keyVaultId

@description('URI of the Key Vault.')
output keyVaultUri string = keyVault.outputs.keyVaultUri

@description('Name of the Key Vault.')
output keyVaultName string = keyVault.outputs.keyVaultName
