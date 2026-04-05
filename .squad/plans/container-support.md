# Plan: Add Container Support to Agentic Ops Advisor

## Problem Statement

The Agentic Ops Advisor currently deploys as a **prompt agent** to Azure AI Foundry Agent Service — it registers the agent definition (model + system prompt) via the SDK but **does not deploy the custom Python tool code** (`tools/sql_telemetry.py`, `tools/work_context_stub.py`, `tools/action_stub.py`). This means the three custom tool surfaces only work when running locally. There is no `Dockerfile`, no `agent.yaml`, and no container build/push step in CI/CD.

The project already provisions an Azure Container Registry (ACR) via `infra/modules/aifoundry.bicep` (line 59) and registers the `Microsoft.ContainerRegistry` provider in `infra/deploy.sh` (line 100), but neither is used.

## Proposed Approach

Add full **Foundry container agent** support: package the agent + tools + dependencies into a Docker image, push to the existing ACR, and deploy as a container-hosted agent on Azure AI Foundry Agent Service. Update documentation, landing page, and create a PM feature spec.

---

## Todos

### 1. `dockerfile` — Create Dockerfile

Create a production `Dockerfile` at the repo root:

- Base image: `python:3.11-slim`
- Install system deps for `pyodbc` (ODBC drivers)
- Copy `agent/`, `tools/`, `data/`, `scripts/`, `eval/`, `requirements.txt`, `pyproject.toml`
- Install Python dependencies (runtime only, no dev deps)
- Set environment variable defaults (`DB_MODE=sqlite`, `ENABLE_WORK_IQ=true`, `ENABLE_MCP=false`)
- Seed the local SQLite database at build time via `scripts/setup_local_db.py`
- Expose a health-check endpoint (or use the Foundry agent entrypoint)
- Entrypoint: `python scripts/run_local.py` (or a new `scripts/serve.py` if needed)
- Add `.dockerignore` to exclude `.git`, `.venv`, `__pycache__`, `.env`, etc.

### 2. `agent-yaml` — Create agent.yaml Manifest

Create `agent.yaml` at the repo root — the Foundry container agent manifest:

- Agent name: `agentic-ops-advisor`
- Model: `gpt-4.1`
- System prompt reference: `agent/system_prompt.md`
- Tool definitions referencing the three tool surfaces
- Container configuration (image reference, port, health check)
- Environment variable declarations

### 3. `dockerignore` — Create .dockerignore

Exclude unnecessary files from the Docker build context:

- `.git/`, `.github/`, `.venv/`, `__pycache__/`, `.env`, `.env.*`
- `*.db`, `*.sqlite`, `*.sqlite3` (rebuilt at build time)
- `docs/`, `monitoring/`, `infra/`, `.squad/`
- `htmlcov/`, `.coverage`, `.pytest_cache/`
- `node_modules/`, `*.log`, `*.tmp`

### 4. `ci-cd-update` — Update deploy.yml Workflow

Update `.github/workflows/deploy.yml` to add container build/push/deploy steps:

- **New Step: Docker Build** — build the image tagged with `${{ github.sha }}` and `latest`
- **New Step: ACR Push** — authenticate to ACR using Azure credentials, push the tagged image
- **New Step: Deploy Container Agent** — replace the current prompt-agent upsert (Step 5) with a Foundry container agent deployment using the pushed image
- Keep the existing smoke test (Step 6) — it should still work against the deployed container agent
- Add ACR name as an output from Bicep (already exists in aifoundry.bicep but not exposed via main.bicep outputs)

Depends on: `dockerfile`, `agent-yaml`, `dockerignore`, `bicep-acr-output`

### 5. `bicep-acr-output` — Expose ACR Name from Bicep

Update `infra/modules/aifoundry.bicep` and `infra/main.bicep` to:

- Add an output for the ACR login server URL (e.g., `crhubagentopsprod.azurecr.io`)
- Surface it through `main.bicep` outputs so `deploy.sh` can capture it
- Update `deploy.sh` to print the ACR login server in the `.env` snippet

### 6. `readme-update` — Update README.md

Update the README to document container deployment:

- Add "Container Deployment" to the Table of Contents
- Update the **Tech Stack** table to include Docker / ACR
- Update **Section 6: Deploying to Azure** with container build/push steps
- Add a new section explaining the Dockerfile, agent.yaml, and local Docker testing
- Update the architecture diagram (mermaid) to show the container layer
- Update Prerequisites to mention Docker

### 7. `landing-page-update` — Update docs/index.html

Update the GitHub Pages landing page:

- Update the "Production Deployment" feature card to mention container deployment
- Add Docker / ACR to the tech stack badges and table
- Update the architecture SVG diagram to show the container runtime layer
- Consider adding a stat to the stats strip (e.g., "Container-Ready" or update existing)

### 8. `feature-spec` — Create PM Feature Spec

Create `docs/specs/container-deployment.md` — a PM feature spec document:

- **Problem Statement**: custom tool code not deployed with the prompt agent
- **User Stories**: as an ops engineer deploying to production, I want the agent and its tools packaged as a container so the deployment is reproducible and complete
- **Requirements**: functional (Dockerfile, ACR push, Foundry container agent) + non-functional (image size < 500MB, build time < 5min, health check)
- **Success Criteria**: CI/CD builds and pushes container; Foundry runs the agent with all tools available; smoke test passes
- **Out of Scope**: ACA deployment, Kubernetes, multi-region
- **Dependencies**: existing ACR in Bicep, Foundry container agent GA
- **Risks**: Foundry container agent API may change (currently in preview)

### 9. `gitignore-update` — Update .gitignore

Add Docker-related entries to `.gitignore`:

- Docker build cache artifacts
- Any local Docker Compose override files

### 10. `env-example-update` — Update .env.example

Add container-related environment variables:

- `ACR_LOGIN_SERVER` — Azure Container Registry login URL
- `CONTAINER_IMAGE_TAG` — image tag (defaults to `latest`)

---

## Dependencies

```
dockerfile ──────────┐
agent-yaml ──────────┤
dockerignore ────────┼──► ci-cd-update
bicep-acr-output ────┘
                          ▲
                          │ (must validate after CI changes)
                          │
readme-update ────────── (independent, can parallel)
landing-page-update ──── (independent, can parallel)
feature-spec ─────────── (independent, can parallel)
gitignore-update ──────── (independent, can parallel)
env-example-update ─────── (independent, can parallel)
```

## Notes & Considerations

- The existing ACR in `aifoundry.bicep` uses the `Basic` SKU — sufficient for this use case
- The `pyodbc` dependency requires ODBC driver installation in the Docker image (Microsoft's `msodbcsql18`)
- The current `deploy.yml` Step 5 does a prompt-agent upsert via Python SDK — this will be replaced with container agent deployment
- The Foundry container agent model is the recommended approach per Azure AI Foundry documentation for agents with custom tool code
- All data remains synthetic — the Dockerfile seeds the SQLite DB at build time for portability
- The `.env` file is never baked into the image — all config comes from environment variables at runtime
