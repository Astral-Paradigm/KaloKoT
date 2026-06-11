#!/bin/bash
# Justice_system — Restore Script
# Usage: ./scripts/restore.sh <backup_file>

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    echo "Available backups:"
    ls -t "$(dirname "$0")/../backups"/*.tar.gz 2>/dev/null || echo "  (none found)"
    exit 1
fi

BACKUP_FILE="$1"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "[JUSTICE] Error: backup file not found: $BACKUP_FILE"
    exit 1
fi

# Stop if running
"$PROJECT_DIR/scripts/stop.sh" 2>/dev/null || true

echo "[JUSTICE] Restoring from $BACKUP_FILE..."
cd "$PROJECT_DIR"
tar -xzf "$BACKUP_FILE"

echo "[JUSTICE] Restore complete. Start with ./scripts/start.sh prod"
