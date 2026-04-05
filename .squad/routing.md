# Routing Rules

| Signal | Route To | Notes |
|--------|----------|-------|
| Architecture, scope, code review | Holden | Lead decisions |
| Python, Azure SDK, agent code, tools | Naomi | Backend implementation |
| Bicep, deployment, infra, Azure resources | Amos | DevOps and infrastructure |
| Tests, eval, quality, pytest | Alex | Testing and evaluation |
| Documentation, project tracking, user stories, definition of success, GitHub Projects | Drummer | PM processes and project ops |
| Logs, decisions, memory | Scribe | Silent — never speaks to user |
| Work queue, backlog, monitoring | Ralph | Continuous work loop |
| Planning, priorities, demo, customer, final decisions | Tammy | Human — PM & Demo Lead, present work and wait for input |
| Cloud code fixes, single-file changes, issue-driven code work | @copilot | Coding Agent — async via issue assignment, creates PRs |

## Standing Directives

- **All feature planning MUST include Drummer.** Before any implementation work begins,
  Drummer writes user stories with acceptance criteria and a definition of success.
  The PM agent is always part of the evaluation team alongside testers and leads.
