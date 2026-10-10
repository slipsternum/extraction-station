from __future__ import annotations

from typing import Any, Optional

from telebot import types

from src.repositories.brew_repository import BrewRepository
from src.services.notification_service import NotificationService
from src.utils.text import ProgressText


class ProgressService:
    """Posts a progress card (photos + recipe) for each saved brew to a configured chat/topic."""

    def __init__(
        self,
        notifications: NotificationService,
        brews: BrewRepository,
        *,
        chat_id: int | str | None,
        thread_id: Optional[int] = None,
    ) -> None:
        self.notifications = notifications
        self.brews = brews
        self.chat_id = chat_id
        self.thread_id = thread_id

    @property
    def enabled(self) -> bool:
        return self.chat_id is not None

    async def post(
        self,
        user_id: int,
        brew_id: int,
        draft: dict[str, Any],
        ctx: dict[str, Any],
    ) -> None:
        attempt = await self.brews.count(user_id, draft["bean_id"], draft["method"])
        history = await self.brews.history(user_id, draft["bean_id"], draft["method"], limit=2)
        previous = next((brew for brew in history if brew.id != brew_id), None)
        caption = ProgressText.caption(draft, ctx, attempt=attempt, previous=previous)

        bean = next((b for b in ctx["beans"] if b["id"] == draft["bean_id"]), {})
        photos = [p for p in (draft.get("photo_file_id"), bean.get("photo_file_id")) if p]
        if len(photos) > 1:
            media = [types.InputMediaPhoto(photos[0], caption=caption, parse_mode="HTML")]
            media += [types.InputMediaPhoto(photo) for photo in photos[1:]]
            await self.notifications.send_media_group(self.chat_id, media, message_thread_id=self.thread_id)
        elif photos:
            await self.notifications.send_photo(
                self.chat_id, photos[0], caption=caption, message_thread_id=self.thread_id
            )
        else:
            await self.notifications.send_message(self.chat_id, caption, message_thread_id=self.thread_id)


__all__ = ["ProgressService"]
