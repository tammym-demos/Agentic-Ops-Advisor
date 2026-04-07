# Copilot Instructions — Agentic Ops Advisor

## Project Overview

This is the **Agentic Ops Advisor** — a governed, production-style AI agent that performs
root-cause + change-context reasoning over infrastructure telemetry and operator intent.
It is designed for deployment to **Azure AI Foundry Agent Service**.

## Tech Stack

- **Language:** Python 3.11+
- **Agent Framework:** Azure AI Agent Service SDK (`azure-ai-projects`)
- **LLM:** GPT-4.1 (via Azure OpenAI)
- **Local Database:** SQLite (dev) / Azure SQL (production)
- **Evaluation:** `azure-ai-evaluation` + custom evaluators
- **Observability:** OpenTelemetry → Application Insights / Azure Monitor
- **IaC:** Bicep templates
- **CI/CD:** GitHub Actions

## Architecture

The agent has **three tool surfaces**:

1. **SQL Telemetry Tool** (`tools/sql_telemetry.py`) — queries synthetic infrastructure
   telemetry (GPU, network, cost, incidents) from SQLite (local) or Azure SQL (deploy)
2. **Work IQ Context Stub** (`tools/work_context_stub.py`) — returns synthetic "work context"
   (change events, decisions, ownership, runbooks). Feature flag: `ENABLE_WORK_IQ`
3. **Action Stub** (`tools/action_stub.py`) — proposes changes and simulates approval workflows.
   Never modifies external systems.

Optional: MCP wrapper (`tools/work_context_mcp.py`) behind `ENABLE_MCP` flag.

## Key Conventions

- **All data is synthetic.** Never use real/internal data. Include disclaimers.
- **Work IQ is simulated.** Always state: "We're simulating Work IQ outputs in this demo.
  Work IQ is in public preview and requires Microsoft 365 Copilot licensing + admin consent."
- **Feature flags** control demo scope: `ENABLE_WORK_IQ` (default ON), `ENABLE_MCP` (default OFF)
- **Content recording OFF by default:** `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=false`
- **Language alignment:** Use terms like "agentic ops", "hybrid", "governance",
  "telemetry + intent", "self-driving operations"
- **Update `.gitignore`** when adding new tools, dependencies, or generated artifacts

## File Structure

```
agent/          — Agent definition, system prompt, config
tools/          — Three tool surfaces (telemetry, work context, actions)
data/           — Synthetic data generators and seed files
eval/           — Evaluation test sets, evaluators, runner
monitoring/     — Azure Monitor Workbook templates
scripts/        — Local runner, regression demo, DB setup
infra/          — Bicep IaC templates
docs/pages/     — GitHub Pages brochure site
tests/          — Unit and integration tests
.github/        — CI/CD workflows
```

## Environment Variables

See `.env.example` for the complete list. Key variables:
- `DB_MODE` — `sqlite` (local) or connection string (Azure SQL)
- `ENABLE_WORK_IQ` / `ENABLE_MCP` — feature flags
- `AZURE_AI_PROJECT_CONNECTION_STRING` — Foundry project connection
- `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_DEPLOYMENT` — model config
- `APPLICATIONINSIGHTS_CONNECTION_STRING` — observability export

## Agent Persona

The agent is a **professional ops teammate** with light humor:
- Short, crisp bullets
- Always include a "Confidence" line (High/Med/Low)
- Always cite evidence from tools ("Telemetry query showed…", "Change context indicated…")
- Include a "Next best question" if confidence is not High
- Light humor OK (roast ambiguous requests, not people)

## Testing

- Run tests: `pytest tests/`
- Run linting: `ruff check .`
- Run eval: `python eval/run_eval.py`

## Azure Configuration

- Subscription: _(set via `AZURE_SUBSCRIPTION_ID` env var or GitHub secret)_
- Region: `eastus`
- Resource Group: `rg-agentic-ops-advisor`
- Tenant: _(your Azure AD tenant)_
