# =============================================================================
# Dockerfile — Agentic Ops Advisor
# Production container for Azure AI Foundry Agent Service deployment
# =============================================================================

FROM python:3.11-slim AS runtime

LABEL maintainer="Agentic Ops Advisor Team" \
      description="Governed AI agent for infrastructure root-cause and change-context reasoning" \
      version="1.0.0"

# ---- Python behaviour ----
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ---- System dependencies & Microsoft ODBC Driver 18 ----
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        unixodbc-dev && \
    # Add Microsoft package repository (Debian 12 / bookworm)
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | \
        gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] \
        https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 && \
    # Clean up apt caches to keep image lean
    apt-get purge -y --auto-remove gnupg && \
    rm -rf /var/lib/apt/lists/*

# ---- Non-root user ----
RUN groupadd --system agent && \
    useradd --system --gid agent --create-home agent

# ---- Working directory ----
WORKDIR /app

# ---- Python dependencies (layer-cached) ----
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- Application source ----
COPY pyproject.toml .
COPY agent/  agent/
COPY tools/  tools/
COPY data/   data/
COPY scripts/ scripts/
COPY eval/   eval/

# ---- Seed local SQLite database at build time ----
RUN python scripts/setup_local_db.py

# ---- Ensure the agent user owns the app directory ----
RUN chown -R agent:agent /app

# ---- Default environment variables ----
ENV DB_MODE=sqlite \
    ENABLE_WORK_IQ=true \
    ENABLE_MCP=false

# ---- Expose health-check / readiness-probe port ----
EXPOSE 8080

# ---- Health check ----
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# ---- Run as non-root ----
USER agent

# ---- Entrypoint ----
ENTRYPOINT ["python", "scripts/run_local.py"]
