# ============================================================
# eVera v1.0 — Multi-stage Docker Build
# Voice-first multi-agent AI assistant | 43 agents | 278+ tools
# ============================================================

# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt || true
RUN pip install --no-cache-dir --prefix=/install \
    pandas openpyxl matplotlib seaborn scikit-learn duckdb \
    psutil pyperclip PyPDF2 reportlab deep-translator langdetect \
    python-pptx speedtest-cli paramiko trimesh 2>/dev/null || true

# --- Stage 2: Runtime ---
FROM python:3.12-slim AS runtime

LABEL maintainer="spatchava@meta.com"
LABEL description="eVera — Voice-first multi-agent AI assistant"
LABEL version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/embeddedos-org/eVera"

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r vera && useradd -r -g vera -d /app -s /sbin/nologin vera

# Copy Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY vera/ ./vera/
COPY config.py main.py pyproject.toml ./
COPY plugins/ ./plugins/

# Create data directories
RUN mkdir -p data/calendar data/flashcards data/study_notes data/automations \
    data/cron_jobs data/webhooks data/social_posts data/api_collections \
    data/migrations data/backups data/reminders && \
    chown -R vera:vera /app

# Copy entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VERA_SERVER_HOST=0.0.0.0 \
    VERA_SERVER_PORT=8000 \
    VERA_LLM_OLLAMA_URL=http://ollama:11434 \
    VERA_LLM_OLLAMA_MODEL=llama3.2 \
    VERA_LLM_FALLBACK_ORDER=ollama,openai,gemini

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

USER vera

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["server"]
