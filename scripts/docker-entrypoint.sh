#!/bin/bash
set -e

# Start FastAPI backend
echo "Starting FastAPI backend..."
python3 src/main.py --api &
BACKEND_PID=$!

# Start Nitro SSR frontend
echo "Starting Nitro SSR frontend..."
PORT=${PORT:-8080} node /app/frontend/dist/server/index.mjs &
FRONTEND_PID=$!

echo "Both servers running. Backend PID: $BACKEND_PID, Frontend PID: $FRONTEND_PID"

cleanup() {
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

# Wait and report which process exited
set +e
wait -n
EXIT_CODE=$?
echo "Process exited with code $EXIT_CODE"
cleanup
