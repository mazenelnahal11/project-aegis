from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import require_admin
from ..gates import create_gate

router = APIRouter(prefix="/api/act", tags=["act"], dependencies=[Depends(require_admin)])


class KillBody(BaseModel):
    pid: int = Field(gt=0)
    reason: str = ""


class FixPermissionBody(BaseModel):
    path: str
    mode: str = "755"
    reason: str = ""


@router.post("/kill")
def request_kill(body: KillBody) -> dict:
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
