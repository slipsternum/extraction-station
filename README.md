# Telegram Bot Template

A clean, production-ready async Telegram bot template built with pyTelegramBotAPI and FastAPI. Supports both polling and webhook modes with built-in logging, rate limiting, and database integration.

## Features

- **Async/Await Support** - Built on pyTelegramBotAPI's async implementation
- **Dual Mode** - Run in polling mode (development) or webhook mode (production)
- **FastAPI Integration** - RESTful API endpoints alongside your bot
- **Database Ready** - SQLite with async support via aiosqlite
- **State Management** - Built-in conversation state handling
- **Rate Limiting** - Configurable rate limits for commands and callbacks
- **Admin Filter** - Gate commands to administrators via the `isadmin` filter
- **Telegram Logging** - Optional log forwarding to Telegram channel
- **Auto SSL Certs** - Automatic self-signed certificate generation for webhooks
- **Clean Architecture** - Organized structure with separation of concerns

## Project Structure

```
├── src/
│   ├── api/                   # FastAPI application
│   │   ├── routers/           # API route handlers
│   │   ├── app.py             # FastAPI app and startup
│   │   ├── certs.py           # SSL certificate management
│   │   └── dependencies.py    # FastAPI dependencies
│   │   
│   ├── bot/                   # Telegram bot
│   │   ├── handlers/          # Message and command handlers
│   │   ├── commands.py        # Bot command definitions
│   │   ├── filters.py         # Custom message filters
│   │   └── middlewares.py     # Rate limiting and middleware
│   │   
│   ├── core/                  # Core functionality
│   │   ├── bootstrap.py       # Bot initialization
│   │   ├── config.py          # Configuration management
│   │   ├── logging.py         # Logging system
│   │   └── states.py          # Conversation states
│   │   
│   ├── models/                # Data models
│   │   └── schemas/           # Database schemas
│   │   
│   ├── repositories/          # Data access layer
│   ├── services/              # Business logic
│   └── utils/                 # Utility functions
│
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variables template
├── AGENTS.md                  # Guide for agent-assisted development
└── README.md
```

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/slipsternum/pyTelegramBotAPI-async-telebot-template <destination-folder>
cd <destination-folder>

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your bot token
# Get your token from @BotFather on Telegram
```

Minimum required configuration:
```env
BOT_TOKEN=your_bot_token_here
USE_POLLING=true
```

The template uses `./.data/` directory for database and state files by default.

### 3. Run the Bot

```bash
python main.py
```

## Configuration

### Bot Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `BOT_TOKEN` | Bot token from @BotFather | - | Yes |
| `USE_POLLING` | Use polling mode (true) or webhook (false) | `true` | No |

### Logging Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |
| `LOGGING_BOT_TOKEN` | Separate bot token for sending logs | - | No |
| `LOGGER_CHAT_ID` | Channel ID for log messages | - | No |

### Database Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SQLITE_DB_PATH` | Path to SQLite database file | `./.data/data.sqlite` | No |
| `SQLITE_SCHEMA_PATH` | Path to SQL schema file | `./src/models/schemas/bot_schema.sql` | No |
| `STATE_STORAGE_PATH` | Path to state storage file | `./.data/states.pkl` | No |

### Admin Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ADMIN_IDS` | Comma-separated admin user IDs | - | No |

### Rate Limiting

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `RATE_LIMIT_COMMAND_SECONDS` | Seconds between commands per user | `3` | No |
| `RATE_LIMIT_CALLBACK_SECONDS` | Seconds between callbacks per user | `3` | No |

### Webhook Configuration

Only needed if `USE_POLLING=false`:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `WEBHOOK_HOST` | Public domain/IP for webhook | - | Yes* |
| `WEBHOOK_PORT` | External port (443, 80, 88, 8443) | `8443` | No |
| `WEBHOOK_LISTEN` | Internal interface to bind | `0.0.0.0` | No |
| `WEBHOOK_LISTEN_PORT` | Internal port to listen on | `8443` | No |
| `WEBHOOK_SECRET_TOKEN` | Secret token for webhook verification | - | No |
| `WEBHOOK_PATH_PREFIX` | URL path prefix | - | No |
| `WEBHOOK_SSL_CERT` | SSL certificate path | - | No** |
| `WEBHOOK_SSL_PRIV` | SSL private key path | - | No** |

\* Required for webhook mode  
\** Leave empty if using reverse proxy

## Development

### Adding New Commands

1. Define commands in `src/bot/commands.py`:
```python
user_commands: CommandSet = CommandSet(
    commands=[
        BotCommand("mycommand", "description"),
        # ... existing commands
    ],
    scope=BotCommandScope(type="all_private_chats"),
)
```

2. Add handler in `src/bot/handlers/general.py`:
```python
@bot.message_handler(commands=["mycommand"], isprivchat=True)
async def handle_mycommand(message: types.Message, state: AsyncStateContext):
    await notifications.send_message(
        message.chat.id,
        "Your response here"
    )
```

For admin-only commands, add the handler in `src/bot/handlers/admin.py` with
`isadmin=True` and register it in `admin_commands` instead. See `/admin` for a
working example.

### Adding Conversation States

1. Define state in `src/core/states.py`:
```python
class UserStates(StatesGroup):
    idle = State()
    waiting_for_input = State()
```

2. Use in handlers:
```python
@bot.message_handler(commands=["start_flow"], isprivchat=True)
async def start_flow(message: types.Message, state: AsyncStateContext):
    await state.set(UserStates.waiting_for_input)
    await notifications.send_message(message.chat.id, "Send me your input:")

@bot.message_handler(state=UserStates.waiting_for_input, content_types=["text"])
async def handle_input(message: types.Message, state: AsyncStateContext):
    user_input = message.text
    # Process input
    await state.set(UserStates.idle)
```

### Adding Database Models

1. Define model in `src/models/__init__.py`:
```python
@dataclass
class MyModel:
    id: int
    name: str
    created_at: int
```

2. Create schema in `src/models/schemas/bot_schema.sql` (or your custom schema file):
```sql
CREATE TABLE IF NOT EXISTS my_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
```

You can use a custom schema file by setting `SQLITE_SCHEMA_PATH` in your `.env`.

3. Create repository in `src/repositories/`:
```python
class MyRepository:
    def __init__(self, db: AsyncSQLiteAdapter):
        self.db = db
    
    async def create(self, name: str) -> int:
        # Implementation
```

### Adding API Endpoints

Create a new router in `src/api/routers/`:
```python
from fastapi import APIRouter

router = APIRouter(tags=["myrouter"])

@router.get("/myendpoint")
async def my_endpoint():
    return {"status": "ok"}
```

Register in `src/api/routers/__init__.py`:
```python
from src.api.routers.myrouter import router as my_router

router = APIRouter()
router.include_router(my_router)
```

## Deployment

### Polling Mode (Simple)

Best for development and small bots:

```bash
# Set environment
USE_POLLING=true

# Run directly
python main.py

# Or with systemd/supervisor/pm2
```

### Webhook Mode (Production)

#### Option 1: With Reverse Proxy (Recommended)

Use nginx/Caddy to handle SSL:

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Environment:
```env
USE_POLLING=false
WEBHOOK_HOST=yourdomain.com
WEBHOOK_PORT=443
WEBHOOK_LISTEN_PORT=8000
WEBHOOK_SECRET_TOKEN=your_secret_token
# Leave SSL cert/key empty - nginx handles it
```

#### Option 2: Direct HTTPS

Let the bot handle SSL directly:

```env
USE_POLLING=false
WEBHOOK_HOST=yourdomain.com
WEBHOOK_PORT=8443
WEBHOOK_LISTEN_PORT=8443
WEBHOOK_SECRET_TOKEN=your_secret_token
WEBHOOK_SSL_CERT=./certs/cert.pem
WEBHOOK_SSL_PRIV=./certs/key.pem
```

Certificates will be auto-generated if paths are set but files don't exist.

## Built-in Commands

- `/start` - Show welcome message
- `/help` - Show available commands
- `/ping` - Check bot health
- `/cancel` - Cancel current operation

Admin-only (gated by the `isadmin` filter):

- `/admin` - Example admin-only command

## Troubleshooting

### Bot doesn't respond
- Check `BOT_TOKEN` is correct
- Verify bot is running: `/ping` should respond with "pong"
- Check logs for errors

### Webhook not working
- Ensure `WEBHOOK_HOST` is publicly accessible
- Verify port is one of: 443, 80, 88, 8443
- Check `WEBHOOK_SECRET_TOKEN` matches
- Test with polling mode first

### Database errors
- Ensure database directory (`./.data/` by default) exists and is writable
- Check `SQLITE_DB_PATH` and `SQLITE_SCHEMA_PATH` configuration
- Verify schema file exists at the specified path
- Check schema SQL syntax is valid

## License

MIT