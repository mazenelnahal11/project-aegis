"""Grace-period routes.

- `GET /api/grace` (admin) — list warnings for the dashboard.
- `GET /api/grace/ack/{token}` (public) — HTML landing page for the recipient.
- `POST /api/grace/ack/{token}` (public) — record STOP or EXPLAIN.

The ack endpoints are PUBLIC because they're triggered from a Slack DM link
the recipient gets. Security model: knowing the token is the auth.
Tokens are 24-byte URL-safe random (~192 bits of entropy), single-use, and
constrained by `status='sent'` so replay does nothing.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse

from ..auth import require_admin
from ..grace import acknowledge, get_by_token, list_warnings

admin_router = APIRouter(prefix="/api/grace", tags=["grace"], dependencies=[Depends(require_admin)])
public_router = APIRouter(prefix="/api/grace", tags=["grace-public"])


@admin_router.get("")
def get_warnings(status: str | None = Query(None)) -> dict:
    return {"warnings": list_warnings(status=status)}  # type: ignore[arg-type]


_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><title>Aegis — acknowledge</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family:-apple-system,Segoe UI,Roboto,sans-serif;
         background:#0d1117; color:#c9d1d9; margin:0; padding:2rem;
         display:flex; min-height:100vh; align-items:center; justify-content:center; }}
  .card {{ background:#161b22; border:1px solid #30363d; border-radius:10px;
          padding:2rem; max-width:520px; width:100%; }}
  h1   {{ color:#58a6ff; margin:0 0 .5rem; font-size:1.3rem; }}
  .meta {{ color:#8b949e; font-size:.9rem; margin-bottom:1rem; }}
  .row {{ background:#0d1117; border:1px solid #30363d; border-radius:6px;
         padding:.6rem .9rem; margin-bottom:.6rem; font-family:ui-monospace,monospace; font-size:.85rem; }}
  textarea {{ width:100%; min-height:80px; background:#0d1117; color:#c9d1d9;
             border:1px solid #30363d; border-radius:6px; padding:.6rem;
             font-family:inherit; font-size:.9rem; box-sizing:border-box; }}
  .btns  {{ display:flex; gap:.6rem; margin-top:1rem; }}
  button {{ flex:1; padding:.7rem; border-radius:6px; border:0; font-weight:600;
           font-size:.95rem; cursor:pointer; }}
  .stop  {{ background:#e3b341; color:#0d1117; }}
  .keep  {{ background:#3fb950; color:#0d1117; }}
  .gone  {{ color:#f85149; text-align:center; font-weight:600; }}
  .ok    {{ color:#3fb950; text-align:center; font-weight:600; }}
</style></head><body><div class="card">
  <h1>🛡  Aegis — process flagged</h1>
  <div class="meta">A process registered to <b>{user}</b> exceeded the
       shared-server policy. Choose one:</div>
  <div class="row"><b>Action:</b> {summary}</div>
  <div class="row"><b>Reason:</b> {reason}</div>
  <div class="row"><b>Deadline:</b> {deadline}</div>
  {body}
</div></body></html>
"""


def _render_form(w) -> str:
    return _PAGE.format(
        user=w["owner_linux_user"] or "(unknown)",
        summary=_action_text(w),
        reason=w["reason"],
        deadline=w["expires_at"],
        body=f"""
  <form method="POST" action="/api/grace/ack/{w['ack_token']}">
    <label style="display:block; color:#8b949e; font-size:.9rem; margin-bottom:.3rem;">
      Optional: why is this needed?
    </label>
    <textarea name="reason" placeholder="e.g. GPU benchmark, finishes by 03:00 UTC"></textarea>
    <div class="btns">
      <button class="stop"  name="action" value="stop">STOP — kill in {{m}} min unless I extend</button>
      <button class="keep"  name="action" value="explain">KEEP — explain &amp; let it finish</button>
    </div>
  </form>
        """.replace("{m}", "30"),
    )


def _render_done(w, message: str, tone: str = "ok") -> str:
    return _PAGE.format(
        user=w["owner_linux_user"] or "(unknown)",
        summary=_action_text(w),
        reason=w["reason"],
        deadline=w["expires_at"],
        body=f'<div class="{tone}">{message}</div>',
    )


def _action_text(w) -> str:
    p = w["target_payload"]
    if w["target_kind"] == "kill":
        return f"Terminate PID {p.get('pid')}"
    if w["target_kind"] == "fix_permission":
        return f"chmod {p.get('mode')} {p.get('path')}"
    return f"{w['target_kind']} {p}"


@public_router.get("/ack/{token}", response_class=HTMLResponse)
def ack_landing(token: str) -> HTMLResponse:
    try:
        w = get_by_token(token)
    except KeyError:
        raise HTTPException(404, "unknown or expired link")
    if w["status"] != "sent":
        msg_map = {
            "stop":       "Already acknowledged. Your process is scheduled to be terminated.",
            "explained":  "Already acknowledged with an explanation. Your process will keep running.",
            "expired":    "This warning has expired.",
            "escalated":  "This warning expired and was escalated to an admin.",
            "failed":     "This warning failed to send.",
        }
        return HTMLResponse(_render_done(w, msg_map.get(w["status"], "Already handled."), tone="gone"))
    return HTMLResponse(_render_form(w))


@public_router.post("/ack/{token}", response_class=HTMLResponse)
def ack_submit(token: str, action: str = Form(...), reason: str = Form("")) -> HTMLResponse:
    if action not in {"stop", "explain"}:
        raise HTTPException(400, "bad action")
    try:
        w = acknowledge(token, action=action, reason=reason or None)  # type: ignore[arg-type]
    except KeyError:
        raise HTTPException(404, "unknown or expired link")
    if w["status"] == "stop":
        msg = "Got it. An admin will be asked to approve the kill shortly."
    elif w["status"] == "explained":
        msg = "Thanks — your process will keep running. Reason recorded in the audit log."
    else:
        msg = f"Recorded (status: {w['status']})."
    return HTMLResponse(_render_done(w, msg, tone="ok"))
