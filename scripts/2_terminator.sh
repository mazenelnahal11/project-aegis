#!/bin/bash
# ============================================================
# Project Aegis - Script 2: Terminator
# Course  : Operating Systems Concepts - Lab Section
# Team    : Mazen Hesham, Mohamed Arafat, Abdelrahman Mohamed,
#           Moaz Ahmed, Ziad Hamed, Mohamed Gamal,
#           Mohand Mouneer, Huda Ahmed, Lamiaa Mahmoud, Omar Abdelaziz
# Authors : Mazen Hesham, Mohamed Arafat, Abdelrahman Mohamed
#
# OS Concepts Used:
#   - Signals / IPC  : kill -15 (SIGTERM), kill -9 (SIGKILL)
#   - Process States : kill -0 checks if process is alive
#   - Exit Codes     : $? checked after every kill
#   - Pipes ( | )    : ps | awk to get process info
#   - I/O Redirection: >> log appending, 2>/dev/null stderr suppress
#   - stderr         : errors sent to >&2
# ============================================================

# ---------- Config ------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/security_audit.log"
PID_FILE="/tmp/aegis_pids.txt"
GRACE=10   # seconds between SIGTERM and SIGKILL

# ---------- Helpers -----------------------------------------
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2" >> "$LOG_FILE"; }

# OS Concept: kill -0 = liveness probe, sends NO real signal
is_alive() { kill -0 "$1" 2>/dev/null; return $?; }

# Get user + command using pipe: ps | awk
proc_info() {
    ps -p "$1" -o user=,comm= 2>/dev/null | awk '{print "USER=" $1 "  CMD=" $2}'
}

# ---------- Main --------------------------------------------
echo "========================================"
echo "  PROJECT AEGIS - Terminator"
echo "========================================"
echo ""
log "INFO" "=== Terminator started ==="

# Guard: PID file must exist and not be empty
if [ ! -f "$PID_FILE" ]; then
    echo "  ERROR: No PID file found. Run process_hunter first." >&2
    log "ERROR" "PID file not found: $PID_FILE"
    exit 1
fi

if [ ! -s "$PID_FILE" ]; then
    echo "  No rogue processes to kill. System is clean."
    log "INFO" "Terminator: PID file empty - nothing to do."
    exit 0
fi

# Read each PID line by line
while IFS= read -r pid; do

    # Input validation: must be a number
    if ! [[ "$pid" =~ ^[0-9]+$ ]]; then
        log "WARN" "Skipping invalid PID: '$pid'"
        continue
    fi

    # Check if process already died before we got here
    if ! is_alive "$pid"; then
        echo "  PID=$pid already gone - skipping."
        log "INFO" "PID=$pid already dead before SIGTERM"
        continue
    fi

    info=$(proc_info "$pid")
    user=$(ps -p "$pid" -o user= 2>/dev/null)

    # ---- Step 1: SIGTERM (signal 15) -----------------------
    # OS Concept: SIGTERM can be caught/ignored by the process
    echo "  Sending SIGTERM (15) -> PID=$pid  $info"
    kill -15 "$pid" 2>/dev/null
    exit_code=$?   # OS Concept: $? holds exit code of last command

    if [ "$exit_code" -ne 0 ]; then
        echo "  WARNING: SIGTERM failed for PID=$pid (permission?)" >&2
        log "WARN" "SIGTERM failed | PID=$pid | exit=$exit_code"
        continue
    fi
    log "ACTION" "SIGTERM sent | PID=$pid | $info | USER=$user"

    # ---- Wait grace period ---------------------------------
    echo "  Waiting ${GRACE}s for graceful exit..."
    sleep "$GRACE"

    # ---- Step 2: SIGKILL if still alive --------------------
    # OS Concept: SIGKILL (9) cannot be caught, blocked, or ignored
    if is_alive "$pid"; then
        echo "  PID=$pid still alive - sending SIGKILL (9)..."
        kill -9 "$pid" 2>/dev/null
        exit_code=$?

        if [ "$exit_code" -eq 0 ]; then
            log "ACTION" "SIGKILL sent | PID=$pid | $info | USER=$user"
            sleep 1
            if is_alive "$pid"; then
                # Only possible if process is in D state (uninterruptible I/O)
                echo "  ERROR: PID=$pid survived SIGKILL (D-state / kernel I/O wait)" >&2
                log "ERROR" "PID=$pid survived SIGKILL - likely in uninterruptible sleep (D)"
            else
                echo "  PID=$pid killed with SIGKILL."
                log "ACTION" "PID=$pid terminated via SIGKILL | USER=$user"
            fi
        else
            echo "  ERROR: SIGKILL failed for PID=$pid" >&2
            log "ERROR" "SIGKILL failed | PID=$pid | exit=$exit_code"
        fi
    else
        echo "  PID=$pid exited cleanly after SIGTERM."
        log "ACTION" "PID=$pid exited cleanly via SIGTERM | USER=$user"
    fi
    echo ""

done < "$PID_FILE"

log "INFO" "=== Terminator done ==="
echo "----------------------------------------"
echo "  Terminator done."
echo "----------------------------------------"
