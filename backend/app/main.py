import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .grace import expire_overdue
from .routes import act, audit, auth, gates, grace, health, scan

log = logging.getLogger("aegis.lifespan")


async def _grace_sweeper() -> None:
    """Periodically escalate expired warnings to gates."""
    while True:
        try:
            escalated = await asyncio.to_thread(expire_overdue)
            if escalated:
                log.info("grace sweeper escalated %d warning(s)", len(escalated))
        except Exception:
            log.exception("grace sweeper iteration failed")
        await asyncio.sleep(settings.grace_expiry_check_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sweeper = asyncio.create_task(_grace_sweeper())
    try:
        yield
    finally:
        sweeper.cancel()
        try:
            await sweeper
        except (asyncio.CancelledError, Exception):
            pass


def create_app() -> FastAPI:
    app = FastAPI(title="Aegis Backend", version="0.2.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(scan.router)
    app.include_router(act.router)
    app.include_router(gates.router)
    app.include_router(audit.router)
    app.include_router(audit.ws_router)
    app.include_router(grace.admin_router)
    app.include_router(grace.public_router)

    if settings.llm_enabled:
        from .routes import llm
        app.include_router(llm.router)

    return app


app = create_app()
