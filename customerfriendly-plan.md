

## 📌 Coding Agent Instructions — “Agentic Ops Advisor” 

### 0) Mission (what you are building)

Build an end‑to‑end demo called **Agentic Ops Advisor**: a **governed, production‑style agent** that performs **root‑cause + change‑context reasoning** over **infrastructure telemetry** and **operator intent**—aligned to **customer's agentic operations narrative** (GreenLake Intelligence / agent mesh / MCP). Our customer emphasizes **agentic AIOps** and explicitly mentions agents collaborating via **Model Context Protocol (MCP)** for context and action. [\[\[EcoTalks\]...sformation \| Teams\]](https://teams.microsoft.com/l/message/19:meeting_ZjU4YjY5YWEtYzc4OS00NmUzLWE3NjMtZTM3NTYxMDE2ZTVl@thread.v2/1743696119673?context=%7B%22contextType%22:%22chat%22%7D), [\[Weekly AIC...ft Meeting \| Meeting\]](https://teams.microsoft.com/l/meeting/details?eventId=AAMkADE4ZjU4ZGI4LTE5MTgtNDRiNi04OWJlLTdhMTc1ZDNlOTQzMwFRAAgI3n43_Q8AAEYAAAAAuglB6H9lUECIrhAXEvLkygcAPCSuBgfwUUyoC1w4TJgw-QAAAAABDQAAPCSuBgfwUUyoC1w4TJgw-QAIeSFEbgAAEA%3d%3d)

The demo must show:

1.  **Build** with GitHub Copilot (you are the coding agent)
2.  **Deploy** to **Azure AI Foundry Agent Service**
3.  **Evaluate** (offline + continuous) and show **regression detection**
4.  **Observe** with tracing + monitoring dashboards/metrics
5.  **Operate** safely (guardrails, human-in-loop option, safe synthetic data)

Foundry provides **tracing, logging, monitoring, evaluation, experimentation** for agents and supports **MCP tools** plus multiple frameworks. [\[Deep Dive...undry L300 \| PowerPoint\]](https://microsofteur.sharepoint.com/teams/InnovationMicrosoftSpain/_layouts/15/Doc.aspx?sourcedoc=%7B394E5207-A336-4FB7-A83A-82AA6F37A7F2%7D&file=Deep%20Dive%20into%20Agent%20Stack%20in%20Azure%20AI%20Foundry%20L300.PPTX&action=edit&mobileredirect=true&DefaultItemOpen=1), [\[Azure AI F...y Overview \| PowerPoint\]](https://microsoftapc.sharepoint.com/teams/MDAIDCExtendedTeam/_layouts/15/Doc.aspx?sourcedoc=%7BEF30270D-3687-40B2-A405-79C69738F097%7D&file=Azure%20AI%20Foundry%20Overview.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1), [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)

***

### 1) Non‑negotiable Constraints (customer safety)

*   **NO Microsoft internal data** in the demo. All “work context” must be **synthetic**.
*   **Work IQ is shown as a pattern**, not a live tenant integration (Work IQ is **public preview**; APIs/features can change). [\[Azure AI F...nt Factory \| PowerPoint\]](https://microsofteur-my.sharepoint.com/personal/mpoeckl_microsoft_com/_layouts/15/Doc.aspx?sourcedoc=%7B5DB64589-5031-421F-9FCE-2D9FC10FBB22%7D&file=Azure%20AI%20Foundry%20The%20Agent%20Factory.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1), [\[agent-ops-overview 2 \| HTML\]](https://microsoft-my.sharepoint.com/personal/tmcclell_microsoft_com/Documents/Microsoft%20Teams%20Chat%20Files/agent-ops-overview%202.html?web=1)
*   If we mention Work IQ, we must state that Work IQ requires **Microsoft 365 Copilot licensing** and admin consent for tenant access; for this demo we simulate it. [\[fabric_sql...r_in_a_day \| PDF\]](https://microsoft.sharepoint.com/teams/DataAIGBBCommunity/Shared%20Documents/FY25/FabCon%20Mini%20Airlift%20-%20March%202025/FabCon%20Resources/fabric_sql_database_data_engineer_in_a_day.pdf?web=1), [\[Azure AI F...nt Factory \| PowerPoint\]](https://microsofteur-my.sharepoint.com/personal/mpoeckl_microsoft_com/_layouts/15/Doc.aspx?sourcedoc=%7B5DB64589-5031-421F-9FCE-2D9FC10FBB22%7D&file=Azure%20AI%20Foundry%20The%20Agent%20Factory.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)
*   Align language with: **agentic ops**, **hybrid**, **governance**, **telemetry + intent**, **self‑driving operations**. Messaging highlights “self‑driving” operations and agentic AI compatible with a hybrid ops framing. [\[Following:...(Optional) \| Meeting\]](https://teams.microsoft.com/l/meeting/details?eventId=AAMkADE4ZjU4ZGI4LTE5MTgtNDRiNi04OWJlLTdhMTc1ZDNlOTQzMwFRAAgI3ooBdUFAAEYAAAAAuglB6H9lUECIrhAXEvLkygcAPCSuBgfwUUyoC1w4TJgw-QAAAAABDQAAPCSuBgfwUUyoC1w4TJgw-QAFkPuoMgAAEA%3d%3d), [\[\[EcoTalks\]...sformation \| Teams\]](https://teams.microsoft.com/l/message/19:meeting_ZjU4YjY5YWEtYzc4OS00NmUzLWE3NjMtZTM3NTYxMDE2ZTVl@thread.v2/1743696119673?context=%7B%22contextType%22:%22chat%22%7D)

***

### 2) Demo Narrative (what the demo should feel like)

**User story:** “I’m an ops engineer running AI factory workloads. Something regressed. I need to know what happened, why, and what to do next—fast, with evidence.”

**Core queries the agent must handle (examples):**

*   “Why did GPU utilization drop in the last 24h?”
*   “What changed right before the latency spike?”
*   “Is this a known issue or a change‑caused incident?”
*   “What’s the safest remediation plan? Provide options and tradeoffs.”

**Agent outputs must include:**

*   A concise **diagnosis**
*   Evidence links to telemetry queries (SQL) + synthetic “change context”
*   A recommended action plan with **risk level**
*   Optional: a “human approval gate” before executing any action (even if actions are stubbed)

***

### 3) Architecture Requirements (minimum viable components)

You will implement the agent with **three tool surfaces**:

#### A) Telemetry tool (Azure SQL)

A tool the agent can call to query telemetry and produce aggregates:

*   Tables (synthetic):
    *   `telemetry_gpu(ts, cluster, node, utilization_pct, mem_pct)`
    *   `telemetry_net(ts, site, latency_ms, loss_pct, throughput_gbps)`
    *   `telemetry_cost(ts, cluster, cost_usd, token_cost_usd)`
    *   `incidents(ts, service, symptom, severity, status)`
*   Provide at least 30 days of synthetic data with a few planted anomalies.

#### B) “Work IQ‑style Context” tool (simulated MCP)

A local MCP server (or in‑repo stub) returning **synthetic** “work context” objects:

*   `change_events`: approvals, policy changes, rollout windows
*   `decisions`: “AI Factory Planning” meeting outcomes
*   `ownership`: who owns a service/team (synthetic)
*   `runbooks`: relevant remediation runbook snippets (synthetic)

This tool must be described as **“Work IQ pattern simulation”** (do not claim it is live Work IQ). Work IQ is a CLI/MCP path and is **public preview**. [\[Azure AI F...nt Factory \| PowerPoint\]](https://microsofteur-my.sharepoint.com/personal/mpoeckl_microsoft_com/_layouts/15/Doc.aspx?sourcedoc=%7B5DB64589-5031-421F-9FCE-2D9FC10FBB22%7D&file=Azure%20AI%20Foundry%20The%20Agent%20Factory.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1), [\[agent-ops-overview 2 \| HTML\]](https://microsoft-my.sharepoint.com/personal/tmcclell_microsoft_com/Documents/Microsoft%20Teams%20Chat%20Files/agent-ops-overview%202.html?web=1)

#### C) Optional action tool (safe)

A stub action tool that *does not* change external systems:

*   `propose_change(plan)` → returns a change request payload
*   `request_approval(payload)` → returns “pending/approved” (simulated)

***

### 4) Foundry Operational Requirements (Evaluation + Monitoring + Deployment)

Your solution must be deployable to **Azure AI Foundry Agent Service** and demonstrate production readiness features:

#### Observability & Tracing

*   Instrument the agent with **OpenTelemetry traces/spans**.
*   Ensure spans exist for:
    *   agent invocation
    *   tool calls
    *   LLM calls
*   Foundry tracing captures stages and includes conventions like `invoke_agent`, `execute_tool`, `llm_call`. [\[Azure AI F...y Overview \| PowerPoint\]](https://microsoftapc.sharepoint.com/teams/MDAIDCExtendedTeam/_layouts/15/Doc.aspx?sourcedoc=%7BEF30270D-3687-40B2-A405-79C69738F097%7D&file=Azure%20AI%20Foundry%20Overview.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1), [\[Deep Dive...undry L300 \| PowerPoint\]](https://microsofteur.sharepoint.com/teams/InnovationMicrosoftSpain/_layouts/15/Doc.aspx?sourcedoc=%7B394E5207-A336-4FB7-A83A-82AA6F37A7F2%7D&file=Deep%20Dive%20into%20Agent%20Stack%20in%20Azure%20AI%20Foundry%20L300.PPTX&action=edit&mobileredirect=true&DefaultItemOpen=1)
*   Support exporting traces to **Application Insights/Azure Monitor** (or OTLP destination). [\[Azure AI F...y Overview \| PowerPoint\]](https://microsoftapc.sharepoint.com/teams/MDAIDCExtendedTeam/_layouts/15/Doc.aspx?sourcedoc=%7BEF30270D-3687-40B2-A405-79C69738F097%7D&file=Azure%20AI%20Foundry%20Overview.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1), [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)
*   Include an environment flag option for content recording: `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true` (document it clearly and default it OFF for demo safety). [\[Azure AI F...y Overview \| PowerPoint\]](https://microsoftapc.sharepoint.com/teams/MDAIDCExtendedTeam/_layouts/15/Doc.aspx?sourcedoc=%7BEF30270D-3687-40B2-A405-79C69738F097%7D&file=Azure%20AI%20Foundry%20Overview.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)

#### Evaluation (offline + continuous)

Implement:

1.  **Offline batch evaluation** on a fixed test set
2.  **Continuous evaluation** that can run after deployment (or on sample “production” conversations)

Foundry supports built‑in/custom evaluators and continuous evaluation/alerting for quality, safety, performance; guidance recommends baselines and evaluation frameworks integrated into CI/CD. [\[What’s New...ve set of  \| Viva Engage\]](https://engage.cloud.microsoft/main/threads/eyJfdHlwZSI6IlRocmVhZCIsImlkIjoiMzc3MDI3MjE1MjEzMzYzMiJ9), [\[Process to...soft Learn \| Learn.Microsoft.com\]](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai-agents/build-secure-process), [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)

**Minimum eval metrics:**

*   “Correctness” (did it identify the right likely cause given planted anomalies?)
*   “Evidence quality” (did it cite telemetry + change context?)
*   “Safety” (no sensitive data leakage; no unsafe actions)
*   “Groundedness/relevance” (response matches provided tool outputs)

**CI/CD requirement:** integrate evaluations into a pipeline (GitHub Actions is fine) to catch regressions before deployment; Microsoft guidance explicitly calls for integrating evals into CI/CD. [\[Process to...soft Learn \| Learn.Microsoft.com\]](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai-agents/build-secure-process), [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)

#### Monitoring

*   Provide a simple monitoring view showing:
    *   request count / throughput
    *   latency
    *   tool failure rate
    *   “quality score trend” from evaluations (even if mocked)
        Foundry monitoring dashboards and evaluation comparison are part of the recommended demo flow. [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1), [\[What’s New...ve set of  \| Viva Engage\]](https://engage.cloud.microsoft/main/threads/eyJfdHlwZSI6IlRocmVhZCIsImlkIjoiMzc3MDI3MjE1MjEzMzYzMiJ9)

***

### 5) Required Demo Moment: “Regression + recovery”

You must implement a scripted demo step where:

1.  Baseline agent performs well (passes evals)
2.  A change is introduced that breaks a tool call or worsens answers
3.  CI/CD evaluation detects regression
4.  Observability (trace) shows where it failed
5.  A fix is applied and eval scores recover

This exact pattern (“push change disables tool call → compare evaluation results → show monitoring”) is called out in BRK168 - AI and Agent Observability in Azure AI Foundry and Azure Monitor\_.pptx. [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)

***

### 6) Repo Deliverables (what files to create)

Create the following structure:

*   `README.md`
    *   How to run locally
    *   How to run evaluations
    *   How to deploy to Foundry
    *   “Synthetic data only” disclaimer
*   `agent/`
    *   agent definition (instructions/system prompt)
    *   tool schemas
    *   orchestration code (framework of choice)
*   `tools/`
    *   `sql_telemetry_tool.*`
    *   `work_context_mcp_stub.*`
    *   `action_stub_tool.*`
*   `data/`
    *   synthetic seed generator + generated dataset (or scripts)
*   `eval/`
    *   `testset.jsonl` (prompts + expected signals)
    *   evaluator scripts
    *   baseline results snapshot
*   `.github/workflows/`
    *   `ci-eval.yml` (run eval on PR)
    *   optional `deploy.yml` (deploy on main)

Design the operational narrative using guidance patterns similar to agentic-ops.html and agent-ops-overview\.html (build → deploy → evaluate → monitor). [\[agentic-ops \| HTML\]](https://microsoft-my.sharepoint.com/personal/tmcclell_microsoft_com/Documents/Microsoft%20Teams%20Chat%20Files/agentic-ops.html?web=1), [\[agent-ops-overview \| HTML\]](https://microsoft-my.sharepoint.com/personal/tmcclell_microsoft_com/Documents/Microsoft%20Teams%20Chat%20Files/agent-ops-overview.html?web=1)

***

### 7) Agent Instruction Requirements (tone + “Tammy humor”)

Agent persona: **professional ops teammate** with light humor. Rules:

*   Do not roast people; you may roast ambiguous requests and messy data gently.
*   Use short, crisp bullets.
*   Always include a “Confidence” line (High/Med/Low) and “Next best question” if confidence is not High.
*   Always cite evidence from tools used (“Telemetry query showed…”, “Change context indicated…”).

Include a one‑liner occasionally, e.g.:

*   “This incident is giving… ‘configuration drift’.”

***

### 8) Definition of Done (acceptance criteria)

You are done when all below are true:

1.  **Local run**: agent answers the 4 core queries using telemetry + simulated Work IQ context.
2.  **Tooling**: agent calls SQL tool and MCP context tool at least once per scenario.
3.  **Evals**: offline evaluation runs and produces a report; CI runs eval on PR. [\[Process to...soft Learn \| Learn.Microsoft.com\]](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai-agents/build-secure-process), [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)
4.  **Tracing**: traces show agent → LLM → tool calls; documented how to view traces (Foundry portal or App Insights). [\[Azure AI F...y Overview \| PowerPoint\]](https://microsoftapc.sharepoint.com/teams/MDAIDCExtendedTeam/_layouts/15/Doc.aspx?sourcedoc=%7BEF30270D-3687-40B2-A405-79C69738F097%7D&file=Azure%20AI%20Foundry%20Overview.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1), [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)
5.  **Deployment**: deployable to Foundry Agent Service, with a documented configuration path (env vars, endpoints, etc.). Foundry Agent Service is described as GA in Foundry materials. [\[Deep Dive...undry L300 \| PowerPoint\]](https://microsofteur.sharepoint.com/teams/InnovationMicrosoftSpain/_layouts/15/Doc.aspx?sourcedoc=%7B394E5207-A336-4FB7-A83A-82AA6F37A7F2%7D&file=Deep%20Dive%20into%20Agent%20Stack%20in%20Azure%20AI%20Foundry%20L300.PPTX&action=edit&mobileredirect=true&DefaultItemOpen=1), [\[What’s New...ve set of  \| Viva Engage\]](https://engage.cloud.microsoft/main/threads/eyJfdHlwZSI6IlRocmVhZCIsImlkIjoiMzc3MDI3MjE1MjEzMzYzMiJ9)
6.  **Regression demo**: scripted regression/fix sequence works and is easy to run. [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)
7.  **No real data**: repository contains only synthetic data and clear disclaimers.

***

### 9) Notes on “Work IQ” (how to reference it correctly)

In all documentation and narration:

*   Say: “We’re simulating Work IQ outputs in this demo.”
*   Add: “Work IQ is in public preview and requires Microsoft 365 Copilot licensing + admin consent for tenant data access.” [\[Azure AI F...nt Factory \| PowerPoint\]](https://microsofteur-my.sharepoint.com/personal/mpoeckl_microsoft_com/_layouts/15/Doc.aspx?sourcedoc=%7B5DB64589-5031-421F-9FCE-2D9FC10FBB22%7D&file=Azure%20AI%20Foundry%20The%20Agent%20Factory.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1), [\[fabric_sql...r_in_a_day \| PDF\]](https://microsoft.sharepoint.com/teams/DataAIGBBCommunity/Shared%20Documents/FY25/FabCon%20Mini%20Airlift%20-%20March%202025/FabCon%20Resources/fabric_sql_database_data_engineer_in_a_day.pdf?web=1)
*   Do **not** claim: “We integrated live Work IQ.”

***

## ✅ Optional: Demo Script Outline (for README)

Use this as the canonical walkthrough:

1.  **Baseline**: Ask “Why did GPU utilization drop?” → agent correlates telemetry + change decision context.
2.  **Evidence**: Show trace waterfall (agent → tool → LLM).
3.  **Regression**: Toggle the broken tool schema or fail the context tool.
4.  **CI eval fails**: show eval report deltas.
5.  **Fix**: revert tool schema or patch prompt/tool call.
6.  **Re-run eval**: scores recover.
7.  **Monitoring**: show request/latency/quality trend line.

This aligns with the customer demo pattern in BRK168 - AI and Agent Observability in Azure AI Foundry and Azure Monitor\_.pptx. [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)

***

## 🔗 Reference Assets you can quote inside the repo (internal)

If helpful, you may point the coding agent to these conceptual guides:

*   Azure AI Foundry Overview\.pptx (agent components + OTel tracing + env var) [\[Azure AI F...y Overview \| PowerPoint\]](https://microsoftapc.sharepoint.com/teams/MDAIDCExtendedTeam/_layouts/15/Doc.aspx?sourcedoc=%7BEF30270D-3687-40B2-A405-79C69738F097%7D&file=Azure%20AI%20Foundry%20Overview.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)
*   Deep Dive into Agent Stack in Azure AI Foundry L300.PPTX (Agent Service + MCP tools + evaluation/monitoring) [\[Deep Dive...undry L300 \| PowerPoint\]](https://microsofteur.sharepoint.com/teams/InnovationMicrosoftSpain/_layouts/15/Doc.aspx?sourcedoc=%7B394E5207-A336-4FB7-A83A-82AA6F37A7F2%7D&file=Deep%20Dive%20into%20Agent%20Stack%20in%20Azure%20AI%20Foundry%20L300.PPTX&action=edit&mobileredirect=true&DefaultItemOpen=1)
*   BRK168 - AI and Agent Observability in Azure AI Foundry and Azure Monitor\_.pptx (demo pattern for regression/evals) [\[BRK168 - A...e Monitor_ \| PowerPoint\]](https://microsoft.sharepoint.com/teams/MCAPSAcademyCDMO/_layouts/15/Doc.aspx?sourcedoc=%7B4158B983-3BA8-4492-8BCF-6333F281A357%7D&file=BRK168%20-%20AI%20and%20Agent%20Observability%20in%20Azure%20AI%20Foundry%20and%20Azure%20Monitor_.pptx&action=edit&mobileredirect=true&DefaultItemOpen=1)
*   agent-ops-overview\.html and agentic-ops.html (end‑to‑end ops narrative) [\[agent-ops-overview \| HTML\]](https://microsoft-my.sharepoint.com/personal/tmcclell_microsoft_com/Documents/Microsoft%20Teams%20Chat%20Files/agent-ops-overview.html?web=1), [\[agentic-ops \| HTML\]](https://microsoft-my.sharepoint.com/personal/tmcclell_microsoft_com/Documents/Microsoft%20Teams%20Chat%20Files/agentic-ops.html?web=1)

***
