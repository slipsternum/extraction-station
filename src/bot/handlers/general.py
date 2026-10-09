from __future__ import annotations

from telebot.async_telebot import AsyncTeleBot, types
from telebot.states.asyncio.context import StateContext as AsyncStateContext

from src.services.notification_service import NotificationService
from src.utils.text import HelpText, WelcomeText


def register_general_handlers(
    bot: AsyncTeleBot,
    *,
    notifications: NotificationService,
) -> None:

    @bot.message_handler(commands=["start"], isadmin=True, isprivchat=True)
    async def handle_start(message: types.Message, state: AsyncStateContext):
        await notifications.send_message(
            message.chat.id,
            WelcomeText.greeting(message.from_user),
        )

    @bot.message_handler(commands=["help"], isadmin=True, isprivchat=True)
    async def handle_help(message: types.Message, state: AsyncStateContext):
        await notifications.send_message(
            message.chat.id,
            HelpText.help_message(),
        )

    @bot.message_handler(commands=["ping"], isadmin=True, isprivchat=True)
    async def handle_ping(message: types.Message, state: AsyncStateContext):
        await notifications.send_message(message.chat.id, "pong")

    @bot.message_handler(commands=["cancel"], isadmin=True, isprivchat=True)
    async def handle_cancel(message: types.Message, state: AsyncStateContext):
        await state.delete()
        await notifications.send_message(message.chat.id, WelcomeText.cancelled())


__all__ = ["register_general_handlers"]
