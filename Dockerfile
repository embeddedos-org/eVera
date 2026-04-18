FROM python:3.12-slim AS base

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    libsndfile1 \
    build-essential \
    curl \
    # For Playwright browser automation
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser
RUN pip install playwright && python -m playwright install chromium --with-deps || true

# Copy app
COPY . .

# Create data directories
RUN mkdir -p data/browser_sessions data/faiss_index

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Labels
LABEL org.opencontainers.image.title="Voca AI Buddy"
LABEL org.opencontainers.image.description="Voice-first multi-agent AI assistant"
LABEL org.opencontainers.image.version="0.4.1"

# Default: server mode
CMD ["python", "main.py", "--mode", "server", "--host", "0.0.0.0", "--port", "8000"]
