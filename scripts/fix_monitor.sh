#!/bin/bash
# Monitor the Hermes CLI bug-fix session
# Runs as a watchdog: checks every 60s if fixes are applied

set -euo pipefail

BUG_FIX_DIR="$HOME/Documents/Justice_system/justice_system_bug_fixes"
TARGET_DIR="$HOME/Documents/Justice_system"
LOG_FILE="$HOME/Documents/Justice_system/logs/fix_monitor.log"
HERMES_PID=6211
API_PID=40507

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%H:%M:%S')] $*" >> "$LOG_FILE"; }

# Check what fix files exist and their md5
declare -A FIX_HASHES
while IFS= read -r -d '' f; do
    rel="${f#$BUG_FIX_DIR/}"
    FIX_HASHES["$rel"]=$(md5sum "$f" | cut -d' ' -f1)
done < <(find "$BUG_FIX_DIR" -name "*.py" -print0)

TOTAL_FIXES=${#FIX_HASHES[@]}
log "Monitoring $TOTAL_FIXES fix files. Hermes PID=$HERMES_PID"

PREV_MATCHED=0
STALL_COUNT=0

while true; do
    # Check if Hermes is still running
    if ! kill -0 "$HERMES_PID" 2>/dev/null; then
        log "HERMES CLI PROCESS EXITED"
        APPLIED_COUNT=0
        for rel in "${!FIX_HASHES[@]}"; do
            target="$TARGET_DIR/$rel"
            if [ -f "$target" ]; then
                target_hash=$(md5sum "$target" | cut -d' ' -f1)
                if [ "${FIX_HASHES[$rel]}" = "$target_hash" ]; then
                    APPLIED_COUNT=$((APPLIED_COUNT + 1))
                fi
            fi
        done
        log "All done. $APPLIED_COUNT/$TOTAL_FIXES fixes applied. Shutting down."
        echo "COMPLETE:$APPLIED_COUNT/$TOTAL_FIXES"
        exit 0
    fi

    # Count how many fixes are now applied
    MATCHED=0
    for rel in "${!FIX_HASHES[@]}"; do
        target="$TARGET_DIR/$rel"
        if [ -f "$target" ]; then
            target_hash=$(md5sum "$target" | cut -d' ' -f1)
            [ "${FIX_HASHES[$rel]}" = "$target_hash" ] && MATCHED=$((MATCHED + 1))
        fi
    done

    if [ "$MATCHED" -ne "$PREV_MATCHED" ]; then
        log "Progress: $MATCHED/$TOTAL_FIXES fixes matched (was $PREV_MATCHED)"
        PREV_MATCHED=$MATCHED
        STALL_COUNT=0
    else
        STALL_COUNT=$((STALL_COUNT + 1))
        # Also check if there's ANY recent modification
        RECENT=$(find "$TARGET_DIR/src" -name "*.py" -mmin -5 -type f 2>/dev/null | wc -l)
        if [ "$RECENT" -gt 0 ]; then
            STALL_COUNT=0  # Reset stall - something is being modified
        fi
    fi

    # If stalled > 30 checks (30 min with no activity at all), flag it
    if [ "$STALL_COUNT" -gt 30 ]; then
        log "STALL WARNING: No progress in 30+ minutes"
        echo "STALLED"
        exit 2
    fi

    sleep 60
done
