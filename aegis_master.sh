#!/bin/bash
# ============================================================
# Project Aegis - Master Orchestrator
# Course  : Operating Systems Concepts - Lab Section
# Team    : Mazen Hesham, Mohamed Arafat, Abdelrahman Mohamed,
#           Moaz Ahmed, Ziad Hamed, Mohamed Gamal,
#           Mohand Mouneer, Huda Ahmed, Lamiaa Mahmoud, Omar Abdelaziz
# Authors : Mohand Mouneer, Huda Ahmed
#
# OS Concepts Used:
#   - Background scheduling : cron (see comment below)
#   - I/O Redirection       : >> log, 2>&1 merge stderr+stdout
#   - Exit Codes ($?)       : checked after each stage
#   - Pipes                 : used inside called scripts
#
# Usage:
#   sudo ./aegis_master.sh                    full run
#   sudo ./aegis_master.sh --dry-run          detect only, no changes
#   sudo ./aegis_master.sh --scan-dir /srv    custom directory
#
# Cron - run every hour automatically (OS Concept: scheduling):
#   0 * * * * /path/to/aegis_master.sh >> /var/log/aegis.log 2>&1
# ============================================================

set -uo pipefail

# ---------- Paths -------------------------------------------
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$DIR/scripts"
LOG_FILE="$DIR/logs/security_audit.log"

# ---------- Defaults ----------------------------------------
DRY_RUN=false
SCAN_DIR="/home"

# ---------- Args --------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)   DRY_RUN=true  ; shift ;;
        --scan-dir)  SCAN_DIR="$2" ; shift 2 ;;
        -h|--help)
            grep '^#' "$0" | grep -v '#!/' | sed 's/^# \?//'
            exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

# ---------- Helpers -----------------------------------------
mkdir -p "$DIR/logs"
log_m() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [MASTER] $1" | tee -a "$LOG_FILE"; }

run_stage() {
    local name="$1" script="$2"; shift 2
    chmod +x "$script"
    echo ""
    echo ">> STAGE: $name"
    echo "   -----------------------------------------------"
    bash "$script" "$@"
    local rc=$?
    [ "$rc" -eq 0 ] \
        && log_m "$name -> OK (exit 0)" \
        || log_m "WARNING: $name -> exit $rc"
    echo ""
}

# ---------- Banner ------------------------------------------
echo ""
echo "============================================================"
echo "  PROJECT AEGIS - Security & Resource Audit System"
echo "  Badya University - OS Lab"
echo "------------------------------------------------------------"
echo "  Team:"
echo "    Mazen Hesham       | Mohamed Arafat    | Abdelrahman Mohamed"
echo "    Moaz Ahmed         | Ziad Hamed        | Mohamed Gamal"
echo "    Mohand Mouneer     | Huda Ahmed"
echo "    Lamiaa Mahmoud     | Omar Abdelaziz"
echo "------------------------------------------------------------"
printf "  Date     : %s\n" "$(date '+%Y-%m-%d %H:%M:%S')"
printf "  Mode     : %s\n" "$($DRY_RUN && echo 'DRY RUN - detect only' || echo 'LIVE - changes will apply')"
printf "  Scan Dir : %s\n" "$SCAN_DIR"
echo "============================================================"

log_m "Pipeline started | DRY_RUN=$DRY_RUN | SCAN_DIR=$SCAN_DIR"

# ---------- Stage 1: Process Hunter -------------------------
run_stage "Process Hunter" "$SCRIPTS/1_process_hunter.sh"

# ---------- Stage 2: Terminator -----------------------------
if $DRY_RUN; then
    echo ">> STAGE: Terminator - SKIPPED (dry-run)"
    log_m "Terminator skipped (dry-run)"
else
    run_stage "Terminator" "$SCRIPTS/2_terminator.sh"
fi

# ---------- Stage 3: Permission Auditor ---------------------
if $DRY_RUN; then
    echo ">> STAGE: Permission Auditor - SKIPPED (dry-run)"
    log_m "Permission Auditor skipped (dry-run)"
else
    run_stage "Permission Auditor" "$SCRIPTS/3_permission_auditor.sh" "$SCAN_DIR"
fi

# ---------- Stage 4: Audit Logger ---------------------------
run_stage "Audit Logger - Summary" "$SCRIPTS/4_audit_logger.sh" "--summary"
run_stage "Audit Logger - Report"  "$SCRIPTS/4_audit_logger.sh" "--report"

log_m "Pipeline complete."
echo "============================================================"
echo "  Done. Log -> $LOG_FILE"
echo "============================================================"
