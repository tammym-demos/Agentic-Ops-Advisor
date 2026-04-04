#!/usr/bin/env bash
# =============================================================================
# infra/deploy.sh — Deploy Agentic Ops Advisor infrastructure to Azure
#
# Usage:
#   ./infra/deploy.sh [--what-if] [--subscription <id>]
#
# Environment variables (override defaults):
#   AZURE_SUBSCRIPTION_ID   — Azure subscription (default: e0b48569-...)
#   AZURE_LOCATION          — Deployment location    (default: eastus2)
#   SQL_ADMIN_PASSWORD      — SQL admin password; stored in Key Vault if secret is missing
#   KEY_VAULT_NAME          — Key Vault name  (default: kv-agentic-ops-secrets)
#   KEY_VAULT_RG            — Key Vault resource group (default: rg-secrets)
#
# The script performs pre-flight checks, deploys via `az deployment sub create`,
# and writes a ready-to-use .env snippet to stdout.
# =============================================================================

set -euo pipefail

# ---- Configuration defaults -------------------------------------------

SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-e0b48569-71a2-40fe-9b7a-2fb859f31288}"
LOCATION="${AZURE_LOCATION:-eastus2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="${SCRIPT_DIR}/main.bicep"
KV_PREREQS_FILE="${SCRIPT_DIR}/keyvault-prereqs.bicep"
PARAMS_FILE="${SCRIPT_DIR}/parameters.json"
DEPLOYMENT_NAME="agentic-ops-advisor-$(date +%Y%m%d%H%M%S)"
WHAT_IF=false

# Key Vault pre-flight defaults (match parameters.json reference)
KV_NAME="${KEY_VAULT_NAME:-kv-agentic-ops-secrets}"
KV_RG="${KEY_VAULT_RG:-rg-secrets}"
KV_SECRET_NAME="sql-admin-password"

# ---- Argument parsing -------------------------------------------------

while [[ $# -gt 0 ]]; do
  case "$1" in
    --what-if)
      WHAT_IF=true
      shift
      ;;
    --subscription)
      SUBSCRIPTION_ID="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# ---- Helpers ----------------------------------------------------------

info()    { echo -e "\033[0;34m[INFO]\033[0m  $*"; }
success() { echo -e "\033[0;32m[OK]\033[0m    $*"; }
warn()    { echo -e "\033[0;33m[WARN]\033[0m  $*"; }
error()   { echo -e "\033[0;31m[ERROR]\033[0m $*" >&2; exit 1; }

# ---- Pre-flight checks ------------------------------------------------

info "Running pre-flight checks…"

# 0. Azure CLI installed (checked first so subsequent steps can use az)
if ! command -v az &>/dev/null; then
  error "Azure CLI (az) is not installed. Install from https://aka.ms/install-azure-cli"
fi
success "Azure CLI found: $(az version --query '"azure-cli"' -o tsv)"

# 1. Logged in
if ! az account show &>/dev/null; then
  error "Not logged in to Azure. Run: az login"
fi
success "Logged in as: $(az account show --query user.name -o tsv)"

# 2. Set subscription
info "Setting subscription to: ${SUBSCRIPTION_ID}"
az account set --subscription "${SUBSCRIPTION_ID}"
success "Active subscription: $(az account show --query name -o tsv) (${SUBSCRIPTION_ID})"

# 3. Verify template and params files exist
[[ -f "${TEMPLATE_FILE}" ]] || error "Template not found: ${TEMPLATE_FILE}"
[[ -f "${PARAMS_FILE}" ]]   || error "Parameters file not found: ${PARAMS_FILE}"
success "Template and parameters files found."

# 4. Register required resource providers
PROVIDERS=(
  "Microsoft.Resources"
  "Microsoft.Sql"
  "Microsoft.CognitiveServices"
  "Microsoft.MachineLearningServices"
  "Microsoft.Insights"
  "Microsoft.OperationalInsights"
  "Microsoft.ManagedIdentity"
  "Microsoft.Storage"
  "Microsoft.KeyVault"
  "Microsoft.ContainerRegistry"
)

info "Checking resource provider registrations…"
for provider in "${PROVIDERS[@]}"; do
  state=$(az provider show --namespace "${provider}" --query registrationState -o tsv 2>/dev/null || echo "NotFound")
  if [[ "${state}" != "Registered" ]]; then
    warn "Registering provider: ${provider}"
    az provider register --namespace "${provider}" --wait
    success "Registered: ${provider}"
  else
    success "Already registered: ${provider}"
  fi
done

# 5. Key Vault pre-flight: ensure kv-agentic-ops-secrets exists with sql-admin-password
#    ARM Key Vault parameter references require the vault to exist BEFORE the main
#    deployment starts, so we create it here if it is missing.
info "Checking Key Vault pre-flight: ${KV_NAME} (${KV_RG})…"

# Query by vault name across the subscription to avoid requiring the RG to exist first.
KV_EXISTS=$(az keyvault list --subscription "${SUBSCRIPTION_ID}" \
  --query "[?name=='${KV_NAME}'].name" -o tsv 2>/dev/null || echo "")

if [[ -z "${KV_EXISTS}" ]]; then
  info "Key Vault not found — deploying keyvault-prereqs.bicep…"
  [[ -f "${KV_PREREQS_FILE}" ]] || error "keyvault-prereqs.bicep not found: ${KV_PREREQS_FILE}"

  # Detect principal type: service principal vs. interactive user.
  ACCOUNT_TYPE=$(az account show --query user.type -o tsv 2>/dev/null || echo "user")
  if [[ "${ACCOUNT_TYPE}" == "servicePrincipal" ]]; then
    SP_NAME=$(az account show --query user.name -o tsv 2>/dev/null || echo "")
    if [[ -n "${SP_NAME}" ]]; then
      DEPLOYER_OBJECT_ID=$(az ad sp show --id "${SP_NAME}" --query id -o tsv 2>/dev/null || echo "")
    else
      DEPLOYER_OBJECT_ID=""
    fi
    PRINCIPAL_TYPE="ServicePrincipal"
  else
    DEPLOYER_OBJECT_ID=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || echo "")
    PRINCIPAL_TYPE="User"
  fi

  if [[ -z "${DEPLOYER_OBJECT_ID}" ]]; then
    warn "Could not determine deployer object ID — skipping Secrets Officer role assignment."
    DEPLOYER_OBJECT_ID=""
  fi

  az deployment sub create \
    --name "keyvault-prereqs-$(date +%Y%m%d%H%M%S)" \
    --location "${LOCATION}" \
    --template-file "${KV_PREREQS_FILE}" \
    --parameters \
        location="${LOCATION}" \
        secretsRgName="${KV_RG}" \
        keyVaultName="${KV_NAME}" \
        secretsOfficerObjectId="${DEPLOYER_OBJECT_ID}" \
        secretsOfficerPrincipalType="${PRINCIPAL_TYPE}" \
    --subscription "${SUBSCRIPTION_ID}" \
    --output none
  success "Key Vault created: ${KV_NAME}"
else
  success "Key Vault already exists: ${KV_NAME}"
fi

# Ensure the sql-admin-password secret is set in the vault.
# Use SQL_ADMIN_PASSWORD env var if provided; in non-interactive environments
# (no TTY) this variable is required — the script will fail with a clear error.
SECRET_EXISTS=$(az keyvault secret show --vault-name "${KV_NAME}" \
  --name "${KV_SECRET_NAME}" --query name -o tsv 2>/dev/null || echo "")

if [[ -z "${SECRET_EXISTS}" ]]; then
  if [[ -n "${SQL_ADMIN_PASSWORD:-}" ]]; then
    SQL_PWD="${SQL_ADMIN_PASSWORD}"
  elif [[ -t 0 ]] && [[ -t 2 ]]; then
    # Interactive session (stdin and stderr are both TTYs) — prompt safely
    info "Secret '${KV_SECRET_NAME}' not found in vault."
    read -r -s -p "  Enter SQL admin password to store in Key Vault: " SQL_PWD
    echo ""
    [[ -n "${SQL_PWD}" ]] || error "Password cannot be empty."
  else
    error "Secret '${KV_SECRET_NAME}' is missing from ${KV_NAME} and SQL_ADMIN_PASSWORD env var is not set. Set SQL_ADMIN_PASSWORD before running this script in non-interactive mode."
  fi
  az keyvault secret set \
    --vault-name "${KV_NAME}" \
    --name "${KV_SECRET_NAME}" \
    --value "${SQL_PWD}" \
    --output none
  success "Secret '${KV_SECRET_NAME}' stored in ${KV_NAME}."
else
  success "Secret '${KV_SECRET_NAME}' already present in ${KV_NAME}."
fi

# 6. Validate Bicep template (--what-if exits after this step)
info "Validating Bicep template…"
if [[ "${WHAT_IF}" == "true" ]]; then
  info "Running what-if analysis (no resources will be created)…"
  az deployment sub what-if \
    --location "${LOCATION}" \
    --template-file "${TEMPLATE_FILE}" \
    --parameters "@${PARAMS_FILE}" \
    --subscription "${SUBSCRIPTION_ID}"
  success "What-if analysis complete. No changes were made."
  exit 0
fi

az deployment sub validate \
  --location "${LOCATION}" \
  --template-file "${TEMPLATE_FILE}" \
  --parameters "@${PARAMS_FILE}" \
  --subscription "${SUBSCRIPTION_ID}" \
  --output none
success "Template validation passed."

# ---- Deploy -----------------------------------------------------------

info "Starting deployment: ${DEPLOYMENT_NAME}"
info "This may take 10–20 minutes…"

DEPLOY_OUTPUT=$(az deployment sub create \
  --name "${DEPLOYMENT_NAME}" \
  --location "${LOCATION}" \
  --template-file "${TEMPLATE_FILE}" \
  --parameters "@${PARAMS_FILE}" \
  --subscription "${SUBSCRIPTION_ID}" \
  --output json)

success "Deployment complete!"

# ---- Extract outputs --------------------------------------------------

get_output() {
  local key="$1"
  echo "${DEPLOY_OUTPUT}" | \
    python3 -c "import sys, json; key=sys.argv[1]; d=json.load(sys.stdin); print(d.get('properties',{}).get('outputs',{}).get(key,{}).get('value',''))" "${key}"
}

AI_PROJECT_CONN=$(get_output aiProjectConnectionString)
OPENAI_ENDPOINT=$(get_output openAiEndpoint)
OPENAI_DEPLOYMENT=$(get_output openAiDeployment)
APPINSIGHTS_CONN=$(get_output appInsightsConnectionString)
SQL_CONN=$(get_output sqlConnectionString)
RG_NAME=$(get_output resourceGroupName)
IDENTITY_CLIENT_ID=$(get_output managedIdentityClientId)

# ---- Print .env snippet -----------------------------------------------

echo ""
echo "================================================================"
echo "  Deployment outputs — copy to your .env file"
echo "================================================================"
cat <<ENV
# === Azure AI Foundry ===
AZURE_AI_PROJECT_CONNECTION_STRING=${AI_PROJECT_CONN}
AZURE_OPENAI_ENDPOINT=${OPENAI_ENDPOINT}
AZURE_OPENAI_DEPLOYMENT=${OPENAI_DEPLOYMENT}
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# === Database ===
DB_MODE=azure
DB_CONNECTION_STRING=${SQL_CONN}

# === Observability ===
APPLICATIONINSIGHTS_CONNECTION_STRING=${APPINSIGHTS_CONN}
AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=false

# === Azure ===
AZURE_SUBSCRIPTION_ID=${SUBSCRIPTION_ID}
AZURE_RESOURCE_GROUP=${RG_NAME}
AZURE_LOCATION=${LOCATION}
AZURE_CLIENT_ID=${IDENTITY_CLIENT_ID}
ENV
echo "================================================================"
echo ""
success "Done. Save the values above to your .env file."
