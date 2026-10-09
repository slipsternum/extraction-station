from __future__ import annotations

from fastapi import Request

from src.core.bootstrap import BotContext


def get_bot_context(request: Request) -> BotContext:
    context = getattr(request.app.state, "bot_context", None)
    if context is None:
        raise RuntimeError("Bot context is not initialised. Check startup sequence.")
    return context


__all__ = ["get_bot_context"]
