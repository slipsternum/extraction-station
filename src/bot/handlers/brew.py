from __future__ import annotations

from typing import Any, Optional

from telebot.async_telebot import AsyncTeleBot, types
from telebot.states import State
from telebot.states.asyncio.context import StateContext as AsyncStateContext

from src.bot.keyboards import Button, callback_arg, callback_prefix, chunk, inline, is_plain_text
from src.core.logging import logger
from src.core.states import BrewStates
from src.models.coffee import BREW_METHODS, CLARITY_LABELS, EXTRACTION_LABELS
from src.services.advice_service import AdviceService
from src.services.brew_service import GRIND_STEP, BrewService
from src.services.notification_service import NotificationService
from src.utils.parsing import parse_number, split_notes
from src.utils.text import BrewText, bean_label

CANCEL_ROW: list[Button] = [("✖ Cancel", "brew:discard")]
EXTRACTION_BUTTONS: tuple[tuple[str, str], ...] = (("😖 Under", "under"), ("👌 Good", "good"), ("😬 Over", "over"))


def _num(value: float) -> str:
    return f"{value:g}"


def register_brew_handlers(
    bot: AsyncTeleBot,
    *,
    notifications: NotificationService,
    brews: BrewService,
    advice: AdviceService,
) -> None:

    async def load(state: AsyncStateContext) -> tuple[dict[str, Any], dict[str, Any], Optional[int]]:
        async with state.data() as data:
            return dict(data.get("brew") or {}), data.get("ctx") or {}, data.get("panel")

    async def render(
        chat_id: int,
        state: AsyncStateContext,
        step: State,
        draft: dict[str, Any],
        text: str,
        markup: Optional[types.InlineKeyboardMarkup],
        call: Optional[types.CallbackQuery] = None,
    ) -> None:
        """Show a step on the brew panel and persist the draft to state (never the DB)."""
        await state.set(step)
        _, _, panel = await load(state)
        if call is not None and call.message.message_id == panel:
            await notifications.edit_message(call.message, text, reply_markup=markup)
        else:
            if panel:
                await notifications.clear_reply_markup(chat_id, panel)
            panel = (await notifications.send_message(chat_id, text, reply_markup=markup)).message_id
        await state.add_data(brew=draft, panel=panel)

    async def guard(call: types.CallbackQuery, state: AsyncStateContext):
        """Load the draft for a button tap, rejecting taps on an outdated panel."""
        draft, ctx, panel = await load(state)
        if not draft or panel != call.message.message_id:
            await notifications.answer_callback(call, BrewText.stale())
            return None
        await notifications.answer_callback(call)
        return draft, ctx

    async def step_bean(chat_id, state, draft, ctx, call=None):
        bean = BrewService.find_bean(ctx, draft["bean_id"])
        markup = inline([[("✅ Use these", "brew:beanok"), ("🔄 Other beans", "brew:beanswitch")], CANCEL_ROW])
        await render(chat_id, state, BrewStates.bean, draft, BrewText.confirm_bean(bean), markup, call)

    async def step_method(chat_id, state, draft, ctx, call=None):
        bean = BrewService.find_bean(ctx, draft["bean_id"])
        rows = chunk([(m.label, f"brew:method:{key}") for key, m in BREW_METHODS.items()], 3)
        markup = inline([*rows, CANCEL_ROW])
        await render(chat_id, state, BrewStates.method, draft, BrewText.pick_method(bean), markup, call)

    async def step_grind(chat_id, state, draft, ctx, call=None):
        suggestion, reason = BrewService.suggest_grind(ctx, draft["bean_id"], draft["method"])
        plan = BrewService.ai_plan(ctx, draft["bean_id"], draft["method"]) or {}
        ai_grind = plan.get("next_brew", {}).get("grind_setting")
        rows: list[list[Button]] = []
        values: list[float] = []
        if suggestion is not None:
            values = [v for v in (suggestion + GRIND_STEP * o for o in (-2, -1, 0, 1, 2)) if v >= 0]
            labels = {v: f"• {_num(v)} •" if v == suggestion else _num(v) for v in values}
            if ai_grind in labels:
                labels[ai_grind] = f"🤖 {_num(ai_grind)}"
            rows.append([(labels[v], f"brew:grind:{_num(v)}") for v in values])
        if ai_grind is not None and ai_grind not in values:
            rows.append([(f"🤖 {_num(ai_grind)} (AI tip)", f"brew:grind:{_num(ai_grind)}")])
        rows.append(CANCEL_ROW)
        text = BrewText.grind(
            draft, ctx, reason, has_options=len(rows) > 1, ai_tip=plan.get("primary_change")
        )
        await render(chat_id, state, BrewStates.grind, draft, text, inline(rows), call)

    async def step_param(chat_id, state, draft, ctx, call=None):
        fields = BREW_METHODS[draft["method"]].fields
        index = draft.get("field_index", 0)
        if index >= len(fields):
            await step_photo(chat_id, state, draft, ctx, call)
            return
        field = fields[index]
        options = BrewService.suggest_values(ctx, draft, field)
        rows = chunk([(label, f"brew:val:{_num(value)}") for label, value in options], 2)
        rows.append([("⏭ Skip", "brew:val:skip")])
        text = BrewText.param(field, bool(options))
        await render(chat_id, state, BrewStates.param, draft, text, inline(rows), call)

    async def step_photo(chat_id, state, draft, ctx, call=None):
        markup = inline([[("⏭ Skip photo", "brew:photoskip")]])
        await render(chat_id, state, BrewStates.photo, draft, BrewText.photo(), markup, call)

    async def step_extraction(chat_id, state, draft, ctx, call=None):
        rows = [[(label, f"brew:ext:{key}") for label, key in EXTRACTION_BUTTONS]]
        await render(chat_id, state, BrewStates.extraction, draft, BrewText.extraction(), inline(rows), call)

    async def step_clarity(chat_id, state, draft, ctx, call=None):
        rows = [[(label, f"brew:clar:{key}") for key, label in CLARITY_LABELS.items()], [("⏭ Skip", "brew:clar:skip")]]
        await render(chat_id, state, BrewStates.clarity, draft, BrewText.clarity(), inline(rows), call)

    async def step_notes(chat_id, state, draft, ctx, call=None):
        selected = draft.setdefault("tasting_notes", [])
        options = draft.setdefault("note_options", BrewService.note_options(ctx, draft["bean_id"]))
        buttons = [(f"✓ {note}" if note in selected else note, f"brew:note:{i}") for i, note in enumerate(options)]
        markup = inline([*chunk(buttons, 3), [("✅ Done", "brew:notesdone")]])
        await render(chat_id, state, BrewStates.notes, draft, BrewText.notes(selected), markup, call)

    async def step_rating(chat_id, state, draft, ctx, call=None):
        rows = [[(f"{n}★", f"brew:rate:{n}") for n in range(1, 6)], [("⏭ Skip", "brew:rate:skip")]]
        await render(chat_id, state, BrewStates.rating, draft, BrewText.rating(), inline(rows), call)

    async def step_comment(chat_id, state, draft, ctx, call=None):
        markup = inline([[("⏭ Skip", "brew:commentskip")]])
        await render(chat_id, state, BrewStates.comment, draft, BrewText.comment(), markup, call)

    async def step_review(chat_id, state, draft, ctx, call=None):
        text = BrewText.summary(draft, ctx, header="📝 <b>Review your brew</b>")
        markup = inline([[("💾 Save", "brew:save"), ("🗑 Discard", "brew:discard")]])
        await render(chat_id, state, BrewStates.review, draft, text, markup, call)

    def on_button(prefix: str, step: State):
        """Register a brew button handler that receives the loaded draft and context."""

        def decorator(func):
            @bot.callback_query_handler(func=callback_prefix(prefix), state=step, isadmin=True)
            async def handler(call: types.CallbackQuery, state: AsyncStateContext):
                loaded = await guard(call, state)
                if loaded:
                    await func(call, state, *loaded)

            return func

        return decorator

    def on_text(step: State):
        """Register a typed-input handler for a brew step."""

        def decorator(func):
            @bot.message_handler(
                state=step, func=is_plain_text, content_types=["text"], isadmin=True, isprivchat=True
            )
            async def handler(message: types.Message, state: AsyncStateContext):
                draft, ctx, _ = await load(state)
                if draft:
                    await func(message, state, draft, ctx)

            return func

        return decorator

    @bot.message_handler(commands=["brew"], isadmin=True, isprivchat=True)
    async def handle_brew(message: types.Message, state: AsyncStateContext):
        ctx = await brews.load_context(message.from_user.id)
        if "grinder" not in ctx["equipment"]:
            await notifications.send_message(message.chat.id, BrewText.needs_grinder())
            return
        bean = BrewService.default_bean(ctx)
        if bean is None:
            await notifications.send_message(message.chat.id, BrewText.needs_beans())
            return
        await state.delete()
        await state.set(BrewStates.bean)
        await state.add_data(ctx=ctx)
        await step_bean(message.chat.id, state, {"bean_id": bean["id"]}, ctx)

    @bot.message_handler(commands=["history"], isadmin=True, isprivchat=True)
    async def handle_history(message: types.Message, state: AsyncStateContext):
        recent = await brews.recent(message.from_user.id, limit=10)
        await notifications.send_message(message.chat.id, BrewText.history(recent))

    @on_button("brew:beanok", BrewStates.bean)
    async def on_bean_ok(call, state, draft, ctx):
        await step_method(call.message.chat.id, state, draft, ctx, call)

    @on_button("brew:beanswitch", BrewStates.bean)
    async def on_bean_switch(call, state, draft, ctx):
        rows = [[(bean_label(b)[:60], f"brew:usebean:{b['id']}")] for b in ctx["beans"][:12]]
        markup = inline([*rows, CANCEL_ROW])
        await render(call.message.chat.id, state, BrewStates.bean, draft, BrewText.pick_bean(), markup, call)

    @on_button("brew:usebean:", BrewStates.bean)
    async def on_use_bean(call, state, draft, ctx):
        bean_id = int(callback_arg(call))
        if BrewService.find_bean(ctx, bean_id):
            draft["bean_id"] = bean_id
        await step_method(call.message.chat.id, state, draft, ctx, call)

    @on_button("brew:method:", BrewStates.method)
    async def on_method(call, state, draft, ctx):
        method = BREW_METHODS.get(callback_arg(call))
        if method is None:
            return
        grinder = ctx["equipment"].get("grinder") or {}
        brewer = ctx["equipment"].get(method.equipment_kind or "") or {}
        draft.update(
            method=method.key,
            grinder_id=grinder.get("id"),
            grinder_name=grinder.get("name"),
            brewer_id=brewer.get("id"),
            brewer_name=brewer.get("name"),
        )
        await step_grind(call.message.chat.id, state, draft, ctx, call)

    async def set_grind(chat_id, state, draft, ctx, value: float, call=None):
        draft["grind_setting"] = value
        draft["field_index"] = 0
        await step_param(chat_id, state, draft, ctx, call)

    @on_button("brew:grind:", BrewStates.grind)
    async def on_grind(call, state, draft, ctx):
        await set_grind(call.message.chat.id, state, draft, ctx, float(callback_arg(call)), call)

    @on_text(BrewStates.grind)
    async def on_grind_text(message, state, draft, ctx):
        value = parse_number(message.text)
        if value is None:
            await notifications.send_message(
                message.chat.id, "Send a number, e.g. <code>12</code> or <code>12.5</code>."
            )
            return
        await set_grind(message.chat.id, state, draft, ctx, value)

    async def set_param(chat_id, state, draft, ctx, value: Optional[float], call=None):
        field = BREW_METHODS[draft["method"]].fields[draft.get("field_index", 0)]
        draft[field.column] = round(value * field.scale, 2) if value is not None else None
        draft["field_index"] = draft.get("field_index", 0) + 1
        await step_param(chat_id, state, draft, ctx, call)

    @on_button("brew:val:", BrewStates.param)
    async def on_param(call, state, draft, ctx):
        arg = callback_arg(call)
        await set_param(call.message.chat.id, state, draft, ctx, None if arg == "skip" else float(arg), call)

    @on_text(BrewStates.param)
    async def on_param_text(message, state, draft, ctx):
        value = parse_number(message.text)
        if value is None:
            await notifications.send_message(message.chat.id, "Send a number (or m:ss for times).")
            return
        await set_param(message.chat.id, state, draft, ctx, value)

    @bot.message_handler(state=BrewStates.photo, content_types=["photo"], isadmin=True, isprivchat=True)
    async def on_brew_photo(message: types.Message, state: AsyncStateContext):
        draft, ctx, _ = await load(state)
        if not draft:
            return
        draft["photo_file_id"] = message.photo[-1].file_id
        await step_extraction(message.chat.id, state, draft, ctx)

    @on_button("brew:photoskip", BrewStates.photo)
    async def on_photo_skip(call, state, draft, ctx):
        await step_extraction(call.message.chat.id, state, draft, ctx, call)

    @on_button("brew:ext:", BrewStates.extraction)
    async def on_extraction(call, state, draft, ctx):
        value = callback_arg(call)
        if value in EXTRACTION_LABELS:
            draft["extraction"] = value
        await step_clarity(call.message.chat.id, state, draft, ctx, call)

    @on_button("brew:clar:", BrewStates.clarity)
    async def on_clarity(call, state, draft, ctx):
        value = callback_arg(call)
        draft["clarity"] = value if value in CLARITY_LABELS else None
        await step_notes(call.message.chat.id, state, draft, ctx, call)

    @on_button("brew:note:", BrewStates.notes)
    async def on_note(call, state, draft, ctx):
        options = draft.get("note_options", [])
        index = int(callback_arg(call))
        if 0 <= index < len(options):
            note = options[index]
            selected = draft.setdefault("tasting_notes", [])
            if note in selected:
                selected.remove(note)
            else:
                selected.append(note)
        await step_notes(call.message.chat.id, state, draft, ctx, call)

    @on_text(BrewStates.notes)
    async def on_note_text(message, state, draft, ctx):
        options = draft.setdefault("note_options", [])
        selected = draft.setdefault("tasting_notes", [])
        for note in split_notes(message.text):
            if note not in options:
                options.append(note)
            if note not in selected:
                selected.append(note)
        await step_notes(message.chat.id, state, draft, ctx)

    @on_button("brew:notesdone", BrewStates.notes)
    async def on_notes_done(call, state, draft, ctx):
        await step_rating(call.message.chat.id, state, draft, ctx, call)

    @on_button("brew:rate:", BrewStates.rating)
    async def on_rating(call, state, draft, ctx):
        value = callback_arg(call)
        draft["rating"] = int(value) if value.isdigit() and 1 <= int(value) <= 5 else None
        await step_comment(call.message.chat.id, state, draft, ctx, call)

    @on_text(BrewStates.comment)
    async def on_comment_text(message, state, draft, ctx):
        draft["comment"] = message.text.strip()[:500]
        await step_review(message.chat.id, state, draft, ctx)

    @on_button("brew:commentskip", BrewStates.comment)
    async def on_comment_skip(call, state, draft, ctx):
        await step_review(call.message.chat.id, state, draft, ctx, call)

    @on_button("brew:save", BrewStates.review)
    async def on_save(call, state, draft, ctx):
        brew_id = await brews.save(call.from_user.id, draft)
        await state.delete()
        text = BrewText.summary(draft, ctx, header=BrewText.saved())
        await notifications.edit_message(call.message, text)
        if advice.enabled:
            await send_advice(call.message.chat.id, call.from_user.id, brew_id, draft, ctx)

    async def send_advice(chat_id: int, user_id: int, brew_id: int, draft, ctx) -> None:
        """Post a "thinking" message, then replace it with the LLM's next-brew tips."""
        notice = await notifications.send_message(chat_id, BrewText.thinking())
        try:
            tips = await advice.advise(user_id, brew_id, draft, ctx)
            text = BrewText.advice(tips, draft["method"])
        except Exception as exc:
            logger.warning("Brew advice failed for brew %s: %s", brew_id, exc, exc_info=exc)
            text = BrewText.advice_failed()
        await notifications.edit_message_text(chat_id, notice.message_id, text)

    @bot.callback_query_handler(func=callback_prefix("brew:discard"), isadmin=True)
    async def on_discard(call: types.CallbackQuery, state: AsyncStateContext):
        if await guard(call, state) is None:
            return
        await state.delete()
        await notifications.edit_message(call.message, BrewText.discarded())

    @bot.callback_query_handler(func=callback_prefix("brew:"), isadmin=True)
    async def on_stale(call: types.CallbackQuery, state: AsyncStateContext):
        await notifications.answer_callback(call, BrewText.stale())


__all__ = ["register_brew_handlers"]
