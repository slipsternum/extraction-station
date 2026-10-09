from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_storage import StatePickleStorage

from src.bot.commands import admin_commands, user_commands
from src.bot.filters import bind_filters
from src.bot.handlers.admin import register_admin_handlers
from src.bot.handlers.general import register_general_handlers
from src.bot.middlewares import bind_middlewares
from src.core import config
from src.core.logging import logger
from src.repositories.async_sqlite_adapter import AsyncSQLiteAdapter
from src.services.notification_service import NotificationService

ALLOWED_UPDATES = [
    "message",
    "edited_message",
    "callback_query",
    "poll",
    "poll_answer",
    "message_reaction",
]


@dataclass(slots=True)
class BotContext:
    bot: AsyncTeleBot
    db_adapter: AsyncSQLiteAdapter
    notifications: NotificationService


def _ensure_directories() -> None:
    Path(config.SQLITE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(config.STATE_STORAGE_PATH).parent.mkdir(parents=True, exist_ok=True)


def create_bot() -> AsyncTeleBot:
    _ensure_directories()
    state_storage = StatePickleStorage(config.STATE_STORAGE_PATH)
    bot = AsyncTeleBot(
        config.BOT_TOKEN,
        state_storage=state_storage,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    return bot


async def configure_bot(bot: AsyncTeleBot) -> None:
    await logger.init(bot)
    await bot.set_my_commands(
        list(user_commands.commands),
        scope=user_commands.scope,
    )
    await bot.set_my_commands(
        list(admin_commands.commands),
        scope=admin_commands.scope,
    )
    bind_filters(bot)
    bind_middlewares(bot)
    logger.info("Bot configured with commands, filters, and middlewares.")


async def bootstrap_services(bot: AsyncTeleBot) -> BotContext:
    adapter = AsyncSQLiteAdapter(config.SQLITE_DB_PATH, config.SQLITE_SCHEMA_PATH)
    await adapter.connect()

    notifications = NotificationService(bot)

    logger.info("Services and repositories initialised.")

    return BotContext(
        bot=bot,
        db_adapter=adapter,
        notifications=notifications,
    )


def register_handlers(context: BotContext) -> None:
    bot = context.bot
    register_general_handlers(
        bot,
        notifications=context.notifications,
    )
    register_admin_handlers(
        bot,
        notifications=context.notifications,
    )


async def bootstrap_bot() -> BotContext:
    bot = create_bot()
    await configure_bot(bot)
    context = await bootstrap_services(bot)
    register_handlers(context)
    return context


__all__ = [
    "ALLOWED_UPDATES",
    "BotContext",
    "bootstrap_bot",
    "configure_bot",
    "create_bot",
    "register_handlers",
]
