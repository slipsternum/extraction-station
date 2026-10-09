from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_storage import StatePickleStorage

from src.bot.commands import admin_commands, user_commands
from src.bot.filters import bind_filters
from src.bot.handlers.admin import register_admin_handlers
from src.bot.handlers.beans import register_bean_handlers
from src.bot.handlers.brew import register_brew_handlers
from src.bot.handlers.general import register_general_handlers
from src.bot.handlers.setup import register_setup_handlers
from src.bot.middlewares import bind_middlewares
from src.core import config
from src.core.logging import logger
from src.repositories.async_sqlite_adapter import AsyncSQLiteAdapter
from src.repositories.bean_repository import BeanRepository
from src.repositories.brew_repository import BrewRepository
from src.repositories.equipment_repository import EquipmentRepository
from src.services.bean_service import BeanService
from src.services.brew_service import BrewService
from src.services.llm_service import LLMService
from src.services.notification_service import NotificationService
from src.services.setup_service import SetupService

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
    llm: LLMService
    setup: SetupService
    beans: BeanService
    brews: BrewService


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
    llm = LLMService(
        model=config.OPENAI_MODEL,
        api_key=config.OPENAI_API_KEY,
        base_url=config.OPENAI_BASE_URL,
        timeout=config.OPENAI_TIMEOUT_SECONDS,
    )
    equipment_repo = EquipmentRepository(adapter)
    bean_repo = BeanRepository(adapter)
    brew_repo = BrewRepository(adapter)

    if not llm.enabled:
        logger.warning("OPENAI_MODEL not set; bean label extraction is disabled.")
    logger.info("Services and repositories initialised.")

    return BotContext(
        bot=bot,
        db_adapter=adapter,
        notifications=notifications,
        llm=llm,
        setup=SetupService(equipment_repo),
        beans=BeanService(bot, bean_repo, llm),
        brews=BrewService(bean_repo, brew_repo, equipment_repo),
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
    register_setup_handlers(
        bot,
        notifications=context.notifications,
        setup=context.setup,
    )
    register_bean_handlers(
        bot,
        notifications=context.notifications,
        beans=context.beans,
    )
    register_brew_handlers(
        bot,
        notifications=context.notifications,
        brews=context.brews,
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
