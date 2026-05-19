#!/bin/bash
# ============================================================
# Project Aegis - Script 1: Process Hunter
# Course  : Operating Systems Concepts - Lab Section
# Team    : Mazen Hesham, Mohamed Arafat, Abdelrahman Mohamed,
#           Moaz Ahmed, Ziad Hamed, Mohamed Gamal,
#           Mohand Mouneer, Huda Ahmed, Lamiaa Mahmoud, Omar Abdelaziz
# Authors : Mazen Hesham, Mohamed Arafat, Abdelrahman Mohamed
#
# OS Concepts Used:
#   - Process Management     : ps command to list all processes
#   - Pipes ( | )            : chain ps -> awk -> while loop
#   - awk                    : extract fields, arithmetic, conditions
#   - Background Jobs        : detect processes running in background
#   - I/O Redirection ( >> ) : write PIDs to file, append to log
#   - stderr Redirection     : 2>/dev/null suppresses permission errors
# ============================================================

# ---------- Config ------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/security_audit.log"
PID_FILE="/tmp/aegis_pids.txt"
CPU_LIMIT=80       # percent
TIME_LIMIT=86400   # seconds = 24 hours

# ---------- Helpers -----------------------------------------
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2" >> "$LOG_FILE"; }

# ---------- Setup -------------------------------------------
mkdir -p "$PROJECT_DIR/logs"
> "$PID_FILE"   # clear old PIDs (I/O truncation)
log "INFO" "=== Process Hunter started ==="
echo "========================================"
echo "  PROJECT AEGIS - Process Hunter"
echo "========================================"
echo ""

# ---------- MAIN SCAN ---------------------------------------
# OS Concept: Pipes (|)
# ps prints raw data -> pipe -> awk extracts + filters -> pipe -> while reads results
#
# awk variables passed from bash: cpu_limit, time_limit
# awk logic:
#   $1=pid  $2=user  $3=cpu  $4=mem  $5=etimes  $6=comm
#   skip system users (root, daemon, nobody, www-data)
#   flag if cpu >= limit OR runtime >= limit
#   print flagged rows as: pid|user|cpu|mem|etimes|comm|reason

echo "[1] Scanning all running processes..."
echo ""

ps -eo pid,user,%cpu,%mem,etimes,comm --no-headers 2>/dev/null \
| awk -v cpu_limit="$CPU_LIMIT" -v time_limit="$TIME_LIMIT" '
{
    pid    = $1
    user   = $2
    cpu    = $3
    mem    = $4
    etimes = $5
    comm   = $6

    # Skip system/root users
    if (user == "root"    || user == "daemon"   || user == "nobody" ||
        user == "www-data"|| user == "systemd+"  || user == "dbus"  ||
        user == "syslog"  || user == "messagebus") next

    cpu_int = int(cpu)   # convert float to int for comparison
    flagged = 0
    reason  = ""

    # Check runtime > 24h
    if (etimes + 0 >= time_limit) {
        flagged = 1
        hours   = int(etimes / 3600)
        reason  = "Runtime=" hours "h (>= 24h)"
    }

    # Check CPU > 80%
    if (cpu_int >= cpu_limit) {
        flagged = 1
        sep     = (reason != "") ? " | " : ""
        reason  = reason sep "CPU=" cpu "% (>= " cpu_limit "%)"
    }

    if (flagged)
        print pid "|" user "|" cpu "|" mem "|" etimes "|" comm "|" reason
}
' \
| while IFS='|' read -r pid user cpu mem etimes comm reason; do
    echo "  [FLAGGED] PID=$pid  USER=$user  CMD=$comm"
    echo "            Reason: $reason"
    echo "            MEM=${mem}%"
    echo ""
    echo "$pid" >> "$PID_FILE"
    log "WARN" "ROGUE PROCESS | PID=$pid | USER=$user | CMD=$comm | $reason | MEM=${mem}%"
done

# ---------- BACKGROUND JOBS CHECK ---------------------------
# OS Concept: Background Jobs - detect stopped/zombie/sleeping processes
echo "[2] Checking for suspicious background job states..."
echo ""

ps -eo pid,user,stat,comm --no-headers 2>/dev/null \
| awk '{
    pid=  $1; user=$2; stat=$3; comm=$4
    if (user=="root" || user=="daemon" || user=="nobody") next
    # T=stopped, Z=zombie, D=uninterruptible sleep
    if (stat ~ /^[TZD]/)
        print pid "|" user "|" stat "|" comm
}' \
| while IFS='|' read -r pid user stat comm; do
    echo "  [SUSPICIOUS] PID=$pid  USER=$user  STATE=$stat  CMD=$comm"
    log "WARN" "SUSPICIOUS STATE | PID=$pid | USER=$user | STATE=$stat | CMD=$comm"
done

# ---------- Summary -----------------------------------------
total=$(wc -l < "$PID_FILE" 2>/dev/null || echo 0)
log "INFO" "=== Process Hunter done - $total rogue process(es) found ==="
echo ""
echo "----------------------------------------"
echo "  Done. $total rogue PID(s) -> $PID_FILE"
echo "----------------------------------------"
