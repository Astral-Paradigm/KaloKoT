#!/bin/bash
# Justice_system — Health Check
# Checks if the Gradio server is responding

set -euo pipefail

HOST="${JUSTICE_HOST:-127.0.0.1}"
PORT="${JUSTICE_PORT:-7860}"
URL="http://${HOST}:${PORT}/"

if curl -sf -o /dev/null "$URL" 2>/dev/null; then
    echo "[JUSTICE] HEALTHY — Server responding on $URL"
    exit 0
else
    echo "[JUSTICE] UNHEALTHY — Server not responding on $URL"
    exit 1
fi
