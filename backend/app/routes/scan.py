from fastapi import APIRouter, Depends, Query

from ..auth import require_admin
from ..scripts.permissions import scan_world_writable
from ..scripts.process_hunter import list_processes, run_hunter_scan

router = APIRouter(prefix="/api/scan", tags=["scan"], dependencies=[Depends(require_admin)])


@router.get("/processes")
def get_processes(only_flagged: bool = Query(False)) -> dict:
    rows = list_processes(only_flagged=only_flagged)
    return {"processes": [r.model_dump(by_alias=True) for r in rows]}


@router.post("/processes/full")
def run_full_hunter_scan() -> dict:
    """Runs the canonical bash detector (writes audit log entries)."""
    res = run_hunter_scan()
    return res.model_dump(by_alias=True)


@router.get("/permissions")
def get_permissions(dir: str = Query("/home")) -> dict:
    res = scan_world_writable(dir)
    return res.model_dump(by_alias=True)
