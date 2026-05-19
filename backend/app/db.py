import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    origin TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    requested_at TEXT NOT NULL,
    executed_at TEXT,
    result_json TEXT,
    chat_session_id TEXT,
    tool_use_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_actions(status);
CREATE INDEX IF NOT EXISTS idx_pending_chat ON pending_actions(chat_session_id);

CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    scanned_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    messages_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grace_warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_kind TEXT NOT NULL,         -- 'kill' | 'fix_permission'
    target_payload TEXT NOT NULL,      -- JSON
    owner_linux_user TEXT,
    owner_slack_id TEXT,
    channel TEXT NOT NULL,             -- 'slack' | 'null'
    reason TEXT NOT NULL,
    ack_token TEXT UNIQUE NOT NULL,
    sent_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent',  -- sent | stop | explained | expired | escalated | failed
    ack_at TEXT,
    ack_action TEXT,                   -- 'stop' | 'explain'
    ack_reason TEXT,
    escalated_gate_id INTEGER REFERENCES pending_actions(id),
    origin TEXT NOT NULL DEFAULT 'ui'  -- 'ui' | 'llm'
);
CREATE INDEX IF NOT EXISTS idx_grace_status_expires ON grace_warnings(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_grace_token ON grace_warnings(ack_token);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_conn: sqlite3.Connection | None = None


def init_db() -> None:
    global _conn
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    _conn = _connect()
    _conn.executescript(SCHEMA)


def conn() -> sqlite3.Connection:
    if _conn is None:
        init_db()
    assert _conn is not None
    return _conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    c = conn()
    c.execute("BEGIN")
    try:
        yield c
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=str)


def loads(s: str | None) -> Any:
    return json.loads(s) if s else None
