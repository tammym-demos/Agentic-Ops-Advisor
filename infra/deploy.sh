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
#   SQL_ADMIN_PASSWORD      — SQL admin password (required unless using KV ref)
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
PARAMS_FILE="${SCRIPT_DIR}/parameters.json"
DEPLOYMENT_NAME="agentic-ops-advisor-$(date +%Y%m%d%H%M%S)"
WHAT_IF=false

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

# 1. Azure CLI installed
if ! command -v az &>/dev/null; then
  error "Azure CLI (az) is not installed. Install from https://aka.ms/install-azure-cli"
fi
success "Azure CLI found: $(az version --query '"azure-cli"' -o tsv)"

# 2. Logged in
if ! az account show &>/dev/null; then
  error "Not logged in to Azure. Run: az login"
fi
success "Logged in as: $(az account show --query user.name -o tsv)"

# 3. Set subscription
info "Setting subscription to: ${SUBSCRIPTION_ID}"
az account set --subscription "${SUBSCRIPTION_ID}"
success "Active subscription: $(az account show --query name -o tsv) (${SUBSCRIPTION_ID})"

# 4. Verify template and params files exist
[[ -f "${TEMPLATE_FILE}" ]] || error "Template not found: ${TEMPLATE_FILE}"
[[ -f "${PARAMS_FILE}" ]]   || error "Parameters file not found: ${PARAMS_FILE}"
success "Template and parameters files found."

# 5. Register required resource providers
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
