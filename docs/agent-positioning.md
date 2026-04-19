# SRE Agent Differentiation

> **Agentic Ops Advisor** — A governed AI agent for infrastructure operations that combines telemetry analysis with organizational context

---

## What Makes This Agent Different?

This is **not** a generic copilot, traditional dashboard, or static runbook. The Agentic Ops Advisor represents a new category: **governed, production-ready agentic operations**.

---

## 1. Beyond Generic Copilots

### Traditional Copilots
- Generic chat interface without domain expertise
- No access to live infrastructure telemetry
- Lack organizational context (who changed what, when, why)
- Provide suggestions without correlation to actual system state
- No governance or auditability

### Agentic Ops Advisor
✅ **Domain-specific reasoning** — Built for infrastructure ops workflows  
✅ **Live telemetry integration** — Queries actual system metrics (GPU, network, cost, incidents)  
✅ **Change-context awareness** — Correlates telemetry with Work IQ organizational data  
✅ **Governed execution** — Feature flags, content recording controls, synthetic data disclaimers  
✅ **Production-ready architecture** — Azure AI Foundry Agent Service deployment with OpenTelemetry observability  

---

## 2. Beyond Dashboards & Static Monitoring

### Traditional Dashboards
- Reactive — operators must interpret visualizations
- No root-cause analysis
- Alert fatigue from threshold-based rules
- No understanding of organizational context
- Manual correlation between metrics and changes

### Agentic Ops Advisor
✅ **Proactive reasoning** — Automatically correlates telemetry anomalies with change events  
✅ **Root-cause analysis** — Traces symptoms to likely causes using LLM reasoning  
✅ **Change-aware** — "GPU throttling started 2 hours after the CUDA driver update deployed by DevOps Team"  
✅ **Natural language interface** — Operators ask questions in plain English  
✅ **Evidence-based responses** — Always cites telemetry queries and change context  

---

## 3. Beyond Manual Runbooks

### Traditional Runbooks
- Static documentation that becomes stale
- No context about current system state
- Manual execution, no approval workflows
- No version control for decisions
- Tribal knowledge trapped in Slack/email

### Agentic Ops Advisor
✅ **Dynamic reasoning** — Adapts to current telemetry, not static instructions  
✅ **Approval workflows** — Action stub simulates change approval processes  
✅ **Audit trail** — OpenTelemetry traces every agent interaction  
✅ **Work IQ integration** — Surfaces organizational knowledge (decisions, ownership, runbooks) from Microsoft 365  
✅ **Self-improving** — Evaluation framework (`azure-ai-evaluation`) measures quality over time  

---

## 4. Key Differentiators

| Capability | Generic Tools | Agentic Ops Advisor |
|-----------|---------------|---------------------|
| **Telemetry + Intent Fusion** | ❌ Metrics only | ✅ Correlates telemetry with Work IQ change context |
| **Root-Cause Analysis** | ❌ Manual investigation | ✅ Automated causation chains |
| **Governed Actions** | ❌ Untracked changes | ✅ Approval workflows + audit logs |
| **Production-Ready** | ❌ Prototype | ✅ Azure AI Foundry deployment, feature flags, disclaimers |
| **Observability** | ❌ Black box | ✅ OpenTelemetry → Application Insights |
| **Evaluation** | ❌ No quality metrics | ✅ Custom evaluators for accuracy, groundedness, safety |

---

## 5. Agent Persona & Response Quality

### Professional Ops Teammate
- **Short, crisp bullets** — No walls of text
- **Evidence-based** — Always cites tool queries ("Telemetry query showed…", "Change context indicated…")
- **Confidence scoring** — Every response includes `Confidence: High | Med | Low`
- **Next best question** — When confidence is not High, suggests follow-up investigation
- **Light humor** — Gently roasts ambiguous requests and messy data, never people

### Example Response Structure
```
## Summary
- GPU cluster throttled at 15:00 UTC
- Coincides with CUDA driver update deployed at 14:45 UTC

## Evidence
- Telemetry query showed: 43% performance drop on `gpu-pool-west`
- Change context indicated: DevOps Team deployed `cuda-12.3.2` at 14:45 UTC

## Analysis
Driver update introduced kernel compatibility issue with workload scheduler

## Recommended Actions
- Rollback to `cuda-12.2.1` (approval required)
- Notify DevOps Team of regression

## Confidence: High
Strong correlation between deployment and throttling timeline

## Next Best Question
(Only if Confidence is Med/Low)
```

---

## 6. Three-Tool Architecture

### SQL Telemetry Tool
- Queries synthetic infrastructure metrics (GPU, network, cost, incidents)
- Supports SQLite (local dev) and Azure SQL (production)
- Time-series analysis, aggregations, anomaly detection

### Work IQ Context Tool
- Returns synthetic "organizational memory" (change events, decisions, ownership, runbooks)
- Simulates Microsoft 365 Copilot Work IQ integration
- Feature flag: `ENABLE_WORK_IQ=true` (default ON)

### Action Stub Tool
- Proposes infrastructure changes with approval workflows
- **Never modifies external systems** — simulation only
- Logs proposed actions for audit

---

## 7. Governance & Compliance

| Feature | Implementation |
|---------|----------------|
| **Synthetic Data** | All telemetry and change context is synthetic — no real customer data |
| **Content Recording** | `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=false` by default |
| **Feature Flags** | `ENABLE_WORK_IQ`, `ENABLE_MCP` control tool surfaces |
| **Disclaimers** | README and system prompt include Work IQ preview notices |
| **Audit Logs** | OpenTelemetry traces exported to Application Insights |
| **RBAC** | Azure AI Foundry project-level role assignments |

---

## 8. Production Deployment

### Container-Based Architecture
- **Dockerfile** — Single-stage Python 3.11 image
- **Health checks** — `serve.py` exposes `/health` endpoint on port 8088
- **Foundry Responses API v1** — Implements Azure AI Agent Service protocol

### Infrastructure as Code
- **Bicep templates** (`infra/`) provision:
  - Azure AI Foundry Hub + Project
  - Azure OpenAI GPT-4.1 deployment
  - Azure SQL Database (production telemetry store)
  - Application Insights workspace
  - Azure Container Registry
- **`azd up`** — One-command deployment pipeline

### Observability
- **OpenTelemetry SDK** — Automatic trace/span collection
- **Application Insights integration** — Trace correlation, dependency tracking
- **Azure Monitor Workbook** — Pre-built dashboards for agent performance

---

## 9. Evaluation Framework

Unlike generic chatbots, this agent includes **production-grade evaluation**:

- **Test sets** (`eval/test_set.jsonl`) — 20+ real-world scenarios
- **Custom evaluators** — Accuracy, groundedness, safety, latency
- **`azure-ai-evaluation` SDK** — Automated eval runs
- **Regression testing** — `scripts/regression_demo.py` validates tool outputs

---

## 10. Use Cases

### Root-Cause Analysis
**Scenario:** GPU throttling in production cluster  
**Traditional:** Operators manually correlate logs, metrics, change logs  
**Agentic Ops:** Agent correlates telemetry spike with recent driver update, cites Work IQ change event

### Change Impact Assessment
**Scenario:** Planning Kubernetes version upgrade  
**Traditional:** Search Slack/Confluence for past upgrade issues  
**Agentic Ops:** Agent surfaces Work IQ decision history, runbook references, past incident patterns

### Cost Anomaly Detection
**Scenario:** 40% cost increase over 7 days  
**Traditional:** Manually query cloud billing APIs, spreadsheet analysis  
**Agentic Ops:** Agent identifies egress spike, correlates with Work IQ data migration project

---

## 11. Technology Stack

| Layer | Technology |
|-------|-----------|
| **Agent Framework** | Azure AI Agent Service SDK (`azure-ai-projects`) |
| **LLM** | GPT-4.1 (Azure OpenAI) |
| **Database** | SQLite (dev) / Azure SQL (production) |
| **Observability** | OpenTelemetry → Application Insights |
| **Evaluation** | `azure-ai-evaluation` + custom evaluators |
| **IaC** | Bicep templates |
| **CI/CD** | GitHub Actions |
| **Language** | Python 3.11+ |

---

## 12. Not Just a Demo

This is a **reference architecture** for production agentic ops:

✅ Feature flags for controlled rollouts  
✅ Content recording controls for compliance  
✅ Synthetic data for safe demos  
✅ Evaluation framework for quality assurance  
✅ OpenTelemetry for observability  
✅ Bicep IaC for repeatable deployments  
✅ GitHub Actions CI/CD for automation  

---

## Summary

The Agentic Ops Advisor is **not a generic copilot** — it's a governed, production-ready agent that fuses infrastructure telemetry with organizational context. It doesn't just answer questions; it performs root-cause analysis, correlates changes with symptoms, and provides evidence-based recommendations with approval workflows.

**Key Differentiators:**
- Telemetry + Intent fusion (Work IQ integration)
- Root-cause reasoning (not just metric reporting)
- Governed actions (approval workflows, audit logs)
- Production-ready architecture (Azure AI Foundry, OpenTelemetry, Bicep IaC)
- Evaluation framework (custom evaluators, regression testing)

---

## Learn More

- **[Project README](../README.md)** — Full setup and deployment guide
- **[Brochure Site](https://tammym-demos.github.io/Agentic-Ops-Advisor/)** — Interactive demo walkthrough
- **[System Prompt](../agent/system_prompt.md)** — Agent persona and response format
- **[Setup Guide](./sre-agent-setup-guide.md)** — Quick start for Azure deployment
- **[Azure SRE Agent Comparison](./sre-agent-differentiation.md)** — How this agent complements Azure SRE Agent
