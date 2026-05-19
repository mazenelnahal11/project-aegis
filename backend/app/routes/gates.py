from fastapi import APIRouter, Depends, HTTPException

from ..auth import require_admin
from ..gates import approve_and_execute, get_gate, list_gates, reject_gate

router = APIRouter(prefix="/api/gates", tags=["gates"], dependencies=[Depends(require_admin)])


@router.get("")
def get_pending(status: str | None = None) -> dict:
    return {"gates": list_gates(status=status)}  # type: ignore[arg-type]


@router.get("/{gate_id}")
def get_one(gate_id: int) -> dict:
    try:
        return get_gate(gate_id)
    except KeyError:
        raise HTTPException(404, "not found")


@router.post("/{gate_id}/approve")
def approve(gate_id: int) -> dict:
    try:
        gate = approve_and_execute(gate_id)
    except KeyError:
        raise HTTPException(404, "not found")
    return gate


@router.post("/{gate_id}/reject")
def reject(gate_id: int) -> dict:
    try:
        return reject_gate(gate_id)
    except KeyError:
        raise HTTPException(404, "not found")
