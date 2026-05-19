"""Tool definitions exposed to the LLM.

The shapes here are the *security boundary*. Read-only tools execute immediately
and return data. Action tools (`propose_*`) only create gated pending actions.
"""

TOOLS = [
    {
        "name": "list_processes",
        "description": (
            "List currently running processes. Returns pid, user, cpu_pct, mem_pct, "
            "runtime_seconds, command, state, flagged, reasons. Use this to find rogue jobs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "only_flagged": {
                    "type": "boolean",
                    "description": "If true, return only processes that exceed CPU/runtime thresholds.",
                    "default": False,
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            },
        },
    },
    {
        "name": "list_world_writable",
        "description": (
            "Scan a directory for world-writable (chmod 777) files. Returns path, owner, "
            "file_type, recommended_mode. Defaults to /home."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dir": {
                    "type": "string",
                    "description": "Absolute directory to scan (must start with /).",
                    "default": "/home",
                }
            },
        },
    },
    {
        "name": "get_audit_log",
        "description": (
            "Read recent entries from security_audit.log. Useful to answer 'what happened?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
                "since": {
                    "type": "string",
                    "description": "Optional ISO timestamp; only return lines at or after this time.",
                },
            },
        },
    },
    {
        "name": "get_audit_summary",
        "description": "Return aggregate counts: rogue, sigterm, sigkill, perm_fixed, errors, warns.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "propose_kill_process",
        "description": (
            "Propose terminating a process. This DOES NOT kill it — it creates a pending "
            "action the human must approve. Returns gate_id and requires_confirmation=true."
        ),
        "input_schema": {
            "type": "object",
            "required": ["pid", "reason"],
            "properties": {
                "pid": {"type": "integer", "minimum": 2},
                "reason": {
                    "type": "string",
                    "description": "Plain-English justification shown in the confirmation modal.",
                },
            },
        },
    },
    {
        "name": "propose_fix_permission",
        "description": (
            "Propose chmod-ing a world-writable file to safer permissions. Creates a "
            "pending action. Allowed modes: 755, 644, 750, 640, 700, 600."
        ),
        "input_schema": {
            "type": "object",
            "required": ["path", "mode", "reason"],
            "properties": {
                "path": {"type": "string", "description": "Absolute path."},
                "mode": {
                    "type": "string",
                    "enum": ["755", "644", "750", "640", "700", "600"],
                },
                "reason": {"type": "string"},
            },
        },
    },
]
