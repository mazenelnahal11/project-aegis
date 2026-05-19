# Project Aegis

A Linux system-security and resource-auditing toolkit, with a web dashboard and an
LLM copilot. The original bash pipeline (process hunter, terminator, permission
auditor, audit logger) remains the only thing that touches the OS; the web and LLM
layers are planners and presenters. Every destructive action passes through an
explicit human confirmation gate.

> Coursework project for the Operating Systems lab at Badya University.

## Architecture

```
┌──────────────────────────┐        ┌────────────────────────────┐
│  React + Vite + Tailwind  │  HTTP  │       FastAPI backend       │
│  - Dashboard tables       │◀──────▶│  - REST + WebSocket         │
│  - LLM chat panel         │   WS   │  - JWT auth + SQLite gates  │
│  - Confirmation modals    │        │  - Claude API (tool use)    │
└──────────────────────────┘        └─────────────┬──────────────┘
                                                  │ subprocess
                                                  ▼
                                    ┌────────────────────────────┐
                                    │  WSL bridge (wsl.exe)      │
                                    │  bash scripts (unchanged): │
                                    │   1_process_hunter.sh      │
                                    │   2_terminator.sh          │
                                    │   3_permission_auditor.sh  │
                                    │   4_audit_logger.sh        │
                                    └────────────────────────────┘
```

## Repository layout

```
aegis_master.sh, demo_setup.sh, scripts/   ← original bash pipeline (untouched)
backend/                                    ← FastAPI app + tests
frontend/                                   ← React/Vite dashboard
docs/                                       ← course report
logs/                                       ← created at runtime
```

## Prerequisites

- Windows 10/11 with **WSL 2** and an **Ubuntu** distro installed
  (`wsl --install -d Ubuntu`).
- Python **3.11+** on Windows.
- Node.js **20+** on Windows.
- (Optional) `ANTHROPIC_API_KEY` for the Copilot tab.

## One-time setup

```bash
# 1. Backend deps
cd backend
python -m pip install -e ".[dev]"

# 2. Frontend deps
cd ../frontend
npm install

# 3. Backend env
cd ../backend
cp .env.example .env
# Generate an admin password hash:
python -c "from app.auth import hash_password; print(hash_password('your-password'))"
# Paste that into AEGIS_ADMIN_PASSWORD_HASH.
# Also fill in AEGIS_JWT_SECRET (any random ~48-char string).
# Optionally fill in ANTHROPIC_API_KEY to enable the Copilot.
```

## Run

In **two terminals**:

```bash
# Terminal A — backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal B — frontend
cd frontend
npm run dev
# open http://localhost:5173
```

## Demo flow

```bash
# Inside WSL, spawn synthetic rogue processes + world-writable files
cd /mnt/c/Users/mazen/Downloads/aegis_final
./demo_setup.sh
```

1. Sign in at `http://localhost:5173` with the admin password you set.
2. **Processes** page — find the flagged demo process, click **Terminate**, approve.
3. **Permissions** page — scan `/tmp/aegis_demo/home_mock`, click **Fix**, approve.
4. **Audit Log** page — watch entries stream in via WebSocket.
5. **Copilot** tab — ask: *"who is hogging the CPU right now? if anyone has been
   running for more than 24 hours, propose killing them."* Approve the proposal
   when the modal appears.

Cleanup: `./demo_setup.sh --cleanup`

## Backend tests

```bash
cd backend
python -m pytest
```

All 23 tests are unit tests with WSL and Anthropic mocked, so they pass without
WSL or an API key.

## Security notes

- The web layer never invokes a free-text shell; all WSL calls go through an
  argv-list allowlist.
- LLM tool calls are statically typed; `propose_*` tools only create pending
  gates, they never execute.
- Path inputs to chmod are validated against a strict regex and reject `..`
  traversal.
- JWT lives in an httpOnly, SameSite=Strict cookie.

## What's where

| Concern | File |
|---|---|
| WSL chokepoint | [backend/app/wsl_bridge.py](backend/app/wsl_bridge.py) |
| Tool schemas (the LLM security boundary) | [backend/app/llm/tools.py](backend/app/llm/tools.py) |
| Gate-enforcing tool dispatcher | [backend/app/llm/executor.py](backend/app/llm/executor.py) |
| Confirmation contract | [backend/app/gates.py](backend/app/gates.py), [backend/app/routes/gates.py](backend/app/routes/gates.py) |
| Per-PID terminator | [backend/app/scripts/terminator.py](backend/app/scripts/terminator.py) |
| Per-path permission fix | [backend/app/scripts/permissions.py](backend/app/scripts/permissions.py) |
| Confirmation modal | [frontend/src/components/ConfirmGateModal.tsx](frontend/src/components/ConfirmGateModal.tsx) |
| Copilot UI | [frontend/src/pages/Copilot.tsx](frontend/src/pages/Copilot.tsx) |
