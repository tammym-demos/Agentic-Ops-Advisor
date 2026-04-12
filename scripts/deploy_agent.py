#!/usr/bin/env python3
"""Register a hosted agent version with Azure AI Foundry Agent Service.

Called by CI/CD after Docker image is built and pushed to ACR.
Uses the Azure AI Projects SDK to create a new hosted agent version.

Required environment variables:
    AZURE_AI_AGENTS_ENDPOINT  — Foundry Agent Service endpoint
    CONTAINER_IMAGE           — Full ACR image ref (e.g. crhubagentopsprod.azurecr.io/agentic-ops-advisor:abc1234)

Optional:
    AZURE_OPENAI_ENDPOINT     — Injected into container env
    AZURE_OPENAI_DEPLOYMENT   — Model deployment name (default: gpt-4.1)
    AZURE_OPENAI_API_KEY      — Injected into container env
    ENABLE_WORK_IQ            — Feature flag (default: true)
    AZURE_CLIENT_ID           — Managed identity client ID

NOTE: All data is synthetic. This is a demo deployment.
"""

from __future__ import annotations

import os
import sys
import time


def main() -> None:
    endpoint = os.environ.get("AZURE_AI_AGENTS_ENDPOINT", "")
    container_image = os.environ.get("CONTAINER_IMAGE", "")

    if not endpoint:
        print("❌ AZURE_AI_AGENTS_ENDPOINT is required")
        sys.exit(1)
    if not container_image:
        print("❌ CONTAINER_IMAGE is required")
        sys.exit(1)

    deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")

    print("🔧 Configuration:")
    print(f"   Endpoint: {endpoint}")
    print(f"   Model deployment: {deployment_name}")
    print(f"   Container image: {container_image}")

    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import HostedAgentDefinition, ProtocolVersionRecord
    from azure.identity import DefaultAzureCredential

    client = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )

    # Hosted agent definition — container handles its own LLM calls,
    # tool dispatch, and system prompt via POST /responses on port 8088.
    env_vars = {}
    for key in [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_KEY",
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED",
        "DB_MODE",
        "ENABLE_WORK_IQ",
        "ENABLE_MCP",
        "AZURE_CLIENT_ID",
    ]:
        val = os.environ.get(key, "")
        if val:
            env_vars[key] = val
    
    # CRITICAL: Set SERVE_PORT=8088 to match Foundry hosting adapter default.
    # Foundry's sidecar occupies port 8080, so the container must listen on 8088.
    # HostedAgentDefinition has no target_port parameter, so we rely on the container
    # reading SERVE_PORT env var.
    env_vars["SERVE_PORT"] = "8088"

    # Provide project endpoint for FoundryCBAgent adapter tracing/tool runtime.
    project_conn = os.environ.get("AZURE_AI_PROJECT_CONNECTION_STRING", "")
    if project_conn:
        # Derive endpoint from connection string: <host>/api/projects/<project>
        parts = project_conn.split(";")
        host = parts[0] if parts else ""
        proj = parts[1] if len(parts) > 1 else ""
        if host and proj:
            env_vars["AZURE_AI_PROJECT_ENDPOINT"] = f"https://{host}/api/projects/{proj}"

    agent_definition = HostedAgentDefinition(
        kind="hosted",
        container_protocol_versions=[
            ProtocolVersionRecord(protocol="responses", version="v1"),
        ],
        cpu="2",
        memory="4Gi",
        image=container_image,
        environment_variables=env_vars,
    )

    agent_name = "agentic-ops-advisor"
    agent_description = (
        "Agentic Ops Advisor — hosted agent for infrastructure "
        "telemetry & change-context reasoning"
    )

    # Retry with backoff for RBAC propagation delays
    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(
                f"Creating hosted agent version "
                f"(attempt {attempt + 1}/{max_retries})..."
            )
            agent_version = client.agents.create_version(
                agent_name=agent_name,
                definition=agent_definition,
                description=agent_description,
                metadata={
                    "container_image": container_image,
                    "deployment_type": "hosted",
                },
            )
            version_id = f"{agent_version.name}/{agent_version.version}"
            print(f"✅ Hosted agent version created: {version_id}")
            # Export for downstream steps
            gh_env = os.environ.get("GITHUB_ENV")
            if gh_env:
                with open(gh_env, "a") as f:
                    f.write(f"DEPLOYED_AGENT_ID={version_id}\n")
            gh_output = os.environ.get("GITHUB_OUTPUT")
            if gh_output:
                with open(gh_output, "a") as f:
                    f.write(f"AGENT_VERSION={version_id}\n")
            break
        except Exception as e:
            err = str(e)
            print(f"   Error: {err}")
            if attempt < max_retries - 1:
                wait = 10 * (attempt + 1)
                print(f"   Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"❌ Failed after {max_retries} attempts")
                sys.exit(1)


if __name__ == "__main__":
    main()
