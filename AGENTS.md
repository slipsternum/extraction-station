# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository. Keep changes
consistent with the conventions below.

## What this is

Extraction Station: a Telegram bot for logging coffee brews and dialling in (equipment setup,
bean bags read from photos by an LLM, and a button-driven `/brew` log). It is built on an async
**pyTelegramBotAPI** (`telebot`) template with a **FastAPI** app for webhook mode. It can run in two modes:

- **Polling** (default, `USE_POLLING=true`) — long-polls Telegram; best for development.
- **Webhook** — serves FastAPI under uvicorn and registers a Telegram webhook; for production.

## Layout

```
main.py                     Entry point -> src/api/app.py:run()
src/
  api/
    app.py                  FastAPI app, lifespan, run() (mode selection)
    certs.py                Self-signed TLS cert generation for webhook mode
    dependencies.py         FastAPI dependencies (bot context injection)
    routers/                HTTP routes: health, telegram webhook
  bot/
    commands.py             Command menus (user_commands, admin_commands)
    filters.py              Custom filters: isadmin, isprivchat
    keyboards.py            Inline keyboard and callback-data helpers
    middlewares.py          Per-user rate limiting
    handlers/               Command handlers (general, admin, setup, beans, brew)
  core/
    bootstrap.py            Wires bot, services, handlers together
    config.py               Environment-driven configuration
    logging.py              Logging adapter over loguru (+ optional Telegram mirror)
    states.py               Conversation states
  models/                   Dataclasses, brew methods/equipment kinds (coffee.py), SQL schema
  repositories/             Async SQLite data access (equipment, beans, brews)
  services/                 Business logic: notification, llm, setup, bean, brew
  utils/                    User-facing text (text.py) and input parsing (parsing.py)
```

Startup flow: `main.py` → `app.run()` → `bootstrap_bot()` (create bot → configure
commands/filters/middlewares → init services → register handlers).

## Setup and running

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then set BOT_TOKEN
python main.py
```

`BOT_TOKEN` is the only required variable. All other configuration is optional and
documented in `README.md` and `.env.example`.

## Conventions

- **Comments:** keep them minimal. Prefer a concise one-line docstring to document a
  function or class; do not add multi-line inline comments explaining how self-evident
  code works. Leave straightforward code uncommented.
- **Handlers** are nested async functions decorated with `@bot.message_handler(...)`
  inside a `register_*_handlers(bot, *, notifications)` function. Access the chat with
  `message.chat.id` and reply through the injected `NotificationService`
  (`notifications.send_message(...)`), not the raw bot.
- **Logging** goes through `from src.core.logging import logger` — `logger.debug/info/
  warning/error(...)`, which support `%`-style args (`logger.info("x %s", y)`) and an
  optional `exc_info=`. Do not use `print` or the stdlib `logging` module directly.
- **Configuration** is read once at import in `config.py` from environment variables;
  add new settings there rather than calling `os.getenv` elsewhere.
- **Admin-only** behavior is gated by the `isadmin` filter (`ADMIN_IDS`); private-chat-
  only behavior by `isprivchat`. For now every handler is admin-only. `isprivchat` doesn't
  apply to callback queries (they have no `chat`), so use it on message handlers only.
- **Multi-step flows** keep their draft in conversation state (`state.add_data` /
  `async with state.data()`) and write to the database once, on the final confirm. `/brew`
  loads everything it needs (`BrewService.load_context`) at the start so button taps never hit
  the database. Callback data is `<flow>:<action>[:<arg>]` (64-byte limit); a flow's catch-all
  `"<flow>:"` callback handler must be registered last.
- **Editing messages**: use `notifications.edit_message(message, ...)`, which edits the caption
  for photo messages and the text otherwise.
- **LLM calls** go through `LLMService` (OpenAI SDK, Chat Completions, configurable
  `OPENAI_BASE_URL`/`OPENAI_MODEL`); it is disabled when `OPENAI_MODEL` is unset.

## Common extension points

Adding a command (e.g. `/foo`) touches up to three places:

1. Define the handler in `src/bot/handlers/general.py` (or `admin.py` with
   `isadmin=True`) inside the relevant `register_*_handlers` function.
2. Register it in the command menu in `src/bot/commands.py` (`user_commands` or
   `admin_commands`).
3. If user-facing, mention it in the help text in `src/utils/text.py`.

Other extension points: conversation states in `src/core/states.py`, data models and
schemas under `src/models/`, repositories in `src/repositories/`, and API routes in
`src/api/routers/` (register new routers in `src/api/routers/__init__.py`).

## Verifying changes

There is no automated test suite or configured linter. Before considering a change done:

- Byte-compile what you touched: `python -m py_compile <files>`.
- Import-check affected modules (requires `BOT_TOKEN` to be set, even a dummy value):
  `BOT_TOKEN=dummy python -c "import src.core.bootstrap"`.
- For runtime behavior, run the bot in polling mode against a test bot token.

## Notes

- Timestamps are emitted in UTC.
- The Telegram log mirror is optional; it activates only when both `LOGGING_BOT_TOKEN`
  and `LOGGER_CHAT_ID` are set.
- Webhook mode can auto-generate a self-signed certificate when SSL paths are configured
  but the files are missing (see `src/api/certs.py`); `openssl` must be available.
