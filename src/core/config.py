"""Minimal configuration layer for the async TeleBot boilerplate."""
from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv(override=True)


def _get_env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise ValueError(f"Missing required environment variable: {name}")
    return value or ""


def _parse_list_env(name: str) -> list[str]:
    raw_value = os.getenv(name, "")
    if not raw_value:
        return []
    normalized = raw_value.replace("\r", "\n").replace(",", "\n")
    return [value.strip() for value in normalized.split("\n") if value.strip()]


def _parse_chat_id(value: str | None) -> int | str | None:
    """Numeric chat IDs become ints; ``@channelusername`` stays a string."""
    value = (value or "").strip()
    if not value:
        return None
    return int(value) if value.lstrip("-").isdigit() else value


BOT_TOKEN: str = _get_env("BOT_TOKEN", required=True)
LOGGING_BOT_TOKEN: str | None = _get_env("LOGGING_BOT_TOKEN") or None
LOGGER_CHAT_ID: int | None = int(os.getenv("LOGGER_CHAT_ID", "0")) or None
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./.data/data.sqlite")
SQLITE_SCHEMA_PATH = os.getenv("SQLITE_SCHEMA_PATH", "./src/models/schemas/bot_schema.sql")
STATE_STORAGE_PATH = os.getenv("STATE_STORAGE_PATH", "./.data/states.pkl")

ADMIN_IDS: list[int] = [int(x) for x in _parse_list_env("ADMIN_IDS")] if os.getenv("ADMIN_IDS") else []
RATE_LIMIT_COMMAND_SECONDS = int(os.getenv("RATE_LIMIT_COMMAND_SECONDS", "0"))
RATE_LIMIT_CALLBACK_SECONDS = int(os.getenv("RATE_LIMIT_CALLBACK_SECONDS", "0"))

OPENAI_API_KEY: str | None = _get_env("OPENAI_API_KEY") or None
OPENAI_BASE_URL: str | None = _get_env("OPENAI_BASE_URL") or None
OPENAI_MODEL: str | None = _get_env("OPENAI_MODEL") or None
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60"))

PROGRESS_CHAT_ID: int | str | None = _parse_chat_id(os.getenv("PROGRESS_CHAT_ID"))
PROGRESS_THREAD_ID: int | None = int(os.getenv("PROGRESS_THREAD_ID", "0")) or None

USE_POLLING: bool = os.getenv("USE_POLLING", "true").lower() == "true"

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))
WEBHOOK_LISTEN = os.getenv("WEBHOOK_LISTEN", "0.0.0.0")
WEBHOOK_LISTEN_PORT = int(os.getenv("WEBHOOK_LISTEN_PORT", str(WEBHOOK_PORT)))
WEBHOOK_SSL_CERT = os.getenv("WEBHOOK_SSL_CERT")
WEBHOOK_SSL_PRIV = os.getenv("WEBHOOK_SSL_PRIV")
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")
WEBHOOK_PATH_PREFIX = os.getenv("WEBHOOK_PATH_PREFIX", "").rstrip("/")
WEBHOOK_URL_BASE = "https://{}:{}".format(WEBHOOK_HOST, WEBHOOK_PORT) if WEBHOOK_HOST else None
WEBHOOK_URL_PATH = "/{}/".format(BOT_TOKEN)
WEBHOOK_URL = WEBHOOK_URL_BASE + WEBHOOK_PATH_PREFIX + WEBHOOK_URL_PATH if WEBHOOK_URL_BASE else None


__all__ = [
    "BOT_TOKEN",
    "LOGGING_BOT_TOKEN",
    "LOGGER_CHAT_ID",
    "LOG_LEVEL",
    "SQLITE_DB_PATH",
    "SQLITE_SCHEMA_PATH",
    "STATE_STORAGE_PATH",
    "ADMIN_IDS",
    "RATE_LIMIT_COMMAND_SECONDS",
    "RATE_LIMIT_CALLBACK_SECONDS",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "OPENAI_TIMEOUT_SECONDS",
    "PROGRESS_CHAT_ID",
    "PROGRESS_THREAD_ID",
    "USE_POLLING",
    "WEBHOOK_HOST",
    "WEBHOOK_PORT",
    "WEBHOOK_LISTEN",
    "WEBHOOK_LISTEN_PORT",
    "WEBHOOK_SSL_CERT",
    "WEBHOOK_SSL_PRIV",
    "WEBHOOK_SECRET_TOKEN",
    "WEBHOOK_PATH_PREFIX",
    "WEBHOOK_URL_BASE",
    "WEBHOOK_URL_PATH",
    "WEBHOOK_URL",
]
