from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Optional, Union

from telebot import TeleBot, types
from telebot.async_telebot import AsyncTeleBot

from src.core.logging import logger

BotLike = Union[TeleBot, AsyncTeleBot]


@dataclass
class NotificationService:
    bot: BotLike

    async def _call_bot(self, method_name: str, *args, **kwargs):
        bot_method = getattr(self.bot, method_name)
        if inspect.iscoroutinefunction(bot_method):
            return await bot_method(*args, **kwargs)
        return bot_method(*args, **kwargs)

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: Optional[types.InlineKeyboardMarkup | types.ReplyKeyboardMarkup] = None,
        disable_web_page_preview: bool = True,
    ) -> types.Message:
        message = await self._call_bot(
            "send_message",
            chat_id,
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )
        logger.log(f"Sent message to {chat_id}", level="DEBUG")
        return message

    async def reply(
        self,
        message: types.Message,
        text: str,
        *,
        reply_markup: Optional[types.InlineKeyboardMarkup | types.ReplyKeyboardMarkup] = None,
    ) -> types.Message:
        response = await self._call_bot("reply_to", message, text, reply_markup=reply_markup)
        logger.log(f"Replied in chat {message.chat.id}", level="DEBUG")
        return response

    async def answer_callback(self, call: types.CallbackQuery, text: str, *, show_alert: bool = False) -> None:
        await self._call_bot("answer_callback_query", call.id, text, show_alert=show_alert)


__all__ = ["NotificationService"]
