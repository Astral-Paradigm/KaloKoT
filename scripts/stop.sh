#!/bin/bash
# Justice_system — Stop Script

set -euo pipefail

PID_FILE="${TMPDIR:-/tmp}/justice.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[JUSTICE] Stopping PID $PID..."
        kill -TERM "$PID" 2>/dev/null || true
        sleep 2
        kill -KILL "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "[JUSTICE] Stopped."
    else
        rm -f "$PID_FILE"
        echo "[JUSTICE] PID not running."
    fi
else
    echo "[JUSTICE] No PID file found."
fi

# Fallback: kill any lingering gradio processes
pkill -f "python.*main.py" 2>/dev/null && echo "[JUSTICE] Cleaned up residual processes." || true
