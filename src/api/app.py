from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.core import config
from src.core.bootstrap import ALLOWED_UPDATES, BotContext, bootstrap_bot
from src.core.logging import logger
from src.api.certs import ensure_certs
from src.api.routers import router as api_router


@asynccontextmanager
async def _lifespan(application: FastAPI):
    context = await bootstrap_bot()
    application.state.bot_context = context
    if config.WEBHOOK_URL:
        await _register_webhook(context)
    try:
        yield
    finally:
        await _shutdown_context(context)


async def _register_webhook(context: BotContext) -> None:
    try:
        await context.bot.remove_webhook()
    except Exception as exc:
        logger.warning(f"Failed to clear existing webhook: {exc}")

    if not config.WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not configured; skipping Telegram webhook registration.")
        return

    webhook_kwargs: dict[str, object] = {
        "url": config.WEBHOOK_URL,
        "allowed_updates": ALLOWED_UPDATES,
    }
    certificate_file = None
    if config.WEBHOOK_SECRET_TOKEN:
        webhook_kwargs["secret_token"] = config.WEBHOOK_SECRET_TOKEN
    try:
        if config.WEBHOOK_SSL_CERT:
            certificate_file = open(config.WEBHOOK_SSL_CERT, "r")
            webhook_kwargs["certificate"] = certificate_file
        await context.bot.set_webhook(**webhook_kwargs)
        logger.info(f"Webhook registered at {config.WEBHOOK_URL}")
    except Exception as exc:
        logger.error(f"Failed to register webhook with Telegram: {exc}")
    finally:
        if certificate_file is not None:
            certificate_file.close()


async def _shutdown_context(context: BotContext) -> None:
    try:
        await context.bot.remove_webhook()
    except Exception as exc:
        logger.warning(f"Failed to remove webhook during shutdown: {exc}")
    try:
        await context.bot.close_session()
    except Exception as exc:
        logger.warning(f"Failed to close bot session: {exc}")
    await context.db_adapter.close()
    await logger.flush()
    await logger.shutdown()


app = FastAPI(docs_url=None, redoc_url=None, lifespan=_lifespan)
app.include_router(api_router)


async def _polling_main() -> None:
    context = await bootstrap_bot()
    try:
        try:
            await context.bot.remove_webhook()
        except Exception as exc:
            logger.warning(f"Failed to clear webhook before polling start: {exc}")
        await context.bot.infinity_polling(allowed_updates=ALLOWED_UPDATES)
    finally:
        await _shutdown_context(context)


def _build_uvicorn_log_config() -> dict:
    """Return a uvicorn logging config that routes its logs to stderr."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(levelprefix)s %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO"},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["default"], "level": "INFO"},
        },
    }


def run() -> None:
    if config.USE_POLLING:
        logger.log("USE_POLLING enabled; starting bot in polling mode.")
        try:
            asyncio.run(_polling_main())
        except KeyboardInterrupt:
            logger.log("Polling interrupted by user.")
        return

    ensure_certs()

    uvicorn_kwargs: dict[str, object] = {
        "app": app,
        "host": config.WEBHOOK_LISTEN,
        "port": config.WEBHOOK_LISTEN_PORT,
    }
    if config.WEBHOOK_SSL_CERT and config.WEBHOOK_SSL_PRIV:
        uvicorn_kwargs["ssl_certfile"] = config.WEBHOOK_SSL_CERT
        uvicorn_kwargs["ssl_keyfile"] = config.WEBHOOK_SSL_PRIV
    uvicorn_kwargs["log_config"] = _build_uvicorn_log_config()
    uvicorn.run(**uvicorn_kwargs)


__all__ = ["app", "run"]
