# SRE Agent Setup Guide

> Quick start for deploying the **Agentic Ops Advisor** to Azure AI Foundry Agent Service

---

## Prerequisites

### Required
- **Azure subscription** with Owner or Contributor access
- **Python 3.11+** installed locally
- **Azure CLI** ([Install](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli))
- **Azure Developer CLI (azd)** ([Install](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd))
- **Docker** (for local container testing)
- **Git** (to clone the repository)

### Optional (for local development)
- **VS Code** with Python extension
- **pytest** for running tests
- **ruff** for linting

---

## 1. Clone the Repository

```bash
git clone https://github.com/tammym-demos/Agentic-Ops-Advisor.git
cd Agentic-Ops-Advisor
```

---

## 2. Environment Setup

### 2.1 Copy Environment Template

```bash
cp .env.example .env
```

### 2.2 Configure Required Variables

Edit `.env` with your Azure settings:

```bash
# === Azure AI Foundry ===
AZURE_AI_AGENTS_ENDPOINT=https://<your-hub>.services.ai.azure.com/api/projects/<your-project>
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4.1
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# === Database ===
# For local dev: leave as "sqlite" (default)
DB_MODE=sqlite

# For Azure deployment: set to Azure SQL connection string
# DB_CONNECTION_STRING=Driver={ODBC Driver 18 for SQL Server};Server=<server>.database.windows.net;Database=agentops;Authentication=ActiveDirectoryDefault;

# === Feature Flags ===
ENABLE_WORK_IQ=true   # Enable Work IQ context tool (simulated data)
ENABLE_MCP=false      # Enable MCP wrapper (advanced, default OFF)

# === Observability ===
APPLICATIONINSIGHTS_CONNECTION_STRING=<from-bicep-output>
AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=false  # Content recording OFF by default

# === Azure Deployment ===
AZURE_SUBSCRIPTION_ID=<your-subscription-id>
AZURE_RESOURCE_GROUP=rg-agentic-ops-advisor
AZURE_LOCATION=eastus
```

### 2.3 Environment Variables Reference

| Variable | Purpose | Required |
|----------|---------|----------|
| `AZURE_AI_AGENTS_ENDPOINT` | Azure AI Foundry project endpoint | ✅ Production |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource URL | ✅ Always |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name (e.g., `gpt-4.1`) | ✅ Always |
| `DB_MODE` | `sqlite` (local) or connection string (Azure SQL) | ✅ Always |
| `ENABLE_WORK_IQ` | Enable Work IQ context tool | ❌ Default: `true` |
| `ENABLE_MCP` | Enable MCP wrapper | ❌ Default: `false` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Observability export | ✅ Production |
| `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` | Content recording toggle | ❌ Default: `false` |

---

## 3. Local Development Setup

### 3.1 Install Python Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3.2 Initialize Local SQLite Database

```bash
python scripts/setup_db.py
```

This creates `telemetry.db` with synthetic infrastructure data (GPU metrics, network stats, cost data, incidents).

### 3.3 Verify Local Setup

```bash
# Run tests
pytest tests/ -q

# Run linting
ruff check .

# Run local demo (tool queries only, no LLM)
python scripts/regression_demo.py
```

**Expected output:**
- All tests pass
- No linting errors
- `regression_demo.py` outputs synthetic telemetry query results

---

## 4. Container-Based Local Testing

This project is **container-only** for consistency with Azure deployment.

### 4.1 Build Container

```bash
docker build -t agentic-ops-advisor .
```

### 4.2 Run Container Locally

```bash
docker run -p 8088:8088 --env-file .env agentic-ops-advisor
```

The container runs `scripts/serve.py`, which implements the Foundry Responses API v1.

### 4.3 Test Health Endpoint

```bash
curl http://localhost:8088/health
```

**Expected response:**
```json
{"status": "healthy", "timestamp": "2025-06-15T12:00:00Z"}
```

---

## 5. Deploying to Azure AI Foundry

### 5.1 Install Azure AI Agents Extension

```bash
azd ext install azure.ai.agents
```

### 5.2 Authenticate to Azure

```bash
# Login to Azure
azd auth login

# Set subscription (optional, if you have multiple)
az account set --subscription <your-subscription-id>
```

### 5.3 Deploy Infrastructure + Agent (One Command)

```bash
azd up
```

**What `azd up` does:**
1. Provisions Azure resources via Bicep (`infra/main.bicep`):
   - Azure AI Foundry Hub + Project
   - Azure OpenAI GPT-4.1 deployment
   - Azure SQL Database
   - Application Insights workspace
   - Azure Container Registry (ACR)
2. Builds Docker image
3. Pushes image to ACR
4. Registers agent in Azure AI Foundry
5. Outputs connection strings and endpoints

**Expected deployment time:** 10-15 minutes

### 5.4 Retrieve Deployment Outputs

After `azd up` completes, note the outputs:

```
AZURE_AI_AGENTS_ENDPOINT: https://<hub-name>.services.ai.azure.com/api/projects/<project-name>
APPLICATIONINSIGHTS_CONNECTION_STRING: InstrumentationKey=<key>;...
ACR_LOGIN_SERVER: <acr-name>.azurecr.io
```

Update your `.env` with these values for future local runs.

---

## 6. First Run in Azure AI Foundry

### 6.1 Open Foundry Portal

Navigate to: **https://ai.azure.com**

1. Select your **Hub** (e.g., `hub-agentops-prod`)
2. Select your **Project** (e.g., `project-agentops`)
3. Go to **Agents** → `agentic-ops-advisor`

### 6.2 Test Sample Queries

Try these example queries in the Foundry chat interface:

#### Query 1: GPU Performance Analysis
```
Show me GPU cluster performance over the last 7 days
```

**Expected response:**
- Summary: GPU throttling detected on Day 5
- Evidence: Telemetry query showed 43% performance drop
- Analysis: Correlates with CUDA driver update
- Recommended Actions: Rollback driver version
- Confidence: High

#### Query 2: Network Anomaly Detection
```
Any network anomalies in the last 24 hours?
```

**Expected response:**
- Summary: Egress spike on `net-cluster-east`
- Evidence: Telemetry query showed 2.3 TB egress (vs. 800 GB baseline)
- Change context: Correlates with data migration project (Work IQ stub)
- Recommended Actions: Review migration job, check compression
- Confidence: Med (limited change context)

#### Query 3: Cost Analysis
```
What's driving the 40% cost increase this week?
```

**Expected response:**
- Summary: Egress and GPU costs increased
- Evidence: Telemetry breakdown by service
- Analysis: Data transfer + extended GPU runs
- Recommended Actions: Optimize data locality, review job scheduling
- Confidence: High

---

## 7. Feature Flags

### 7.1 Work IQ Context Tool

**Purpose:** Simulates Microsoft 365 Copilot Work IQ integration (change events, decisions, ownership, runbooks)

**Enable:**
```bash
ENABLE_WORK_IQ=true  # Default: ON
```

**Disable:**
```bash
ENABLE_WORK_IQ=false
```

When disabled, the agent only uses telemetry data (no change context).

### 7.2 MCP Wrapper

**Purpose:** Exposes Work IQ context via Model Context Protocol (advanced feature)

**Enable:**
```bash
ENABLE_MCP=true
```

**Disable:**
```bash
ENABLE_MCP=false  # Default: OFF
```

⚠️ **Note:** MCP requires additional setup. See `tools/work_context_mcp.py` for details.

---

## 8. Observability & Monitoring

### 8.1 Application Insights

After deployment, view agent traces in Azure Portal:

1. Navigate to **Application Insights** resource (e.g., `appi-agentops-prod`)
2. Go to **Transaction search** → Filter by `customDimensions.tool_name`
3. View tool execution traces, latencies, error rates

### 8.2 Azure Monitor Workbook

Pre-built dashboard for agent performance:

```bash
# Deploy workbook template
az monitor app-insights workbook create \
  --resource-group rg-agentic-ops-advisor \
  --workbook-definition @monitoring/agent-performance-workbook.json
```

**Metrics tracked:**
- Tool invocation counts
- Average latency by tool
- Error rates
- Confidence score distribution

---

## 9. Running Evaluations

### 9.1 Evaluation Framework

The agent includes a production-grade eval pipeline:

- **Test set:** `eval/test_set.jsonl` (20+ scenarios)
- **Evaluators:** Accuracy, groundedness, safety, latency
- **SDK:** `azure-ai-evaluation`

### 9.2 Run Evaluation

```bash
python eval/run_eval.py
```

**Expected output:**
```
=== Evaluation Results ===
Accuracy: 0.85
Groundedness: 0.92
Safety: 1.00
Avg Latency: 2.3s
```

### 9.3 View Evaluation Traces

Evaluation results are exported to Application Insights with tag `eval_run_id`.

---

## 10. Database Migration (SQLite → Azure SQL)

### 10.1 Production Database Setup

After deploying to Azure, migrate from SQLite to Azure SQL:

1. **Get connection string** from Bicep output:
   ```
   DB_CONNECTION_STRING=Driver={ODBC Driver 18 for SQL Server};Server=<server>.database.windows.net;Database=agentops;Authentication=ActiveDirectoryDefault;
   ```

2. **Update `.env`:**
   ```bash
   DB_MODE=<connection-string>
   ```

3. **Run migration script:**
   ```bash
   python scripts/migrate_to_azure_sql.py
   ```

This copies synthetic data from `telemetry.db` to Azure SQL.

---

## 11. Agent Configuration

### 11.1 `agent.yaml` (Foundry Agent Definition)

Located at: `agent.yaml`

```yaml
name: agentic-ops-advisor
description: AI agent for infrastructure telemetry + operator intent reasoning
model: gpt-4.1
tools:
  - sql_telemetry
  - work_context_stub
  - action_stub
```

### 11.2 `azure.yaml` (Azure Developer CLI Config)

Located at: `azure.yaml`

Defines deployment pipeline:
- Infrastructure provisioning (`infra/main.bicep`)
- Container build and push
- Agent registration

---

## 12. Troubleshooting

### Issue: `azd up` fails with "subscription not registered"

**Solution:**
```bash
az provider register --namespace Microsoft.CognitiveServices
az provider register --namespace Microsoft.Sql
az provider register --namespace Microsoft.Insights
```

### Issue: Health check returns 404

**Solution:**
- Verify `serve.py` is running on port 8088
- Check Docker logs: `docker logs <container-id>`
- Ensure `.env` is mounted: `docker run --env-file .env ...`

### Issue: Agent returns "Tool execution failed"

**Solution:**
- Check Application Insights for error traces
- Verify database connection string
- Ensure `AZURE_OPENAI_DEPLOYMENT` matches actual deployment name

### Issue: Work IQ tool returns empty results

**Solution:**
- Verify `ENABLE_WORK_IQ=true` in `.env`
- Check `tools/work_context_stub.py` for synthetic data generation
- This is expected behavior if no matching change events exist

---

## 13. Next Steps

### Production Readiness Checklist

- [ ] Review `.gitignore` (ensure no secrets committed)
- [ ] Set `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=false` for compliance
- [ ] Configure Azure RBAC for Foundry project
- [ ] Set up Azure Monitor alerts for agent errors
- [ ] Run evaluation pipeline on production traffic sample
- [ ] Document runbook for agent updates (`azd deploy`)

### Advanced Features

- [ ] Enable MCP wrapper (`ENABLE_MCP=true`)
- [ ] Customize system prompt (`agent/system_prompt.md`)
- [ ] Add custom evaluators (`eval/evaluators/`)
- [ ] Integrate real Work IQ data (requires Microsoft 365 Copilot licensing)

### Scaling

- [ ] Configure autoscaling for hosted agent
- [ ] Set up Azure SQL read replicas for high-traffic scenarios
- [ ] Implement caching layer for telemetry queries
- [ ] Deploy multi-region for global availability

---

## 14. Additional Resources

- **[Project README](../README.md)** — Comprehensive guide
- **[Differentiation Doc](./sre-agent-differentiation.md)** — Why this agent is different
- **[System Prompt](../agent/system_prompt.md)** — Agent persona and behavior
- **[Brochure Site](https://tammym-demos.github.io/Agentic-Ops-Advisor/)** — Interactive demo walkthrough
- **[Azure AI Foundry Docs](https://learn.microsoft.com/en-us/azure/ai-studio/)** — Platform reference

---

## 15. Synthetic Data Disclaimer

⚠️ **All data in this demo is synthetic.** No real infrastructure, customer, or Microsoft internal data is included. Telemetry metrics, change events, and Work IQ outputs are generated for demonstration purposes only.

Work IQ is in **public preview** and requires:
- Microsoft 365 Copilot licensing
- Admin consent for tenant data access
- Production deployment outside this demo environment

For production use with real Work IQ data, contact your Microsoft account team.

---

## Support

- **Issues:** [GitHub Issues](https://github.com/tammym-demos/Agentic-Ops-Advisor/issues)
- **Discussions:** [GitHub Discussions](https://github.com/tammym-demos/Agentic-Ops-Advisor/discussions)
- **Azure AI Foundry Support:** [Azure Support Portal](https://portal.azure.com/#blade/Microsoft_Azure_Support/HelpAndSupportBlade)
