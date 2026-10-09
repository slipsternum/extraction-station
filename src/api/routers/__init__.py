from fastapi import APIRouter

from src.api.routers.health import router as health_router
from src.api.routers.webhook import router as webhook_router

router = APIRouter()
router.include_router(health_router)
router.include_router(webhook_router)

__all__ = ["router"]
