"""Async logging adapter over loguru with optional mirroring to a Telegram channel."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from typing import Any

import aiohttp
from loguru import logger as _console
from telebot.async_telebot import AsyncTeleBot
from telebot.formatting import escape_html

from src.core import config

_CONSOLE_FORMAT = (
    "<green>[{extra[ts]}]</green> "
    "[<cyan>{extra[bot]}</cyan>] "
    "[<level>{level}</level>] "
    "<level>{message}</level>"
)

_console.remove()
_console.add(
    sys.stdout,
    level="DEBUG",
    format=_CONSOLE_FORMAT,
    colorize=True,
    backtrace=False,
    diagnose=False,
    enqueue=False,
)


class Logger:
    """Logging adapter over loguru with an async Telegram-channel mirror."""

    LOG_LEVEL_ORDER = ["DEBUG", "INFO", "WARNING", "ERROR"]
    LOG_LEVEL = config.LOG_LEVEL if config.LOG_LEVEL in LOG_LEVEL_ORDER else "INFO"

    BOT_USERNAME = "bot"
    _queue: asyncio.Queue[dict[str, Any] | object] | None = None
    _worker_task: asyncio.Task[None] | None = None
    _sentinel: object = object()

    @classmethod
    async def init(cls, bot: AsyncTeleBot | None = None) -> None:
        """Start the Telegram-mirror worker and resolve the bot username."""
        if cls._worker_task is not None:
            await cls.shutdown()

        cls._queue = asyncio.Queue(maxsize=500)
        cls._worker_task = asyncio.create_task(cls._worker_loop(), name="logger-worker")

        if bot is not None:
            try:
                me = await bot.get_me()
                cls.BOT_USERNAME = getattr(me, "username", cls.BOT_USERNAME) or cls.BOT_USERNAME
            except Exception as exc:
                cls.debug("Could not resolve bot username: %s", exc)

        cls.info("Logger initialised.")

    @classmethod
    def _should_log(cls, level: str) -> bool:
        """Return True when ``level`` meets the configured threshold."""
        return _console.level(level).no >= _console.level(cls.LOG_LEVEL).no

    @classmethod
    def _emit_console(
        cls, level: str, ts: str, message: str, exc_info: Any = None
    ) -> None:
        """Write a record to the console sink; message braces are treated literally."""
        bound = _console.bind(ts=ts, bot=cls.BOT_USERNAME)
        if exc_info:
            bound.opt(exception=exc_info).log(level, message)
        else:
            bound.log(level, message)

    @classmethod
    def log(
        cls,
        message: str,
        *,
        level: str = "INFO",
        to_channel: bool | None = None,
        to_console: bool = True,
        exc_info: Any = None,
    ) -> None:
        """Emit a message to the console and, when configured, the Telegram channel."""
        if not cls._should_log(level):
            return
        ts = datetime.now(timezone.utc).isoformat()
        formatted = f"[{ts}] [{cls.BOT_USERNAME}] [{level}] {message}"

        if to_console:
            cls._emit_console(level, ts, message, exc_info)

        send_to_channel = to_channel
        if send_to_channel is None:
            send_to_channel = bool(config.LOGGING_BOT_TOKEN and config.LOGGER_CHAT_ID)
        if (
            send_to_channel
            and cls._queue is not None
            and config.LOGGING_BOT_TOKEN
            and config.LOGGER_CHAT_ID
        ):
            cls._enqueue(
                {
                    "chat_id": config.LOGGER_CHAT_ID,
                    "text": f"<pre>{escape_html(formatted)}</pre>",
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }
            )

    @classmethod
    def debug(cls, message: str, *fmt_args, **kwargs) -> None:
        if cls._should_log("DEBUG"):
            cls.log(message % fmt_args if fmt_args else message, level="DEBUG", **kwargs)

    @classmethod
    def info(cls, message: str, *fmt_args, **kwargs) -> None:
        if cls._should_log("INFO"):
            cls.log(message % fmt_args if fmt_args else message, level="INFO", **kwargs)

    @classmethod
    def warning(cls, message: str, *fmt_args, **kwargs) -> None:
        if cls._should_log("WARNING"):
            cls.log(message % fmt_args if fmt_args else message, level="WARNING", **kwargs)

    @classmethod
    def error(cls, message: str, *fmt_args, **kwargs) -> None:
        if cls._should_log("ERROR"):
            cls.log(message % fmt_args if fmt_args else message, level="ERROR", **kwargs)

    @classmethod
    def _enqueue(cls, payload: dict[str, Any]) -> None:
        if cls._queue is None:
            return
        try:
            cls._queue.put_nowait(payload)
        except asyncio.QueueFull:
            cls.log("Queue full; dropping log payload.", level="WARNING", to_channel=False)

    @classmethod
    async def _worker_loop(cls) -> None:
        """Deliver queued payloads to Telegram until the shutdown sentinel arrives."""
        assert cls._queue is not None
        timeout = aiohttp.ClientTimeout(total=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                while True:
                    item = await cls._queue.get()
                    if item is cls._sentinel:
                        cls._queue.task_done()
                        break
                    try:
                        await cls._send_to_telegram(session, item)
                    except Exception as exc:
                        cls.log(
                            f"Failed to deliver log: {exc}",
                            level="ERROR",
                            to_channel=False,
                        )
                    finally:
                        cls._queue.task_done()
        except asyncio.CancelledError:
            raise

    @classmethod
    async def _send_to_telegram(
        cls, session: aiohttp.ClientSession, payload: dict[str, Any]
    ) -> None:
        url = f"https://api.telegram.org/bot{config.LOGGING_BOT_TOKEN}/sendMessage"
        async with session.post(url, data=payload) as response:
            if response.status != 200:
                body = await response.text()
                cls.log(
                    f"Telegram logging failed: {response.status} {body}",
                    level="ERROR",
                    to_channel=False,
                )

    @classmethod
    async def flush(cls) -> None:
        """Block until all queued payloads have been delivered."""
        if cls._queue is None:
            return
        await cls._queue.join()

    @classmethod
    async def shutdown(cls) -> None:
        """Stop the worker and wait for it to drain."""
        if cls._queue is None:
            return
        await cls._queue.put(cls._sentinel)
        if cls._worker_task is not None:
            await cls._worker_task
        cls._queue = None
        cls._worker_task = None


logger = Logger

__all__ = ["Logger", "logger"]
