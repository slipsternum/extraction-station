from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_filters import SimpleCustomFilter, StateFilter

from src.core import config


class AdminFilter(SimpleCustomFilter):
    key = "isadmin"

    async def check(self, message) -> bool:
        return bool(message.from_user and message.from_user.id in config.ADMIN_IDS)


class PrivateChatFilter(SimpleCustomFilter):
    key = "isprivchat"

    async def check(self, message) -> bool:
        chat = getattr(message, "chat", None)
        return getattr(chat, "type", None) == "private"


def bind_filters(bot: AsyncTeleBot) -> None:
    bot.add_custom_filter(AdminFilter())
    bot.add_custom_filter(PrivateChatFilter())
    bot.add_custom_filter(StateFilter(bot))


__all__ = ["AdminFilter", "PrivateChatFilter", "bind_filters"]
