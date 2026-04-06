#!/usr/bin/env bash
# =============================================================================
# Grant subscription-scope Contributor to the deploy Service Principal
#
# Run this ONE TIME as an Azure Owner or User Access Administrator to allow
# the GitHub Actions SP to run subscription-scoped Bicep deployments
# (az deployment sub create).
#
# Without this, deploy.yml falls back to resource-group-scoped deployment
# using main-rg.bicep, which works but cannot create the RG itself.
#
# Usage:
#   ./scripts/grant-sp-permissions.sh
#   ./scripts/grant-sp-permissions.sh --sp-object-id <id> --subscription <id>
# =============================================================================

set -euo pipefail

# ---- Defaults (match project config) -----------------------------------------

SP_OBJECT_ID="${SP_OBJECT_ID:-d30fcff3-4eab-4b85-a366-f9a17142be39}"
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-e0b48569-71a2-40fe-9b7a-2fb859f31288}"
RG_NAME="${AZURE_RESOURCE_GROUP:-rg-agentic-ops-advisor}"

# ---- Argument parsing ---------------------------------------------------------

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sp-object-id)  SP_OBJECT_ID="$2";    shift 2 ;;
    --subscription)  SUBSCRIPTION_ID="$2"; shift 2 ;;
    --rg)            RG_NAME="$2";         shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--sp-object-id <id>] [--subscription <id>] [--rg <name>]"
      echo ""
      echo "Grants the deploy SP subscription-scope Contributor so that"
      echo "'az deployment sub create' works in the deploy pipeline."
      echo ""
      echo "Defaults:"
      echo "  SP_OBJECT_ID:    ${SP_OBJECT_ID}"
      echo "  SUBSCRIPTION_ID: ${SUBSCRIPTION_ID}"
      echo "  RG_NAME:         ${RG_NAME}"
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

# ---- Pre-flight ---------------------------------------------------------------

echo "🔍 Checking Azure CLI login..."
az account show --output none 2>/dev/null || {
    echo "❌ Not logged in. Run: az login"
    exit 1
}

CURRENT_SUB=$(az account show --query id -o tsv)
if [[ "$CURRENT_SUB" != "$SUBSCRIPTION_ID" ]]; then
    echo "⚠️  Current subscription ($CURRENT_SUB) differs from target ($SUBSCRIPTION_ID)"
    echo "   Switching..."
    az account set --subscription "$SUBSCRIPTION_ID"
fi

# ---- Check current RG-scope assignment ----------------------------------------

echo ""
echo "📋 Current role assignments for SP ${SP_OBJECT_ID}:"
az role assignment list \
    --assignee "$SP_OBJECT_ID" \
    --query "[].{Role:roleDefinitionName, Scope:scope}" \
    --output table 2>/dev/null || echo "(could not list)"

# ---- Grant subscription-scope Contributor -------------------------------------

SUB_SCOPE="/subscriptions/${SUBSCRIPTION_ID}"

echo ""
echo "🔧 Assigning Contributor at subscription scope..."
echo "   SP:    ${SP_OBJECT_ID}"
echo "   Scope: ${SUB_SCOPE}"
echo ""

az role assignment create \
    --assignee-object-id "$SP_OBJECT_ID" \
    --assignee-principal-type ServicePrincipal \
    --role "Contributor" \
    --scope "$SUB_SCOPE" \
    --output none 2>&1 && {
    echo "✅ Subscription-scope Contributor granted."
    echo ""
    echo "The deploy pipeline can now use 'az deployment sub create' directly."
    echo "Run a workflow_dispatch deploy to verify."
} || {
    echo "❌ Failed to assign role."
    echo ""
    echo "You need Owner or User Access Administrator on subscription ${SUBSCRIPTION_ID}."
    echo "Ask your admin to run:"
    echo ""
    echo "  az role assignment create \\"
    echo "    --assignee-object-id ${SP_OBJECT_ID} \\"
    echo "    --assignee-principal-type ServicePrincipal \\"
    echo "    --role Contributor \\"
    echo "    --scope ${SUB_SCOPE}"
    exit 1
}

# ---- Verify -------------------------------------------------------------------

echo ""
echo "📋 Updated role assignments:"
az role assignment list \
    --assignee "$SP_OBJECT_ID" \
    --query "[].{Role:roleDefinitionName, Scope:scope}" \
    --output table
