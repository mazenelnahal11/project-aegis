#!/bin/bash
# ============================================================
# Project Aegis - Demo Setup
# Team    : Lamiaa Mahmoud, Omar Abdelaziz (Architects/Presenters)
#
# Creates a safe demo environment BEFORE the live presentation.
# Spawns a background process (OS Concept: Background Jobs)
# and creates 777 files to show the "before" state.
#
# Usage:
#   ./demo_setup.sh             create demo environment
#   ./demo_setup.sh --cleanup   remove everything after demo
# ============================================================

DEMO_DIR="/tmp/aegis_demo/home_mock"
PIDS_FILE="/tmp/aegis_demo/demo_pids.txt"

cleanup() {
    echo "[DEMO] Cleaning up..."
    [ -f "$PIDS_FILE" ] && while IFS= read -r p; do
        kill "$p" 2>/dev/null && echo "  Killed demo PID $p"
    done < "$PIDS_FILE"
    rm -rf /tmp/aegis_demo
    echo "[DEMO] Done."
    exit 0
}

[ "${1:-}" = "--cleanup" ] && cleanup

mkdir -p "$DEMO_DIR/mazen_hesham" "$DEMO_DIR/moaz_ahmed" "$DEMO_DIR/ziad_hamed"
mkdir -p /tmp/aegis_demo
> "$PIDS_FILE"

echo ""
echo "============================================================"
echo "  PROJECT AEGIS - Demo Setup"
echo "  Lamiaa Mahmoud & Omar Abdelaziz"
echo "============================================================"
echo ""

# Create insecure 777 files - "before" state
echo "[1] Creating world-writable (777) files..."
touch "$DEMO_DIR/mazen_hesham/dataset.csv"      && chmod 777 "$DEMO_DIR/mazen_hesham/dataset.csv"
touch "$DEMO_DIR/mazen_hesham/model.pt"          && chmod 777 "$DEMO_DIR/mazen_hesham/model.pt"
mkdir -p "$DEMO_DIR/moaz_ahmed/secret_project"   && chmod 777 "$DEMO_DIR/moaz_ahmed/secret_project"
touch "$DEMO_DIR/moaz_ahmed/api_keys.txt"        && chmod 777 "$DEMO_DIR/moaz_ahmed/api_keys.txt"
touch "$DEMO_DIR/ziad_hamed/results.csv"         && chmod 777 "$DEMO_DIR/ziad_hamed/results.csv"
echo "  Created 5 world-writable items."

# Spawn background rogue process (OS Concept: Background Jobs with &)
echo ""
echo "[2] Spawning rogue background process..."
( while true; do :; done ) &   # infinite CPU loop runs in background with &
ROGUE_PID=$!
echo "$ROGUE_PID" >> "$PIDS_FILE"
echo "  Rogue PID=$ROGUE_PID (background CPU loop)"

echo ""
echo "============================================================"
echo "  BEFORE STATE:"
echo ""
echo "  World-writable files:"
find "$DEMO_DIR" -perm 777 2>/dev/null | sed 's/^/    /'
echo ""
echo "  Rogue background process:"
ps -p "$ROGUE_PID" -o pid,user,%cpu,stat,comm 2>/dev/null | sed 's/^/    /'
echo ""
echo "  NOW RUN:"
echo "    sudo ./aegis_master.sh --scan-dir $DEMO_DIR"
echo ""
echo "  AFTER DEMO:"
echo "    ./demo_setup.sh --cleanup"
echo "============================================================"
