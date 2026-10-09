from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Optional, Union

from telebot import TeleBot, types
from telebot.asyncio_helper import ApiTelegramException
from telebot.async_telebot import AsyncTeleBot

from src.core.logging import logger

BotLike = Union[TeleBot, AsyncTeleBot]
Markup = Optional[types.InlineKeyboardMarkup | types.ReplyKeyboardMarkup]


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
        reply_markup: Markup = None,
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
        reply_markup: Markup = None,
    ) -> types.Message:
        response = await self._call_bot("reply_to", message, text, reply_markup=reply_markup)
        logger.log(f"Replied in chat {message.chat.id}", level="DEBUG")
        return response

    async def answer_callback(
        self, call: types.CallbackQuery, text: Optional[str] = None, *, show_alert: bool = False
    ) -> None:
        await self._call_bot("answer_callback_query", call.id, text, show_alert=show_alert)

    async def _call_edit(self, method_name: str, *args, **kwargs):
        """Call an edit method, treating Telegram's "message is not modified" as a no-op."""
        try:
            return await self._call_bot(method_name, *args, **kwargs)
        except ApiTelegramException as exc:
            if "message is not modified" in str(exc.description):
                return None
            raise

    async def send_photo(
        self,
        chat_id: int,
        photo: str | bytes,
        *,
        caption: Optional[str] = None,
        reply_markup: Markup = None,
    ) -> types.Message:
        message = await self._call_bot("send_photo", chat_id, photo, caption=caption, reply_markup=reply_markup)
        logger.log(f"Sent photo to {chat_id}", level="DEBUG")
        return message

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: Optional[types.InlineKeyboardMarkup] = None,
        disable_web_page_preview: bool = True,
    ) -> types.Message | bool | None:
        return await self._call_edit(
            "edit_message_text",
            text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )

    async def edit_message_caption(
        self,
        chat_id: int,
        message_id: int,
        caption: str,
        *,
        reply_markup: Optional[types.InlineKeyboardMarkup] = None,
    ) -> types.Message | bool | None:
        return await self._call_edit(
            "edit_message_caption",
            caption,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )

    async def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        *,
        reply_markup: Optional[types.InlineKeyboardMarkup] = None,
    ) -> types.Message | bool | None:
        return await self._call_edit(
            "edit_message_reply_markup",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )

    async def edit_message_photo(
        self,
        chat_id: int,
        message_id: int,
        photo: str,
        *,
        caption: Optional[str] = None,
        reply_markup: Optional[types.InlineKeyboardMarkup] = None,
    ) -> types.Message | bool | None:
        media = types.InputMediaPhoto(photo, caption=caption, parse_mode="HTML")
        return await self._call_edit(
            "edit_message_media",
            media,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )

    async def edit_message(
        self,
        message: types.Message,
        text: str,
        *,
        reply_markup: Optional[types.InlineKeyboardMarkup] = None,
    ) -> types.Message | bool | None:
        """Edit a message's visible text, using the caption for photo messages."""
        if message.photo:
            return await self.edit_message_caption(
                message.chat.id, message.message_id, text, reply_markup=reply_markup
            )
        return await self.edit_message_text(
            message.chat.id, message.message_id, text, reply_markup=reply_markup
        )

    async def clear_reply_markup(self, chat_id: int, message_id: int) -> None:
        """Remove inline buttons from an older message, ignoring messages that are gone."""
        try:
            await self.edit_message_reply_markup(chat_id, message_id)
        except ApiTelegramException as exc:
            logger.debug("Could not clear markup on %s/%s: %s", chat_id, message_id, exc.description)

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        try:
            await self._call_bot("delete_message", chat_id, message_id)
        except ApiTelegramException as exc:
            logger.debug("Could not delete %s/%s: %s", chat_id, message_id, exc.description)


__all__ = ["NotificationService"]
