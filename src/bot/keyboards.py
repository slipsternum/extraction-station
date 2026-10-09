from __future__ import annotations

from typing import Callable, Sequence

from telebot import types

Button = tuple[str, str]


def inline(rows: Sequence[Sequence[Button]]) -> types.InlineKeyboardMarkup:
    """Build an inline keyboard from rows of (text, callback_data) pairs."""
    markup = types.InlineKeyboardMarkup()
    for row in rows:
        if row:
            markup.row(*(types.InlineKeyboardButton(text, callback_data=data) for text, data in row))
    return markup


def chunk(buttons: Sequence[Button], size: int) -> list[list[Button]]:
    return [list(buttons[i : i + size]) for i in range(0, len(buttons), size)]


def callback_prefix(prefix: str) -> Callable[[types.CallbackQuery], bool]:
    return lambda call: bool(call.data) and call.data.startswith(prefix)


def is_plain_text(message: types.Message) -> bool:
    """True for text that isn't a command, so commands still work mid-flow."""
    return bool(message.text) and not message.text.startswith("/")


def callback_arg(call: types.CallbackQuery) -> str:
    """Return the last ``:``-separated segment of the callback data."""
    return call.data.rsplit(":", 1)[-1]


__all__ = ["Button", "callback_arg", "callback_prefix", "chunk", "inline", "is_plain_text"]
