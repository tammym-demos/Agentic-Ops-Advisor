# =============================================================================
# Dockerfile — Agentic Ops Advisor (Multi-stage optimized)
# Production container for Azure AI Foundry Agent Service deployment
# Size optimization: ~450 MB target (vs ~550-800 MB single-stage)
# =============================================================================

# ============ STAGE 1: Builder ============
# Install build tools and compile Python wheels
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        libffi-dev \
        python3-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .

RUN pip install --no-cache-dir --no-warn-script-location \
        --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --no-warn-script-location \
        -r requirements.txt

# ============ STAGE 2: Runtime ============
FROM python:3.11-slim AS runtime

LABEL maintainer="Agentic Ops Advisor Team" \
      description="Governed AI agent for infrastructure root-cause and change-context reasoning" \
      version="1.0.0"

# ---- Python behaviour ----
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# ---- System dependencies & Microsoft ODBC Driver 18 ----
# Base image is Debian 13 (trixie) — use official Microsoft .deb package
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg && \
    curl -fsSL https://packages.microsoft.com/config/debian/13/packages-microsoft-prod.deb \
        -o /tmp/packages-microsoft-prod.deb && \
    dpkg -i /tmp/packages-microsoft-prod.deb && \
    rm /tmp/packages-microsoft-prod.deb && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 && \
    apt-get purge -y --auto-remove gnupg && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ---- Copy compiled dependencies from builder (system-wide install) ----
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# ---- Non-root user ----
RUN groupadd --system agent && \
    useradd --system --gid agent --create-home agent

# ---- Working directory ----
WORKDIR /app

# ---- Application source ----
COPY pyproject.toml .
COPY agent/  agent/
COPY tools/  tools/
COPY data/   data/
COPY scripts/ scripts/
COPY eval/   eval/
COPY static/ static/

# ---- Seed local SQLite database at build time ----
RUN python scripts/setup_local_db.py

# ---- Ensure the agent user owns the app directory ----
RUN chown -R agent:agent /app

# ---- Default environment variables ----
ENV DB_MODE=sqlite \
    ENABLE_WORK_IQ=true \
    ENABLE_MCP=false \
    MODE=serve

# ---- Expose hosted agent service port ----
# Port 8088 for Azure AI Foundry Agent Service (non-privileged port for non-root user)
# Foundry reads EXPOSE to determine the target port for routing
# Override via PORT env var for local development
EXPOSE 8088

# ---- Health check ----
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${SERVE_PORT:-8088}/readiness || exit 1

# ---- Run as non-root ----
USER agent

# ---- Entrypoint ----
ENTRYPOINT ["python", "scripts/serve.py"]
