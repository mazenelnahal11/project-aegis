from fastapi import APIRouter

from ..config import settings
from ..wsl_bridge import health_check

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "wsl": health_check(),
        "llm_enabled": settings.llm_enabled,
        "llm_provider": settings.llm_provider if settings.llm_enabled else None,
        "llm_model": settings.llm_model if settings.llm_enabled else None,
        "llm_base_url": settings.llm_base_url if settings.llm_enabled else None,
    }
