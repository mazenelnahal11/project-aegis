import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, PlainTextResponse

from ..auth import COOKIE_NAME, decode_token, require_admin
from ..config import settings
from ..scripts.audit import generate_html_report, read_audit_lines, summary_counts
from ..wsl_bridge import run_inline

router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("/log")
def get_log(limit: int = Query(500, le=5000), since: str | None = None) -> dict:
    lines = read_audit_lines(limit=limit, since=since)
    return {"lines": [line.model_dump() for line in lines]}


@router.get("/summary")
def get_summary() -> dict:
    return summary_counts()


@router.get("/report", response_class=HTMLResponse)
def get_report() -> HTMLResponse:
    html = generate_html_report()
    return HTMLResponse(content=html)


ws_router = APIRouter(tags=["audit-ws"])


@ws_router.websocket("/ws/audit")
async def audit_stream(ws: WebSocket) -> None:
    """Live-tail security_audit.log. First message from the client must be the JWT.

    We spawn `tail -F` inside WSL and pump each new line out over the socket.
    """
    await ws.accept()
    try:
        token = await asyncio.wait_for(ws.receive_text(), timeout=5.0)
        decode_token(token)
    except Exception:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    import shutil
    import subprocess

    exe = shutil.which("wsl.exe") or shutil.which("wsl")
    if not exe:
        await ws.send_json({"type": "error", "message": "wsl.exe not available"})
        await ws.close()
        return

    log_path = f"{settings.project_dir_wsl}/logs/security_audit.log"
    proc = subprocess.Popen(
        [exe, "-d", settings.wsl_distro, "--", "tail", "-n", "0", "-F", log_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    loop = asyncio.get_event_loop()
    try:
        while True:
            assert proc.stdout is not None
            line = await loop.run_in_executor(None, proc.stdout.readline)
            if not line:
                break
            await ws.send_json({"type": "line", "raw": line.rstrip("\n")})
    except WebSocketDisconnect:
        pass
    finally:
        proc.terminate()
