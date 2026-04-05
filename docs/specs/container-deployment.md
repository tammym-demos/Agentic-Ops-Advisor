# Feature Spec: Container Deployment for Agentic Ops Advisor

## Overview

This feature transitions the Agentic Ops Advisor from a prompt-only Foundry agent to a fully containerized deployment. By packaging the agent definition, all three custom Python tool surfaces, and a pre-seeded SQLite database into a single Docker image, we close the gap between local development and production — ensuring that the deployed agent can execute its tools end-to-end.

## Problem Statement

The Agentic Ops Advisor currently deploys as a "prompt agent" — registering only the agent definition (model + system prompt) with Azure AI Foundry Agent Service. The three custom Python tool surfaces (SQL Telemetry, Work IQ Context Stub, Action Stub) are NOT deployed, meaning they only work locally. This creates a gap between the local development experience and production: the deployed agent cannot execute its tools.

Additionally, the project provisions an Azure Container Registry (ACR) via Bicep but never uses it. Containerization would provide reproducible, portable deployments and unlock Foundry's container agent model.

## User Stories

1. **As an ops engineer deploying to production**, I want the agent and all its custom tools packaged into a single container image so that production behavior matches local development.
2. **As a DevOps engineer**, I want the CI/CD pipeline to automatically build, push, and deploy the container so deployments are consistent and auditable.
3. **As a platform engineer**, I want the agent container to include a health check endpoint so the orchestration layer can verify liveness.
4. **As a demo presenter**, I want to show that the agent is deployed as a container to demonstrate production-readiness and alignment with enterprise container strategies.

## Requirements

### Functional Requirements

| ID   | Requirement |
|------|-------------|
| FR-1 | Dockerfile packages Python 3.11 runtime, all agent code, tools, and dependencies |
| FR-2 | Docker image includes ODBC drivers for Azure SQL connectivity |
| FR-3 | SQLite database is seeded at build time with synthetic telemetry data |
| FR-4 | `agent.yaml` manifest defines the Foundry container agent configuration |
| FR-5 | CI/CD pipeline builds Docker image, pushes to ACR, deploys as Foundry container agent |
| FR-6 | Bicep outputs include ACR login server URL |
| FR-7 | All three tool surfaces (`query_telemetry`, `get_work_context`, `propose_change`/`request_approval`) function in the container |

### Non-Functional Requirements

| ID    | Requirement |
|-------|-------------|
| NFR-1 | Docker image size < 500 MB (compressed) |
| NFR-2 | Docker build time < 5 minutes in CI |
| NFR-3 | Container starts and is healthy within 30 seconds |
| NFR-4 | No secrets baked into the image — all configuration via environment variables at runtime |
| NFR-5 | Container runs as non-root user |
| NFR-6 | Health check endpoint responds at `/health` on port 8080 |

## Success Criteria

- [ ] `docker build` succeeds locally and produces a working image
- [ ] CI/CD pipeline builds, pushes to ACR, and deploys without errors
- [ ] Deployed container agent passes the existing smoke test (GPU utilization query)
- [ ] All four custom evaluators (correctness, evidence_quality, safety, groundedness) maintain baseline scores
- [ ] Image size is under 500 MB compressed
- [ ] Container runs as non-root

## Architecture

```
Developer → git push → GitHub Actions CI/CD
                              │
                              ├─ docker build + tag
                              ├─ docker push → ACR (crhubagentopsprod.azurecr.io)
                              └─ az ai agent deploy → Foundry Agent Service
                                                          │
                                                          ├─ Container: agentic-ops-advisor
                                                          │   ├─ agent/ (agent definition)
                                                          │   ├─ tools/ (3 tool surfaces)
                                                          │   └─ data/ (seeded SQLite)
                                                          │
                                                          └─ GPT-4.1 (Azure OpenAI)
```

## Out of Scope

- Azure Container Apps (ACA) deployment
- Kubernetes / AKS deployment
- Multi-region container replication
- Custom base image registry
- GPU-enabled container runtime

## Dependencies

- **Azure Container Registry** — already provisioned via Bicep (`infra/modules/aifoundry.bicep`)
- **Azure AI Foundry container agent support** (preview)
- **Microsoft ODBC Driver 18 for SQL Server** — installed in Dockerfile

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Foundry container agent API changes (preview) | Medium | High | Pin SDK version; abstract deployment behind a script |
| Docker image bloat from ODBC drivers | Low | Medium | Use slim base image; audit layer sizes |
| Secrets accidentally baked into image | Low | High | `.dockerignore` excludes `.env`; CI validates no secrets |
| ACR Basic SKU throttling under load | Low | Low | Upgrade to Standard if needed |

## Timeline

This feature is planned for the current sprint. No time estimates provided.
