#!/bin/bash
# ============================================================
# Project Aegis - Script 4: Audit Logger
# Course  : Operating Systems Concepts - Lab Section
# Team    : Mazen Hesham, Mohamed Arafat, Abdelrahman Mohamed,
#           Moaz Ahmed, Ziad Hamed, Mohamed Gamal,
#           Mohand Mouneer, Huda Ahmed, Lamiaa Mahmoud, Omar Abdelaziz
# Authors : Mohand Mouneer, Huda Ahmed
#
# OS Concepts Used:
#   - I/O Redirection : >> append, > create, 2>/dev/null
#   - awk             : parse + count log entries by pattern
#   - sed             : replace text for HTML color coding
#   - grep            : filter lines by pattern
#   - Pipes ( | )     : chain grep | tail | awk
#   - gzip            : compress old log files (log rotation)
#   - find -mtime     : locate files older than N days
#
# Usage:
#   ./4_audit_logger.sh --summary   print event counts
#   ./4_audit_logger.sh --rotate    compress logs > 30 days
#   ./4_audit_logger.sh --report    generate HTML report
# ============================================================

# ---------- Config ------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/security_audit.log"
ARCHIVE_DIR="$PROJECT_DIR/logs/archive"
ROTATE_DAYS=30
TODAY=$(date '+%Y-%m-%d')

# ---------- Helpers -----------------------------------------
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2" | tee -a "$LOG_FILE"; }

# ---------- SUMMARY -----------------------------------------
# OS Concept: awk multi-pattern counting + pipes
show_summary() {
    echo "========================================"
    echo "  PROJECT AEGIS - Audit Summary"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "  Badya University - OS Lab"
    echo "========================================"
    echo ""
    echo "  Team:"
    echo "    Mazen Hesham        Mohamed Arafat      Abdelrahman Mohamed"
    echo "    Moaz Ahmed          Ziad Hamed           Mohamed Gamal"
    echo "    Mohand Mouneer      Huda Ahmed"
    echo "    Lamiaa Mahmoud      Omar Abdelaziz"
    echo ""
    echo "----------------------------------------"

    if [ ! -f "$LOG_FILE" ]; then
        echo "  No log file found at $LOG_FILE"
        return 1
    fi

    # awk scans the whole log file once, counting each event type
    # pipes used: grep | tail | awk for the last-actions section
    awk '
        /SIGTERM sent/   { sigterm++ }
        /SIGKILL sent/   { sigkill++ }
        /PERM FIXED/     { perm++    }
        /ROGUE PROCESS/  { rogue++   }
        /\[ERROR\]/      { errors++  }
        /\[WARN\]/       { warns++   }
        END {
            printf "  %-38s %d\n", "Rogue processes detected:",        rogue+0
            printf "  %-38s %d\n", "SIGTERM sent:",                    sigterm+0
            printf "  %-38s %d\n", "SIGKILL sent:",                    sigkill+0
            printf "  %-38s %d\n", "Permission violations fixed:",     perm+0
            printf "  %-38s %d\n", "Warnings:",                        warns+0
            printf "  %-38s %d\n", "Errors:",                          errors+0
        }
    ' "$LOG_FILE"

    echo ""
    echo "  Last 10 actions:"
    echo "  ----------------------------------------"
    # Pipe: grep filters ACTION lines -> tail gets last 10 -> awk indents
    grep "\[ACTION\]" "$LOG_FILE" 2>/dev/null \
    | tail -10 \
    | awk '{ print "  " $0 }'
    echo ""
}

# ---------- LOG ROTATION ------------------------------------
# OS Concept: find -mtime + gzip compression
rotate_logs() {
    mkdir -p "$ARCHIVE_DIR"
    echo "[ROTATE] Looking for logs older than $ROTATE_DAYS days..."

    # find locates old logs -> pipe -> while compresses each one
    find "$PROJECT_DIR/logs" -maxdepth 1 -name "*.log" -mtime +"$ROTATE_DAYS" \
    | while IFS= read -r old_log; do
        archive_name="$(basename "$old_log" .log)_$(date '+%Y%m%d').log.gz"
        # gzip -c: write compressed output to stdout -> redirect (>) to archive
        if gzip -c "$old_log" > "$ARCHIVE_DIR/$archive_name" 2>/dev/null; then
            rm -f "$old_log"
            echo "  Archived: $(basename "$old_log") -> $archive_name"
            log "INFO" "Log rotated: $old_log -> $archive_name"
        else
            echo "  ERROR: Could not archive $old_log" >&2
            log "ERROR" "Rotation failed for: $old_log"
        fi
    done
    echo "[ROTATE] Done."
}

# ---------- HTML REPORT -------------------------------------
# OS Concept: sed multi-substitution for HTML formatting
generate_report() {
    local out="$PROJECT_DIR/logs/report_${TODAY}.html"

    # awk extracts counts for the stats cards
    read -r rogue sigterm sigkill perm < <(awk '
        /ROGUE PROCESS/ { rogue++  }
        /SIGTERM sent/  { sigterm++ }
        /SIGKILL sent/  { sigkill++ }
        /PERM FIXED/    { perm++   }
        END { print rogue+0, sigterm+0, sigkill+0, perm+0 }
    ' "$LOG_FILE" 2>/dev/null)

    # sed pipeline: escape HTML special chars, then colorize log levels
    local log_html
    log_html=$(cat "$LOG_FILE" 2>/dev/null \
        | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g' \
        | sed 's/\[WARN\]/<span class="w">[WARN]<\/span>/g'   \
        | sed 's/\[ERROR\]/<span class="e">[ERROR]<\/span>/g' \
        | sed 's/\[ACTION\]/<span class="a">[ACTION]<\/span>/g' \
        | sed 's/\[INFO\]/<span class="i">[INFO]<\/span>/g')

    cat > "$out" <<HTML
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Aegis Report - $TODAY</title>
<style>
  *    { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:'Courier New',monospace; background:#0d1117; color:#c9d1d9; padding:2rem; }
  h1   { color:#58a6ff; border-bottom:2px solid #21262d; padding-bottom:.6rem; margin-bottom:1rem; }
  h2   { color:#79c0ff; margin:2rem 0 .8rem; }
  .meta{ color:#8b949e; font-size:.9rem; margin-bottom:1.5rem; }
  .cards { display:flex; gap:1rem; flex-wrap:wrap; margin:1rem 0 2rem; }
  .card  { background:#161b22; border:1px solid #30363d; border-radius:8px;
           padding:.8rem 1.2rem; min-width:150px; }
  .card .n { font-size:2.4rem; font-weight:bold; color:#58a6ff; }
  .card .l { font-size:.8rem; color:#8b949e; margin-top:.3rem; }
  .team  { background:#161b22; border:1px solid #30363d; border-radius:8px;
           padding:1rem 1.4rem; margin-bottom:1rem; }
  .team h3 { color:#3fb950; margin-bottom:.5rem; }
  .team p  { color:#c9d1d9; font-size:.9rem; line-height:1.7; }
  pre  { background:#161b22; border:1px solid #30363d; border-radius:8px;
         padding:1rem; overflow:auto; font-size:.8rem; line-height:1.7; }
  .w { color:#e3b341; } .e { color:#f85149; }
  .a { color:#3fb950; } .i { color:#8b949e; }
</style>
</head>
<body>
<h1>&#x1F6E1; Project Aegis &mdash; Security Audit Report</h1>
<p class="meta">Generated: $(date '+%Y-%m-%d %H:%M:%S') &nbsp;|&nbsp; Badya University &mdash; OS Lab</p>

<h2>Statistics</h2>
<div class="cards">
  <div class="card"><div class="n">$rogue</div><div class="l">Rogue Processes</div></div>
  <div class="card"><div class="n">$sigterm</div><div class="l">SIGTERM Sent</div></div>
  <div class="card"><div class="n">$sigkill</div><div class="l">SIGKILL Sent</div></div>
  <div class="card"><div class="n">$perm</div><div class="l">Perms Fixed</div></div>
</div>

<h2>Team Members</h2>
<div class="team">
  <h3>Core Logic / SysAdmins</h3>
  <p>Mazen Hesham &nbsp;&bull;&nbsp; Mohamed Arafat &nbsp;&bull;&nbsp; Abdelrahman Mohamed</p>
</div>
<div class="team">
  <h3>Data Wranglers</h3>
  <p>Moaz Ahmed &nbsp;&bull;&nbsp; Ziad Hamed &nbsp;&bull;&nbsp; Mohamed Gamal</p>
</div>
<div class="team">
  <h3>Orchestrators</h3>
  <p>Mohand Mouneer &nbsp;&bull;&nbsp; Huda Ahmed</p>
</div>
<div class="team">
  <h3>Architects / Presenters</h3>
  <p>Lamiaa Mahmoud &nbsp;&bull;&nbsp; Omar Abdelaziz</p>
</div>

<h2>Full Audit Log</h2>
<pre>$log_html</pre>
</body>
</html>
HTML

    echo "[REPORT] Saved -> $out"
    log "INFO" "HTML report generated: $out"
}

# ---------- Entry Point -------------------------------------
mkdir -p "$PROJECT_DIR/logs"

[ $# -eq 0 ] && { show_summary; exit 0; }

for arg in "$@"; do
    case "$arg" in
        --summary) show_summary     ;;
        --rotate)  rotate_logs      ;;
        --report)  generate_report  ;;
        *) echo "Usage: $0 [--summary|--rotate|--report]" >&2; exit 1 ;;
    esac
done
