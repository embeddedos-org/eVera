# ============================================================
# eVera v1.0 — Multi-stage Docker Build
# Voice-first multi-agent AI assistant | 43 agents | 278+ tools
# Production-hardened: non-root, minimal image, health checks
# ============================================================

# --- Stage 1: Builder ---
FROM python:3.14-slim AS builder

WORKDIR /build

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install core requirements
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt || true

# Install optional enhancement packages (failures are non-fatal)
RUN pip install --no-cache-dir --prefix=/install \
    pandas openpyxl matplotlib seaborn scikit-learn duckdb \
    psutil PyPDF2 reportlab deep-translator langdetect \
    python-pptx paramiko 2>/dev/null || true

# --- Stage 2: Runtime ---
FROM python:3.14-slim AS runtime

LABEL maintainer="embeddedos-org"
LABEL description="eVera — Voice-first multi-agent AI assistant (43 agents, 278+ tools)"
LABEL version="1.0.0"
LABEL org.opencontainers.image.title="eVera"
LABEL org.opencontainers.image.description="Voice-first multi-agent AI assistant"
LABEL org.opencontainers.image.source="https://github.com/embeddedos-org/eVera"
LABEL org.opencontainers.image.licenses="MIT"

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates tini && \
    rm -rf /var/lib/apt/lists/* && \
    # Create non-root user
    groupadd -r vera && \
    useradd -r -g vera -d /app -s /sbin/nologin -c "eVera service account" vera

# Copy Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY vera/ ./vera/
COPY config.py main.py pyproject.toml ./
COPY plugins/ ./plugins/

# Create data directories with proper permissions
RUN mkdir -p \
    data/calendar \
    data/flashcards \
    data/study_notes \
    data/automations \
    data/cron_jobs \
    data/webhooks \
    data/social_posts \
    data/api_collections \
    data/migrations \
    data/backups \
    data/reminders \
    data/memory \
    data/logs && \
    chown -R vera:vera /app

# Copy entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh && chown vera:vera /docker-entrypoint.sh

# Production environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    VERA_SERVER_HOST=0.0.0.0 \
    VERA_SERVER_PORT=8000 \
    VERA_LLM_OLLAMA_URL=http://ollama:11434 \
    VERA_LLM_OLLAMA_MODEL=llama3.2 \
    VERA_LLM_FALLBACK_ORDER=ollama,openai,gemini \
    VERA_SERVER_ZONE_WWW_ENABLED=true \
    VERA_SERVER_ZONE_WWW_AUTH_REQUIRED=true \
    VERA_SERVER_ZONE_WWW_RATE_LIMIT_RPM=60

EXPOSE 8000

# Health check — uses /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--", "/docker-entrypoint.sh"]
CMD ["server"]

# Drop to non-root user
USER vera
