# Squad Team

> Agentic Ops Advisor — governed AI agent for infrastructure telemetry reasoning

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Squad | Coordinator | Routes work, enforces handoffs and reviewer gates. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| Holden | Lead | [charter](agents/holden/charter.md) | 🟢 Active |
| Naomi | Backend Dev | [charter](agents/naomi/charter.md) | 🟢 Active |
| Amos | DevOps | [charter](agents/amos/charter.md) | 🟢 Active |
| Alex | Tester | [charter](agents/alex/charter.md) | 🟢 Active |
| Drummer | Program Manager | [charter](agents/drummer/charter.md) | 🟢 Active |
| Scribe | Session Logger | [charter](agents/scribe/charter.md) | 🟢 Active |
| Ralph | Work Monitor | — | 🔄 Monitor |
| Tammy | Human (PM & Demo Lead) | — | 👤 Human |
| @copilot | Coding Agent | [instructions](../../.github/copilot-instructions.md) | 🤖 Cloud |

<!-- copilot-auto-assign: true -->

### @copilot Capability Profile

| Category | Fit | Notes |
|----------|-----|-------|
| Single-file code fixes | 🟢 | Ideal — scoped, testable |
| Multi-file refactors | 🟢 | Good with clear instructions |
| New feature from issue | 🟡 | Works if well-specified |
| Bicep/IaC changes | 🟡 | Can edit templates, can't deploy |
| Azure CLI operations | 🔴 | No credentials in cloud runner |
| Database operations | 🔴 | No DB access in cloud runner |
| Test execution + reporting | 🟡 | Can run pytest if setup-steps configured |

## Project Context

- **Project:** Agentic Ops Advisor
- **Stack:** Python 3.11, Azure AI Agent Service SDK, GPT-4.1, Bicep, OpenTelemetry
- **Repo:** tammym-demos/Agentic-Ops-Advisor
- **User:** Tammy
- **Created:** 2026-04-04

## Issue Source

- **Repository:** tammym-demos/Agentic-Ops-Advisor
- **Connected:** 2026-04-04
