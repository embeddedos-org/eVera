#!/bin/bash
# ============================================================
# eVera — Docker Entrypoint Script
# Production-hardened: signal handling, health checks, logging
# ============================================================
set -euo pipefail

# Print banner
echo ""
echo "  ___     __   __"
echo " / __|   \\ \\ / /__ _ _ __ _"
echo "| (__     \\ V / -_) '_/ _\` |"
echo " \\___|     \\_/\\___|_| \\__,_|"
echo ""
echo "  eVera v1.0 — Production Container"
echo "  Agents: 43+ | Tools: 278+ | Languages: 19"
echo "  Host: ${VERA_SERVER_HOST:-0.0.0.0}:${VERA_SERVER_PORT:-8000}"
echo ""

MODE="${1:-server}"

# Validate environment
if [ -z "${VERA_LLM_OPENAI_API_KEY:-}" ] && \
   [ -z "${VERA_LLM_GEMINI_API_KEY:-}" ] && \
   [ -z "${VERA_LLM_ANTHROPIC_API_KEY:-}" ] && \
   [ -z "${VERA_LLM_GROQ_API_KEY:-}" ]; then
    echo "  ⚠  WARNING: No cloud LLM API keys configured."
    echo "     Vera will use Ollama (local) if available."
    echo "     Set VERA_LLM_OPENAI_API_KEY or similar in .env for cloud LLMs."
    echo ""
fi

if [ -z "${VERA_SERVER_API_KEY:-}" ]; then
    echo "  ⚠  WARNING: VERA_SERVER_API_KEY is not set."
    echo "     Public internet connections will be unauthenticated."
    echo "     Set a strong random key in .env for production."
    echo ""
fi

case "$MODE" in
    server)
        echo "  ▶  Starting eVera server..."
        exec python main.py --mode server \
            --host "${VERA_SERVER_HOST:-0.0.0.0}" \
            --port "${VERA_SERVER_PORT:-8000}"
        ;;
    text)
        echo "  ▶  Starting eVera in text mode..."
        exec python main.py --mode text
        ;;
    cli)
        echo "  ▶  Starting eVera in voice CLI mode..."
        exec python main.py --mode cli
        ;;
    both)
        echo "  ▶  Starting eVera in voice + server mode..."
        exec python main.py --mode both \
            --host "${VERA_SERVER_HOST:-0.0.0.0}" \
            --port "${VERA_SERVER_PORT:-8000}"
        ;;
    test)
        echo "  ▶  Running tests..."
        shift
        exec python -m pytest tests/ -v --tb=short "$@"
        ;;
    benchmark)
        echo "  ▶  Running benchmarks..."
        shift
        exec python -m pytest tests/test_benchmarks.py -v -s "$@"
        ;;
    shell)
        echo "  ▶  Starting shell..."
        exec /bin/bash
        ;;
    migrate)
        echo "  ▶  Running database migrations..."
        exec python -m vera.migrations
        ;;
    *)
        exec "$@"
        ;;
esac
