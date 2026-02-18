# Phase 1: Skeleton — Implementation Plan

## Goal
Create the project structure, Docker infrastructure, config loader, security gate, and a basic echo handler. By the end of this phase, the bot should be runnable (locally or in Docker) and respond to Telegram messages from the authorized user with an echo reply.

---

## Steps

### 1. Create directory structure
Create all the directories and `__init__.py` files outlined in DESIGN.md:

```
bot/
  clawdia/
    __init__.py
    __main__.py
    config.py
    security.py
    handlers/
      __init__.py
      chat.py
      admin.py
    ai/
      __init__.py
    mcp/
      __init__.py
    scheduler/
      __init__.py
mcp-servers/
  calendar/
  weather/
config/
tests/
```

Only the directories and empty `__init__.py` files for now. The `ai/`, `mcp/`, and `scheduler/` packages get their implementation modules in later phases — we just create the package shells so imports don't break.

### 2. `bot/clawdia/config.py` — Settings loader
Implement `Settings` using `pydantic-settings`:
- `telegram_bot_token: str` (required, from env)
- `telegram_user_id: int` (required, from env)
- `openai_api_key: str` (required, from env)
- `openai_model: str = "gpt-5.2"`
- `reasoning_effort: str = "medium"`
- `max_tool_rounds: int = 5`
- `mcp_config_path: str = "config/mcp_servers.yaml"`

Uses `pydantic-settings` to read from environment variables (and `.env` file).

### 3. `bot/clawdia/security.py` — Telegram user ID gate
Implement a `python-telegram-bot` handler filter or check function:
- Compares `update.effective_user.id` against the configured `telegram_user_id`
- Silently ignores messages from unauthorized users (no error response)
- Rejects all group/supergroup messages (only allows private chats)

### 4. `bot/clawdia/handlers/chat.py` — Echo handler (placeholder)
A simple message handler that echoes back the user's message. This is a placeholder — Phase 2 will replace it with the AI-powered handler. Purpose is to verify the Telegram bot wiring works end-to-end.

### 5. `bot/clawdia/handlers/admin.py` — Admin commands (stubs)
Stub `/status` and `/reload` command handlers that return placeholder text (e.g., "Status: running" and "Reload: not yet implemented"). These get real implementations in later phases.

### 6. `bot/clawdia/__main__.py` — Entrypoint
Wire everything together:
- Load settings from env
- Create `Application` from `python-telegram-bot`
- Register the security filter, message handler, and admin command handlers
- Start polling
- Log startup info

### 7. `bot/requirements.txt`
Pin the dependencies needed for Phase 1:
```
python-telegram-bot[job-queue]~=22.0
pydantic-settings~=2.0
pyyaml~=6.0
```
(OpenAI, mcp, tiktoken added in later phases when needed.)

### 8. `bot/Dockerfile`
Based on `python:3.12-slim`:
- Copy requirements, install deps
- Copy bot source
- Set `CMD ["python", "-m", "clawdia"]`
- Non-root user, read-only compatible

### 9. MCP server Dockerfiles (stubs)
Create minimal Dockerfiles and placeholder `server.py` files for:
- `mcp-servers/weather/` (port 8002) — simple HTTP health endpoint only
- `mcp-servers/calendar/` (port 8001) — simple HTTP health endpoint only

These just need to start and pass health checks so `docker-compose` doesn't block. Real MCP logic comes in Phases 3 and 4.

### 10. `config/mcp_servers.yaml`
Create the YAML registry file with the two server entries (weather + calendar URLs).

### 11. `docker-compose.yml`
Full compose file per the design: bot, mcp-calendar, mcp-weather, internal network, health checks, security options, resource limits.

### 12. `.env.example`
Template showing required env vars:
```
TELEGRAM_BOT_TOKEN=your-token-here
TELEGRAM_USER_ID=your-telegram-user-id
OPENAI_API_KEY=your-openai-key
```

### 13. `Makefile`
Convenience targets: `make up`, `make down`, `make logs`, `make build`, `make test` (test runs pytest, which will pass vacuously for now).

### 14. `.gitignore`
Add entries for `.env`, `__pycache__`, `client_secret.json`, `token.json`, `*.pyc`, `.pytest_cache`, etc.

### 15. Tests for Phase 1
- `tests/conftest.py` — shared fixtures
- `tests/test_security.py` — test authorized user passes, unauthorized user rejected, group chats rejected
- `tests/test_config.py` — test settings load from env vars, test defaults

---

## What this does NOT include
- No OpenAI/AI integration (Phase 2)
- No conversation manager (Phase 2)
- No MCP tool discovery or execution (Phase 3)
- No real MCP server logic (Phases 3-4)
- No scheduler (Phase 4)
- No SQLite persistence (Phase 5)

## Deliverable
A working Telegram bot that:
1. Starts up and connects to Telegram
2. Accepts messages only from the authorized user in private chats
3. Echoes back the user's message as a reply
4. Has stub MCP servers that pass health checks
5. Runs in Docker via `docker compose up`
6. Has passing unit tests for security and config
