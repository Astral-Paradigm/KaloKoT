#!/bin/bash
set -e

echo "Starting FastAPI backend..."
python3 src/main.py --api &
BACKEND_PID=$!

# Wait for FastAPI to be ready (up to 5 minutes)
echo "Waiting for FastAPI on port $API_PORT..."
for i in $(seq 1 60); do
    if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${API_PORT:-8000}/health', timeout=2)" 2>/dev/null; then
        echo "FastAPI is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "FastAPI failed to start within 5 minutes"
        exit 1
    fi
    sleep 5
done

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

set +e
wait -n
EXIT_CODE=$?
echo "Process exited with code $EXIT_CODE"
cleanup
