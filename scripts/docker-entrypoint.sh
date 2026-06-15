#!/bin/bash
set -e

echo "Starting FastAPI backend..."
python3 src/main.py --api &
BACKEND_PID=$!

echo "Starting Nitro SSR frontend..."
PORT=${PORT:-8080} node /app/frontend/dist/server/index.mjs &
FRONTEND_PID=$!

cleanup() {
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

echo "Both servers running. Backend PID: $BACKEND_PID, Frontend PID: $FRONTEND_PID"
wait
