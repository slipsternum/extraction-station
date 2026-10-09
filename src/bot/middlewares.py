from __future__ import annotations

from datetime import datetime, timedelta, timezone

from telebot.async_telebot import AsyncTeleBot, types
from telebot.asyncio_handler_backends import (
    BaseMiddleware as AsyncBaseMiddleware,
    CancelUpdate as AsyncCancelUpdate,
)
from telebot.states.asyncio.middleware import StateMiddleware as AsyncStateMiddleware

from src.core import config
from src.core.logging import logger

AsyncBot = AsyncTeleBot


class AsyncMessageRateLimit(AsyncBaseMiddleware):
    def __init__(self, limit_seconds: int, bot: AsyncBot) -> None:
        self.limit_seconds = limit_seconds
        self.update_types = ["message"]
        self.bot = bot
        self.last_time: dict[int, int] = {}

    async def pre_process(self, message: types.Message, data):
        if not message.from_user or not message.text or not message.text.startswith("/"):
            return
        if message.from_user.id in config.ADMIN_IDS:
            return
        if getattr(message.chat, "type", None) != "private":
            return

        previous = self.last_time.get(message.from_user.id)
        if previous is None:
            self.last_time[message.from_user.id] = message.date
            return

        elapsed = message.date - previous
        if elapsed < self.limit_seconds:
            logger.debug("Rate limited command from %s", message.from_user.id)
            return AsyncCancelUpdate()
        self.last_time[message.from_user.id] = message.date

    async def post_process(self, message, data, exception):
        return


class AsyncCallbackQueryRateLimit(AsyncBaseMiddleware):
    def __init__(self, limit_seconds: int, bot: AsyncBot) -> None:
        self.limit_seconds = timedelta(seconds=limit_seconds)
        self.update_types = ["callback_query"]
        self.bot = bot
        self.last_time: dict[int, datetime] = {}

    async def pre_process(self, call: types.CallbackQuery, data):
        now = datetime.now(timezone.utc)
        if not call.from_user:
            return
        if call.from_user.id in config.ADMIN_IDS:
            return

        previous = self.last_time.get(call.from_user.id)
        if previous is None:
            self.last_time[call.from_user.id] = now
            return

        elapsed = now - previous
        if elapsed < self.limit_seconds:
            logger.debug("Rate limited callback from %s", call.from_user.id)
            return AsyncCancelUpdate()
        self.last_time[call.from_user.id] = now

    async def post_process(self, call, data, exception):
        return


def bind_middlewares(bot: AsyncBot) -> None:
    """Bind async middlewares for AsyncTeleBot runtime."""
    message_rate_limiter = AsyncMessageRateLimit(
        config.RATE_LIMIT_COMMAND_SECONDS,
        bot,
    )
    callback_rate_limiter = AsyncCallbackQueryRateLimit(
        config.RATE_LIMIT_CALLBACK_SECONDS,
        bot,
    )
    bot.setup_middleware(message_rate_limiter)
    bot.setup_middleware(callback_rate_limiter)
    bot.setup_middleware(AsyncStateMiddleware(bot))


__all__ = [
    "bind_middlewares",
    "AsyncMessageRateLimit",
    "AsyncCallbackQueryRateLimit",
]
