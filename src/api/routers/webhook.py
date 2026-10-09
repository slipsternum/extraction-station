from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from telebot.types import Update

from src.core import config
from src.core.logging import logger
from src.api.dependencies import get_bot_context

router = APIRouter(tags=["webhook"])


@router.post(config.WEBHOOK_URL_PATH)
async def telegram_webhook(request: Request, context=Depends(get_bot_context)) -> Response:
    if config.WEBHOOK_SECRET_TOKEN:
        incoming_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if incoming_secret != config.WEBHOOK_SECRET_TOKEN:
            logger.warning("Webhook secret token mismatch.")
            return Response(status_code=403)

    try:
        payload = await request.json()
    except ValueError:
        logger.warning("Webhook payload is not valid JSON.")
        return Response(status_code=400)

    if not payload:
        return Response(status_code=204)

    try:
        update = Update.de_json(payload)
    except ValueError:
        logger.warning("Webhook payload could not be deserialized into Update.")
        return Response(status_code=400)

    await context.bot.process_new_updates([update])
    return Response(status_code=200)


__all__ = ["router"]
