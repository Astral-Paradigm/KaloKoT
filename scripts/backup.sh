#!/bin/bash
# Justice_system — Backup Script
# Archives project source, config, and legal corpora

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/justice_${TIMESTAMP}.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "[JUSTICE] Backing up..."
cd "$PROJECT_DIR"

tar -czf "$BACKUP_FILE" \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='logs' \
    --exclude='backups' \
    .

# Keep only last 10 backups
ls -t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[JUSTICE] Backup saved: $BACKUP_FILE ($SIZE)"
echo "[JUSTICE] Backups retained: $(ls "$BACKUP_DIR"/*.tar.gz 2>/dev/null | wc -l)"
