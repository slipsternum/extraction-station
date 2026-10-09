from __future__ import annotations

from telebot.async_telebot import AsyncTeleBot, types
from telebot.states.asyncio.context import StateContext as AsyncStateContext

from src.services.notification_service import NotificationService


def register_admin_handlers(
    bot: AsyncTeleBot,
    *,
    notifications: NotificationService,
) -> None:
    """Register admin-only command handlers, gated by the ``isadmin`` filter."""

    @bot.message_handler(commands=["admin"], isadmin=True)
    async def handle_admin(message: types.Message, state: AsyncStateContext):
        await notifications.send_message(message.chat.id, "You are an admin!")


__all__ = ["register_admin_handlers"]
