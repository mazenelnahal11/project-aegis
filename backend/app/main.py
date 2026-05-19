from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routes import act, audit, auth, gates, health, scan


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Aegis Backend", version="0.1.0", lifespan=lifespan)

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

    # LLM routes are optional — only wired if the key is set.
    if settings.llm_enabled:
        from .routes import llm
        app.include_router(llm.router)

    return app


app = create_app()
