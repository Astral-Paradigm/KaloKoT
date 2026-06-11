#!/bin/bash
# Justice_system — Docker Build & Run
# Usage: ./scripts/docker.sh [build|up|down|logs]

set -euo pipefail

CMD="${1:-help}"

case "$CMD" in
    build)
        docker compose build
        ;;
    up)
        docker compose up -d
        echo "[JUSTICE] Running at http://localhost:7860"
        ;;
    down)
        docker compose down
        ;;
    logs)
        docker compose logs -f
        ;;
    rebuild)
        docker compose down
        docker compose build --no-cache
        docker compose up -d
        echo "[JUSTICE] Rebuilt and running"
        ;;
    *)
        echo "Usage: $0 [build|up|down|logs|rebuild]"
        exit 1
        ;;
esac
