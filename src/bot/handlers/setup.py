from __future__ import annotations

from telebot.async_telebot import AsyncTeleBot, types
from telebot.states.asyncio.context import StateContext as AsyncStateContext

from src.bot.keyboards import callback_arg, callback_prefix, inline, is_plain_text
from src.core.states import SetupStates
from src.models.coffee import EQUIPMENT_KINDS
from src.services.notification_service import NotificationService
from src.services.setup_service import SetupService
from src.utils.text import SetupText


def register_setup_handlers(
    bot: AsyncTeleBot,
    *,
    notifications: NotificationService,
    setup: SetupService,
) -> None:

    async def overview(user_id: int) -> tuple[str, types.InlineKeyboardMarkup]:
        defaults = await setup.defaults(user_id)
        rows = [[(label, f"setup:kind:{kind}")] for kind, label in EQUIPMENT_KINDS.items()]
        rows.append([("✅ Done", "setup:done")])
        return SetupText.overview(defaults), inline(rows)

    async def leave_naming(state: AsyncStateContext) -> None:
        if await state.get() == SetupStates.add_name.name:
            await state.delete()

    @bot.message_handler(commands=["setup"], isadmin=True, isprivchat=True)
    async def handle_setup(message: types.Message, state: AsyncStateContext):
        text, markup = await overview(message.from_user.id)
        await notifications.send_message(message.chat.id, text, reply_markup=markup)

    @bot.callback_query_handler(func=callback_prefix("setup:home"), isadmin=True)
    async def on_home(call: types.CallbackQuery, state: AsyncStateContext):
        await leave_naming(state)
        text, markup = await overview(call.from_user.id)
        await notifications.edit_message(call.message, text, reply_markup=markup)
        await notifications.answer_callback(call)

    @bot.callback_query_handler(func=callback_prefix("setup:done"), isadmin=True)
    async def on_done(call: types.CallbackQuery, state: AsyncStateContext):
        await leave_naming(state)
        defaults = await setup.defaults(call.from_user.id)
        await notifications.edit_message(call.message, SetupText.overview(defaults))
        await notifications.answer_callback(call, "Saved")

    @bot.callback_query_handler(func=callback_prefix("setup:kind:"), isadmin=True)
    async def on_kind(call: types.CallbackQuery, state: AsyncStateContext):
        kind = callback_arg(call)
        if kind not in EQUIPMENT_KINDS:
            await notifications.answer_callback(call)
            return
        await leave_naming(state)
        items = await setup.list_kind(call.from_user.id, kind)
        rows = [[(f"{'✓ ' if item.is_default else ''}{item.name}", f"setup:pick:{item.id}")] for item in items]
        rows.append([(f"➕ Add {EQUIPMENT_KINDS[kind].lower()}", f"setup:add:{kind}")])
        rows.append([("⬅ Back", "setup:home")])
        await notifications.edit_message(call.message, SetupText.pick(kind, bool(items)), reply_markup=inline(rows))
        await notifications.answer_callback(call)

    @bot.callback_query_handler(func=callback_prefix("setup:pick:"), isadmin=True)
    async def on_pick(call: types.CallbackQuery, state: AsyncStateContext):
        item = await setup.set_default(call.from_user.id, int(callback_arg(call)))
        text, markup = await overview(call.from_user.id)
        await notifications.edit_message(call.message, text, reply_markup=markup)
        await notifications.answer_callback(call, f"Default set: {item.name}" if item else "Not found")

    @bot.callback_query_handler(func=callback_prefix("setup:add:"), isadmin=True)
    async def on_add(call: types.CallbackQuery, state: AsyncStateContext):
        kind = callback_arg(call)
        if kind not in EQUIPMENT_KINDS:
            await notifications.answer_callback(call)
            return
        await state.delete()
        await state.set(SetupStates.add_name)
        await state.add_data(setup_kind=kind, setup_panel=call.message.message_id)
        markup = inline([[("⬅ Back", f"setup:kind:{kind}")]])
        await notifications.edit_message(call.message, SetupText.ask_name(kind), reply_markup=markup)
        await notifications.answer_callback(call)

    @bot.message_handler(
        state=SetupStates.add_name, func=is_plain_text, content_types=["text"], isadmin=True, isprivchat=True
    )
    async def on_name(message: types.Message, state: AsyncStateContext):
        async with state.data() as data:
            kind = data.get("setup_kind")
            panel_id = data.get("setup_panel")
        name = message.text.strip()[:60]
        await state.delete()
        if kind not in EQUIPMENT_KINDS:
            return
        await setup.add(message.from_user.id, kind, name)
        if panel_id:
            await notifications.clear_reply_markup(message.chat.id, panel_id)
        text, markup = await overview(message.from_user.id)
        await notifications.send_message(message.chat.id, text, reply_markup=markup)


__all__ = ["register_setup_handlers"]
