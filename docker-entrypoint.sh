#!/bin/bash
set -e

echo ""
echo " __     __"
echo " \ \   / /___   ___  __ _"
echo "  \ \ / / _ \ / __|/ _\` |"
echo "   \ V / (_) | (__| (_| |"
echo "    \_/ \___/ \___|\__,_|"
echo ""
echo "  eVera v1.0 — Docker Container"
echo "  Agents: 43+ | Tools: 278+"
echo ""

MODE="${1:-server}"

case "$MODE" in
    server)
        echo "Starting eVera server on ${VERA_SERVER_HOST:-0.0.0.0}:${VERA_SERVER_PORT:-8000}..."
        exec python main.py --mode server --host "${VERA_SERVER_HOST:-0.0.0.0}" --port "${VERA_SERVER_PORT:-8000}"
        ;;
    text)
        echo "Starting eVera in text mode..."
        exec python main.py --mode text
        ;;
    cli)
        echo "Starting eVera in voice CLI mode..."
        exec python main.py --mode cli
        ;;
    both)
        echo "Starting eVera in voice + server mode..."
        exec python main.py --mode both --host "${VERA_SERVER_HOST:-0.0.0.0}" --port "${VERA_SERVER_PORT:-8000}"
        ;;
    test)
        echo "Running tests..."
        shift
        exec python -m pytest tests/ -v --tb=short "$@"
        ;;
    benchmark)
        echo "Running benchmarks..."
        shift
        exec python -m pytest tests/test_benchmarks.py -v -s "$@"
        ;;
    shell)
        echo "Starting shell..."
        exec /bin/bash
        ;;
    *)
        exec "$@"
        ;;
esac
