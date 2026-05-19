#!/bin/bash
# ============================================================
# Project Aegis - Script 3: Permission Auditor
# Course  : Operating Systems Concepts - Lab Section
# Team    : Mazen Hesham, Mohamed Arafat, Abdelrahman Mohamed,
#           Moaz Ahmed, Ziad Hamed, Mohamed Gamal,
#           Mohand Mouneer, Huda Ahmed, Lamiaa Mahmoud, Omar Abdelaziz
# Authors : Moaz Ahmed, Ziad Hamed, Mohamed Gamal
#
# OS Concepts Used:
#   - File Permissions : chmod, octal notation (777, 755, 644)
#   - find command     : scan directory tree by permission
#   - Pipes ( | )      : find -> awk -> while loop
#   - awk              : extract and format file info
#   - sed              : clean up file type string output
#   - Exit Codes ($?)  : check chmod success/failure
#   - stderr           : 2>/dev/null, >&2 for error output
# ============================================================

# ---------- Config ------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/security_audit.log"
SCAN_DIR="${1:-/home}"   # default scan /home, can override: ./script /srv
REPORT="$PROJECT_DIR/logs/perm_report_$(date '+%Y%m%d_%H%M%S').txt"

# ---------- Helpers -----------------------------------------
log() {
    local entry="[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2"
    echo "$entry" >> "$LOG_FILE"
    echo "$entry" >> "$REPORT"
}

# ---------- Setup -------------------------------------------
mkdir -p "$PROJECT_DIR/logs"
log "INFO" "=== Permission Auditor started - scanning: $SCAN_DIR ==="
echo "========================================"
echo "  PROJECT AEGIS - Permission Auditor"
echo "  Scanning: $SCAN_DIR"
echo "========================================"
echo ""

fixed=0
errors=0

# ---------- MAIN SCAN ---------------------------------------
# OS Concept: Pipes (|)
# find locates 777 files -> pipe -> awk passes path -> pipe -> while fixes each
#
# find -perm 777 : exact match for world-writable (rwxrwxrwx)
# 2>/dev/null    : suppress "Permission denied" from find itself (stderr redirect)

echo "[*] Finding world-writable (777) files and directories..."
echo ""

find "$SCAN_DIR" -perm 777 2>/dev/null \
| awk '{ print $0 }' \
| while IFS= read -r target; do

    # Get file owner using stat + awk
    owner=$(stat -c '%U' "$target" 2>/dev/null)

    # Get file type using stat then sed to clean up label
    # sed: removes the word "regular " -> "regular file" becomes "file"
    ftype=$(stat -c '%F' "$target" 2>/dev/null | sed 's/regular //')

    # Decide new permission based on type
    # OS Concept: File Permission octal notation
    #   755 = rwxr-xr-x  (directory needs x for traversal)
    #   644 = rw-r--r--  (regular file)
    if [ -d "$target" ]; then
        new_perm="755"
    else
        new_perm="644"
    fi

    # Show current permissions using ls + awk (pipe)
    old_perms=$(ls -ld "$target" 2>/dev/null | awk '{print $1}')

    # Apply chmod and capture exit code
    chmod "$new_perm" "$target" 2>/dev/null
    rc=$?   # OS Concept: $? = exit code of last command

    if [ "$rc" -eq 0 ]; then
        printf "  [FIXED]  %-45s  %s -> %s\n" "$target" "777" "$new_perm"
        printf "           Owner=%-12s  Type=%s\n" "$owner" "$ftype"
        echo ""
        log "ACTION" "PERM FIXED | PATH=$target | TYPE=$ftype | OWNER=$owner | 777 -> $new_perm"
        (( fixed++ )) || true
    else
        printf "  [ERROR]  %-45s  chmod failed (rc=%s)\n" "$target" "$rc" >&2
        log "ERROR" "PERM FIX FAILED | PATH=$target | OWNER=$owner | rc=$rc"
        (( errors++ )) || true
    fi

done

# ---------- Summary using awk on report file ----------------
# awk counts ACTION and ERROR lines from this run's report
echo ""
echo "[*] Summary:"
if [ -f "$REPORT" ]; then
    awk '
        /\[ACTION\]/ { fixed++ }
        /\[ERROR\]/  { err++ }
        END {
            printf "  Fixed  : %d\n", fixed+0
            printf "  Errors : %d\n", err+0
        }
    ' "$REPORT"
fi

log "INFO" "=== Permission Auditor done - Fixed=$fixed Errors=$errors ==="
echo ""
echo "  Report saved -> $REPORT"
echo "----------------------------------------"
