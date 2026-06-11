#!/bin/bash
# Justice_system — Start Script
# Usage: ./scripts/start.sh [--dev|--prod|--share]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Load .env
[ -f .env ] && set -a && source .env && set +a

MODE="${1:-prod}"
HOST="${JUSTICE_HOST:-127.0.0.1}"
PORT="${JUSTICE_PORT:-7860}"

# Ensure venv
if [ ! -d .venv ]; then
    echo "[JUSTICE] Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi

case "$MODE" in
    dev)
        echo "[JUSTICE] Starting in DEV mode on $HOST:$PORT"
        exec .venv/bin/python src/main.py --host "$HOST" --port "$PORT"
        ;;
    prod)
        echo "[JUSTICE] Starting in PROD mode on $HOST:$PORT"
        mkdir -p logs
        exec .venv/bin/python src/main.py --host "$HOST" --port "$PORT" 2>&1 | tee -a logs/justice.log
        ;;
    share)
        echo "[JUSTICE] Starting with public link (Gradio share)"
        exec .venv/bin/python src/main.py --host "$HOST" --port "$PORT" --share
        ;;
    *)
        echo "Usage: $0 [dev|prod|share]"
        exit 1
        ;;
esac
