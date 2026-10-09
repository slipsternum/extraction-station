from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

from telebot.async_telebot import AsyncTeleBot, types
from telebot.states.asyncio.context import StateContext as AsyncStateContext

from src.bot.keyboards import callback_arg, callback_prefix, chunk, inline, is_plain_text
from src.core.logging import logger
from src.core.states import BeanStates
from src.services.bean_service import BEAN_FIELDS, BeanService
from src.services.notification_service import NotificationService
from src.utils.parsing import parse_date, split_notes
from src.utils.text import BeanText, bean_label


def _review_markup() -> types.InlineKeyboardMarkup:
    edits = [(f"✏️ {BeanText.FIELD_LABELS[f]}", f"bean:edit:{f}") for f in BEAN_FIELDS]
    return inline([[("✅ Save", "bean:save")], *chunk(edits, 2), [("✖ Cancel", "bean:cancel")]])


def register_bean_handlers(
    bot: AsyncTeleBot,
    *,
    notifications: NotificationService,
    beans: BeanService,
) -> None:

    async def show_review(
        chat_id: int,
        state: AsyncStateContext,
        draft: dict[str, Any],
        *,
        call: Optional[types.CallbackQuery] = None,
        header: Optional[str] = None,
    ) -> None:
        """Render the draft card: edit it in place on a button tap, else send a fresh card."""
        text = BeanText.card(draft, header=header or BeanText.review_header())
        await state.set(BeanStates.review)
        if call:
            await notifications.edit_message(call.message, text, reply_markup=_review_markup())
            return
        async with state.data() as data:
            old_panel = data.get("bean_panel")
        if old_panel:
            await notifications.clear_reply_markup(chat_id, old_panel)
        if draft.get("photo_file_id"):
            sent = await notifications.send_photo(
                chat_id, draft["photo_file_id"], caption=text, reply_markup=_review_markup()
            )
        else:
            sent = await notifications.send_message(chat_id, text, reply_markup=_review_markup())
        await state.add_data(bean_draft=draft, bean_panel=sent.message_id)

    async def is_current_panel(call: types.CallbackQuery, state: AsyncStateContext) -> bool:
        async with state.data() as data:
            panel = data.get("bean_panel")
        if panel != call.message.message_id:
            await notifications.answer_callback(call, "This card is out of date.")
            return False
        return True

    async def extract(chat_id: int, run) -> tuple[dict[str, Any], bool]:
        notice = await notifications.send_message(chat_id, BeanText.reading())
        try:
            return await run(), True
        except Exception as exc:
            logger.warning("Bean label extraction failed: %s", exc, exc_info=exc)
            return {}, False
        finally:
            await notifications.delete_message(chat_id, notice.message_id)

    @bot.message_handler(commands=["newbean"], isadmin=True, isprivchat=True)
    async def handle_newbean(message: types.Message, state: AsyncStateContext):
        await state.delete()
        await state.set(BeanStates.capture)
        await notifications.send_message(message.chat.id, BeanText.capture_prompt(beans.extraction_enabled))

    @bot.message_handler(state=BeanStates.capture, content_types=["photo"], isadmin=True, isprivchat=True)
    async def on_bag_photo(message: types.Message, state: AsyncStateContext):
        file_id = message.photo[-1].file_id
        draft: dict[str, Any] = {}
        ok = True
        if beans.extraction_enabled:
            draft, ok = await extract(message.chat.id, lambda: beans.extract_from_photo(file_id, message.caption))
        elif message.caption:
            draft = {"name": message.caption.strip()[:80]}
        draft["photo_file_id"] = file_id
        header = BeanText.manual_header() if not beans.extraction_enabled else None
        header = header if ok else BeanText.extraction_failed()
        await show_review(message.chat.id, state, draft, header=header)

    @bot.message_handler(
        state=BeanStates.capture, func=is_plain_text, content_types=["text"], isadmin=True, isprivchat=True
    )
    async def on_bag_text(message: types.Message, state: AsyncStateContext):
        draft: dict[str, Any] = {}
        if beans.extraction_enabled:
            draft, _ = await extract(message.chat.id, lambda: beans.extract_from_text(message.text))
        if not any(draft.values()):
            draft = {"name": message.text.strip()[:80]}
        await show_review(message.chat.id, state, draft)

    @bot.callback_query_handler(func=callback_prefix("bean:edit:"), state=BeanStates.review, isadmin=True)
    async def on_edit(call: types.CallbackQuery, state: AsyncStateContext):
        if not await is_current_panel(call, state):
            return
        field = callback_arg(call)
        if field not in BEAN_FIELDS:
            await notifications.answer_callback(call)
            return
        await state.set(BeanStates.edit_field)
        await state.add_data(bean_field=field)
        markup = inline([[("⬅ Back", "bean:back")]])
        await notifications.edit_message(call.message, BeanText.ask_field(field), reply_markup=markup)
        await notifications.answer_callback(call)

    @bot.callback_query_handler(func=callback_prefix("bean:back"), state=BeanStates.edit_field, isadmin=True)
    async def on_back(call: types.CallbackQuery, state: AsyncStateContext):
        if not await is_current_panel(call, state):
            return
        async with state.data() as data:
            draft = dict(data.get("bean_draft") or {})
        await show_review(call.message.chat.id, state, draft, call=call)
        await notifications.answer_callback(call)

    @bot.message_handler(
        state=BeanStates.edit_field, func=is_plain_text, content_types=["text"], isadmin=True, isprivchat=True
    )
    async def on_field_value(message: types.Message, state: AsyncStateContext):
        async with state.data() as data:
            draft = dict(data.get("bean_draft") or {})
            field = data.get("bean_field")
        text = message.text.strip()
        if text == "-":
            draft[field] = [] if field == "tasting_notes" else None
        elif field == "tasting_notes":
            draft[field] = split_notes(text)
        elif field == "roast_date":
            parsed = parse_date(text)
            if parsed is None:
                await notifications.send_message(message.chat.id, BeanText.bad_date())
                return
            draft[field] = parsed.isoformat()
        else:
            draft[field] = text[:80]
        await state.add_data(bean_draft=draft)
        await show_review(message.chat.id, state, draft)

    @bot.callback_query_handler(func=callback_prefix("bean:save"), state=BeanStates.review, isadmin=True)
    async def on_save(call: types.CallbackQuery, state: AsyncStateContext):
        if not await is_current_panel(call, state):
            return
        async with state.data() as data:
            draft = dict(data.get("bean_draft") or {})
        bean = await beans.save_draft(call.from_user.id, draft)
        await state.delete()
        text = BeanText.card(asdict(bean), header=BeanText.saved(asdict(bean)))
        await notifications.edit_message(call.message, text)
        await notifications.answer_callback(call, "Saved")

    @bot.callback_query_handler(func=callback_prefix("bean:cancel"), state=BeanStates.review, isadmin=True)
    async def on_cancel(call: types.CallbackQuery, state: AsyncStateContext):
        if not await is_current_panel(call, state):
            return
        await state.delete()
        await notifications.edit_message(call.message, "Discarded.")
        await notifications.answer_callback(call)

    @bot.message_handler(commands=["beans"], isadmin=True, isprivchat=True)
    async def handle_beans(message: types.Message, state: AsyncStateContext):
        items = await beans.list_active(message.from_user.id)
        rows = [[(bean_label(asdict(bean))[:60], f"bean:view:{bean.id}")] for bean in items]
        await notifications.send_message(
            message.chat.id, BeanText.list_header(len(items)), reply_markup=inline(rows) if rows else None
        )

    @bot.callback_query_handler(func=callback_prefix("bean:view:"), isadmin=True)
    async def on_view(call: types.CallbackQuery, state: AsyncStateContext):
        bean = await beans.get(call.from_user.id, int(callback_arg(call)))
        if bean is None:
            await notifications.answer_callback(call, "Not found")
            return
        markup = inline([[("🗄 Archive (bag finished)", f"bean:archive:{bean.id}")]])
        text = BeanText.card(asdict(bean))
        if bean.photo_file_id:
            await notifications.send_photo(call.message.chat.id, bean.photo_file_id, caption=text, reply_markup=markup)
        else:
            await notifications.send_message(call.message.chat.id, text, reply_markup=markup)
        await notifications.answer_callback(call)

    @bot.callback_query_handler(func=callback_prefix("bean:archive:"), isadmin=True)
    async def on_archive(call: types.CallbackQuery, state: AsyncStateContext):
        bean_id = int(callback_arg(call))
        await beans.set_archived(call.from_user.id, bean_id, True)
        bean = await beans.get(call.from_user.id, bean_id)
        markup = inline([[("↩ Undo", f"bean:restore:{bean_id}")]])
        text = BeanText.card(asdict(bean), header="🗄 Archived") if bean else "🗄 Archived"
        await notifications.edit_message(call.message, text, reply_markup=markup)
        await notifications.answer_callback(call)

    @bot.callback_query_handler(func=callback_prefix("bean:restore:"), isadmin=True)
    async def on_restore(call: types.CallbackQuery, state: AsyncStateContext):
        bean_id = int(callback_arg(call))
        await beans.set_archived(call.from_user.id, bean_id, False)
        bean = await beans.get(call.from_user.id, bean_id)
        markup = inline([[("🗄 Archive (bag finished)", f"bean:archive:{bean_id}")]])
        text = BeanText.card(asdict(bean)) if bean else "Restored"
        await notifications.edit_message(call.message, text, reply_markup=markup)
        await notifications.answer_callback(call, "Restored")

    @bot.callback_query_handler(func=callback_prefix("bean:"), isadmin=True)
    async def on_stale(call: types.CallbackQuery, state: AsyncStateContext):
        await notifications.answer_callback(call, "This card has expired. Start again with /newbean.")


__all__ = ["register_bean_handlers"]
