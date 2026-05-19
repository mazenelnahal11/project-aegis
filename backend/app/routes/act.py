from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import require_admin
from ..gates import create_gate
from ..grace import create_warning
from ..scripts.process_hunter import list_processes

router = APIRouter(prefix="/api/act", tags=["act"], dependencies=[Depends(require_admin)])


class KillBody(BaseModel):
    pid: int = Field(gt=0)
    reason: str = ""
    mode: Literal["immediate", "warn_then_kill"] = "immediate"
    grace_minutes: int | None = None  # only used in warn_then_kill


class FixPermissionBody(BaseModel):
    path: str
    mode: str = "755"
    reason: str = ""


def _owner_of(pid: int) -> str:
    """Look up the Linux owner of a PID via the cached process listing."""
    for p in list_processes():
        if p.pid == pid:
            return p.user
    return "(unknown)"


@router.post("/kill")
def request_kill(body: KillBody) -> dict:
    if body.mode == "warn_then_kill":
        owner = _owner_of(body.pid)
        w = create_warning(
            target_kind="kill",
            target_payload={"pid": body.pid},
            owner_linux_user=owner,
            reason=body.reason or "exceeds policy thresholds",
            grace_minutes=body.grace_minutes,
            origin="ui",
        )
        return {
            "warning_id": w["id"],
            "owner": owner,
            "expires_at": w["expires_at"],
            "channel": w["channel"],
            "summary": f"warn user '{owner}' then kill PID {body.pid} after grace period",
        }

    gate = create_gate(
        kind="kill",
        payload={"pid": body.pid, "reason": body.reason},
        origin="ui",
    )
    return {"gate_id": gate["id"], "summary": f"kill -15 {body.pid}; sleep 10; kill -9 {body.pid} (if alive)"}


@router.post("/fix-permission")
def request_fix(body: FixPermissionBody) -> dict:
    if body.mode not in {"755", "644", "750", "640", "700", "600"}:
        raise HTTPException(400, "disallowed mode")
    gate = create_gate(
        kind="fix_permission",
        payload={"path": body.path, "mode": body.mode, "reason": body.reason},
        origin="ui",
    )
    return {
        "gate_id": gate["id"],
        "summary": f"chmod {body.mode} {body.path}",
    }
