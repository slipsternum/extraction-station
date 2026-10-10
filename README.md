# ☕ Extraction Station

A personal Telegram bot for logging coffee brews and dialling in.

Snap a photo of a new bag and the bot reads the label. Log each brew with a few taps, and get AI
tips on what to change next time. If you like, every brew can also be posted as a progress card to
a group or channel. It's built for working through a grinder, an espresso machine and a pour-over
dripper, one bag at a time.

## How it works

```
/setup    register your gear once         DF54 · Gaggia Classic Pro · Hario V60
/newbean  photo of the bag → label read   HoneyBloom · Ethiopia Yirgacheffe · natural · roasted 5 Oct
/brew     tap through the brew            beans → method → grind → recipe → photo → tasting → save
          ↳ progress card                 posted to your group/topic
          ↳ 🤖 next-brew tips             sent to you privately
```

### Beans

Send `/newbean` and a photo of the bag. A vision model reads the name, roaster, origin, process,
varietal, roast level, roast date and tasting notes. You confirm or edit each field before saving,
which matters most for handwritten roast dates. You can also type the details, or fill them in by
hand if no model is configured.

### Brewing

`/brew` is one message that updates as you tap:

1. **Beans**: defaults to whatever you brewed last.
2. **Method**: espresso, pour-over or cold brew, using your gear from `/setup`.
3. **Grind**: suggested from your last brew of those beans on that grinder, one step finer if it
   was under-extracted or coarser if over.
4. **Recipe**: dose, then yield or water, then temperature and time. Suggestions come from your
   last brew, a standard ratio, or the AI's last tip (marked 🤖).
5. **Photo** of the cup (optional).
6. **Tasting**: under/good/over extraction, clarity, tasting notes (the bag's notes come first as
   buttons) and a rating.
7. **Save**: the draft lives in conversation state until this point, so nothing is written to the
   database before you save.

### Next-brew tips

After you save, the AI looks at this brew and your history with the same beans and method. That
includes tasting notes, clarity, ratio, time, roast age, your comments, and whether its earlier
advice helped. It replies privately with:

- a short diagnosis of the cup
- **one** change to make next, with a full recipe
- other ways in, and what to taste for

The next `/brew` with those beans brings the tip back and offers its numbers as 🤖 buttons.

### Progress posts

Point the bot at a group, forum topic or channel, and each brew is posted there as a card. It
shows your cup and bag photos, the attempt number for those beans and method, and the recipe, with
anything changed since the last attempt marked:

```
Cold brew · attempt 2
☕ HoneyBloom · roasted 5 Oct (7 days ago)
⚙️ 82 (was 85) · DF54
💧 1:10 (45g / 450g) (was 1:12)
⏰ 19h

👌 Well extracted · clean cup · ★★★★★
👅 floral, honey
```

AI tips never appear in progress posts.

## Quick start

You'll need Python 3.13, a bot token from [@BotFather](https://t.me/BotFather), and optionally an
API key for an OpenAI-compatible vision model.

```bash
git clone https://github.com/slipsternum/extraction-station.git
cd extraction-station
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

```env
BOT_TOKEN=123456:ABC...            # from @BotFather
ADMIN_IDS=your_telegram_user_id    # the bot only answers these users
OPENAI_MODEL=your_vision_model     # optional: label reading + tips
OPENAI_API_KEY=sk-...
```

Then run the bot and send it `/start`:

```bash
python main.py
```

To find your Telegram user ID, message [@userinfobot](https://t.me/userinfobot).

## Commands

| Command | What it does |
|---------|--------------|
| `/brew` | Log a brew; tips for the next one follow the save |
| `/newbean` | Add a bag of beans from a photo or text |
| `/beans` | List your beans; archive a bag when it's finished |
| `/history` | Your last 10 brews |
| `/setup` | Register your grinder, espresso machine and dripper |
| `/chatid` | Show the chat and topic IDs for progress posts (send it in that chat) |
| `/cancel` | Cancel the current flow |
| `/help` | Show all commands |

Every command is admin-only. Anyone not in `ADMIN_IDS` is ignored.

## Configuration

All settings live in `.env`; see [`.env.example`](.env.example) for the full list.

### Essentials

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_TOKEN` | Bot token from @BotFather (required) | - |
| `ADMIN_IDS` | Comma-separated Telegram user IDs allowed to use the bot | - |

### AI (label reading and tips)

Both features use one model through the OpenAI SDK's Chat Completions API. Any OpenAI-compatible
provider with a vision model works: OpenAI, OpenRouter, or a local server. If `OPENAI_MODEL` is
empty, you enter beans by hand and `/brew` uses the rule-of-thumb grind suggestion.

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_MODEL` | Vision-capable model ID; empty disables AI features | - |
| `OPENAI_API_KEY` | API key for the provider | - |
| `OPENAI_BASE_URL` | Base URL of an OpenAI-compatible API | OpenAI |
| `OPENAI_TIMEOUT_SECONDS` | Request timeout | `60` |

### Progress posts

| Variable | Description | Default |
|----------|-------------|---------|
| `PROGRESS_CHAT_ID` | Group/channel to post to (`-100…` ID or `@channelname`); empty disables | - |
| `PROGRESS_THREAD_ID` | Forum topic within that chat | - |

To set it up:

1. Add the bot to the group or channel. For a channel, make it an admin.
2. Send `/chatid` in the target chat or topic, and copy the two lines it replies with into `.env`.
3. Restart the bot.

If a post fails, the bot tells you why in your private chat. The brew itself is always saved.

### Storage and logging

| Variable | Description | Default |
|----------|-------------|---------|
| `SQLITE_DB_PATH` | SQLite database | `./.data/data.sqlite` |
| `STATE_STORAGE_PATH` | Conversation state (in-progress brews) | `./.data/states.pkl` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` or `ERROR` | `INFO` |
| `LOGGING_BOT_TOKEN` / `LOGGER_CHAT_ID` | Optional: mirror logs to a Telegram chat | - |

## Running it

**Polling** (the default, `USE_POLLING=true`) is all a personal bot needs: run `python main.py`
on any machine that stays on, under systemd, pm2 or similar.

**Webhook mode** (`USE_POLLING=false`) serves a FastAPI app under uvicorn instead. Set
`WEBHOOK_HOST`, `WEBHOOK_PORT`, `WEBHOOK_LISTEN_PORT` and `WEBHOOK_SECRET_TOKEN`. Either put it
behind a reverse proxy that terminates TLS, or set `WEBHOOK_SSL_CERT` and `WEBHOOK_SSL_PRIV`. If
those files don't exist, a self-signed certificate is generated for you (this needs `openssl`).

## Troubleshooting

- **The bot doesn't reply.** Check that your user ID is in `ADMIN_IDS` and that `BOT_TOKEN` is
  right. `/ping` should answer "pong".
- **Label reading or tips don't appear.** Check that `OPENAI_MODEL` is set and supports images,
  then look for warnings in the logs.
- **Progress posts fail.** The bot must be in the chat (as an admin, for channels) and allowed to
  post in that topic. The DM it sends you includes Telegram's reason.
- **Buttons say the brew has ended.** That panel is from a finished or cancelled brew. Start a new
  one with `/brew`.

## Development

The stack is async [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI), SQLite via
aiosqlite, and the OpenAI SDK, with FastAPI for webhook mode. `requirements.txt` is a fully pinned
set tested on Python 3.13.

See [AGENTS.md](AGENTS.md) for the code layout, conventions, dependency upgrades and how to verify
changes.

## License

MIT
