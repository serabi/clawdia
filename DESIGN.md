# Clawdia: Telegram Bot with MCP Integration

## Context

Build a single-user Telegram bot ("Clawdia") that acts as a personal AI assistant you can chat back and forth with. It uses OpenAI's GPT-5.2 via the Responses API (Codex plan), and connects to MCP servers for calendar and weather tools at launch. Runs on your Raspberry Pi 5 in Docker. Designed to be easily extensible with new MCP servers.

## Architecture Overview

```
┌──────────────────────────────────────────────────┐
│                 Docker Compose                    │
│                                                   │
│  ┌───────────┐  Streamable HTTP  ┌────────────┐  │
│  │           │◄─────────────────►│ MCP Weather │  │
│  │  Clawdia  │                   └────────────┘  │
│  │   Bot     │  Streamable HTTP  ┌────────────┐  │
│  │           │◄─────────────────►│MCP Calendar │  │
│  │           │                   └────────────┘  │
│  └───────────┘                                    │
│       │                                           │
└───────┼───────────────────────────────────────────┘
        │  outbound only
        ▼
   Telegram API + OpenAI Responses API (GPT-5.2)
```

Later phases add vault MCP server, git-sync sidecar, task management, and comms.

## Message Flow

The bot maintains a persistent conversation — you chat back and forth naturally via Telegram. Each message builds on the prior context.

```
You send Telegram message
        ↓
  User ID gate (single authorized user)
        ↓
  Conversation manager appends to history
        ↓
  OpenAI Responses API call (async) with:
    - instructions (Clawdia's persona/system prompt)
    - input (full conversation history)
    - tools (discovered MCP tools as function definitions)
    - reasoning.effort = "medium" (configurable)
        ↓
  Response contains output items:
    ├─ function_call items → route to MCP server (parallel) → append results → loop back
    └─ message item → split if >4096 chars → send to Telegram, save to history
```

Conversation history persists in memory for the session and is backed by a lightweight SQLite store so context survives container restarts. The sliding window trims by both item count and estimated token budget, evicting oldest complete exchanges to stay within limits.

## Key Design Decisions

### 1. GPT-5.2 via Responses API

Using GPT-5.2 (`gpt-5.2`) through the Responses API, which is the recommended interface:
- `instructions` param for system prompt (Clawdia's persona)
- `input` for conversation history (replaces `messages`)
- `reasoning.effort` to control thinking depth (default `medium`, save cost on Pi)
- Tool schema: fields (`name`, `description`, `parameters`) are **top-level** (no `function` wrapper)
- Response returns typed `output` items (`function_call`, `message`) — no `choices` array
- **Critical**: use `item.call_id` (not `item.id`) when returning `function_call_output`
- Can pass previous turn's chain-of-thought for higher cache hits and lower latency

```python
# Responses API tool definition (different from ChatCompletions!)
{
    "type": "function",
    "name": "weather__get_current",        # top-level, no "function" wrapper
    "description": "Get current weather",
    "parameters": { ... },
    "strict": True,                        # guarantees schema-valid arguments
}

# Tool result format
{
    "type": "function_call_output",
    "call_id": tool_call.call_id,          # NOT tool_call.id!
    "output": json.dumps(result),
}
```

Model is configurable via env var. Options under Codex plan:
- `gpt-5.2` — recommended default, best function calling
- `gpt-5.2-pro` — deeper reasoning for harder problems
- `gpt-5-mini` — cost-optimized, good for lighter queries
- `gpt-5-nano` — cheapest, for simple tasks

### 2. Custom function bridge (not native MCP tool type)

The Responses API has a native `"type": "mcp"` tool, but it requires publicly reachable HTTPS endpoints. Since our MCP servers run on the local Docker network, we use custom function tools and bridge to MCP ourselves. This also gives full control over tool execution and avoids exposing anything to the internet.

### 3. Streamable HTTP for MCP transport

Each MCP server runs in its own container on the internal Docker network. HTTP transport is the natural fit for inter-container communication.

### 4. Conversational by design

This is a chat bot, not a command bot. The conversation manager maintains full back-and-forth history so Clawdia remembers what you've been talking about. You can ask follow-up questions, reference earlier messages, and have a natural conversation. Tool calls happen transparently in the background when needed.

### 5. Tool namespacing

Tools namespaced as `servername__toolname` to avoid collisions across MCP servers. The bot discovers tools at startup and translates MCP schemas to Responses API format. Server and tool names must not themselves contain `__` — the bridge validates this at discovery time.

### 6. YAML-driven MCP registry

Adding a new MCP server = new Docker service + one YAML entry. No bot code changes.

```yaml
# config/mcp_servers.yaml
servers:
  weather:
    url: http://mcp-weather:8002/mcp
    description: "Weather forecasts via Open-Meteo"
  calendar:
    url: http://mcp-calendar:8001/mcp
    description: "Google Calendar integration"
```

### 7. Fully async

The bot, AI client, and MCP calls are all async (`asyncio`). The OpenAI client uses `AsyncOpenAI` so API calls never block the event loop. When the model returns multiple tool calls in a single response, they execute concurrently via `asyncio.gather`.

## Clawdia's Persona

The system prompt establishes Clawdia as a helpful, concise personal assistant. Key traits:

- **Tone**: Friendly but not overly chatty. Direct answers, no filler.
- **Tools**: Uses tools proactively when the question warrants it (e.g., "what's my day look like?" triggers calendar lookup without being asked).
- **Transparency**: Briefly mentions when it's checking a tool ("Let me check your calendar...") so the user knows what's happening.
- **Scope**: Knows it's running on a Raspberry Pi for a single user. Doesn't pretend to be more than it is.

The system prompt is defined in `bot/clawdia/ai/prompts.py` and loaded at startup. It is not user-configurable at runtime (changing it requires redeployment).

## Project Structure

```
clawdia/
├── docker-compose.yml
├── .env.example
├── Makefile
├── bot/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── clawdia/
│       ├── __init__.py
│       ├── __main__.py          # entrypoint, wires everything together
│       ├── config.py            # pydantic-settings config loader
│       ├── security.py          # telegram user ID gate
│       ├── handlers/
│       │   ├── __init__.py
│       │   ├── chat.py          # message handler (telegram → openai → mcp → reply)
│       │   └── admin.py         # /status, /reload commands
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── client.py        # GPT-5.2 Responses API loop with tool execution
│       │   ├── tool_bridge.py   # MCP↔Responses API schema translation
│       │   ├── conversation.py  # sliding window conversation history
│       │   └── prompts.py       # system prompt / persona definition
│       ├── mcp/
│       │   ├── __init__.py
│       │   ├── registry.py      # connects to all MCP servers, discovers tools
│       │   └── client.py        # single MCP server session wrapper
│       └── scheduler/
│           ├── __init__.py
│           └── jobs.py          # morning briefing
├── mcp-servers/
│   ├── calendar/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── server.py           # Google Calendar via FastMCP
│   └── weather/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── server.py           # Open-Meteo API via FastMCP (free, no key)
├── config/
│   ├── mcp_servers.yaml        # MCP server URLs and descriptions
│   └── schedule.yaml           # cron-like job schedule config
└── tests/
    ├── conftest.py
    ├── test_conversation.py    # conversation manager unit tests
    ├── test_tool_bridge.py     # schema translation + namespacing tests
    ├── test_security.py        # user ID gate tests
    └── test_client.py          # AI client loop tests (mocked OpenAI)
```

## Core Components

### Conversation Manager (`ai/conversation.py`)

This is what makes Clawdia conversational. It maintains the full `input` items list with dual-limit trimming (item count and estimated token budget) that evicts complete exchanges rather than individual items:

```python
import tiktoken

class ConversationManager:
    """Maintains back-and-forth chat history for the Responses API."""

    def __init__(self, max_items: int = 80, max_tokens: int = 60_000):
        self._items: list = []
        self._max_items = max_items
        self._max_tokens = max_tokens
        self._encoder = tiktoken.encoding_for_model("gpt-4o")  # close enough for estimation

    def add_user_message(self, text: str):
        self._items.append({"role": "user", "content": text})
        self._trim()

    def add_response_output(self, output_items: list):
        """Append the model's output items (messages, tool calls, etc.)."""
        self._items.extend(output_items)
        self._trim()

    def add_tool_result(self, call_id: str, output: str):
        self._items.append({
            "type": "function_call_output",
            "call_id": call_id,
            "output": output,
        })

    def get_input(self) -> list:
        return list(self._items)

    def _estimate_tokens(self) -> int:
        """Rough token estimate across all items."""
        total = 0
        for item in self._items:
            if isinstance(item, dict):
                text = item.get("content") or item.get("output") or ""
                total += len(self._encoder.encode(str(text)))
            else:
                # Response API output objects — estimate from string repr
                total += len(self._encoder.encode(str(item)))
        return total

    def _trim(self):
        """Drop oldest complete exchanges until within both limits.

        Evicts in logical units: finds the first user message boundary
        and removes everything before it, so tool call / result pairs
        are never orphaned.
        """
        while (len(self._items) > self._max_items
               or self._estimate_tokens() > self._max_tokens):
            # Find the second user message — everything before it is the oldest exchange
            second_user = None
            for i, item in enumerate(self._items):
                if isinstance(item, dict) and item.get("role") == "user":
                    if i > 0:
                        second_user = i
                        break
            if second_user is None:
                break  # only one exchange left, can't trim further
            self._items = self._items[second_user:]
```

**Known limitation**: Conversation history is in-memory and will be lost on container restart. Phase 5 adds optional SQLite-backed persistence so history survives restarts.

### AI Client Loop (`ai/client.py`)

Uses `AsyncOpenAI` so API calls never block the event loop. Tool calls returned in a single response are executed concurrently:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def respond(conversation: ConversationManager, tools: list,
                  registry: McpRegistry, settings: Settings) -> str:
    for _ in range(settings.max_tool_rounds):
        try:
            response = await client.responses.create(
                model=settings.openai_model,  # "gpt-5.2"
                instructions=SYSTEM_PROMPT,
                input=conversation.get_input(),
                tools=tools,
                reasoning={"effort": settings.reasoning_effort},  # "medium"
            )
        except openai.RateLimitError:
            return "I'm being rate-limited by OpenAI. Try again in a moment."
        except openai.APIError as e:
            logger.error("OpenAI API error: %s", e)
            return "Something went wrong talking to the AI. Please try again."

        conversation.add_response_output(response.output)

        tool_calls = [i for i in response.output if i.type == "function_call"]
        if not tool_calls:
            return response.output_text  # final text answer

        # Execute tool calls concurrently
        async def _exec(tc):
            server, tool = parse_function_name(tc.name)
            result = await registry.call_tool(server, tool, json.loads(tc.arguments))
            conversation.add_tool_result(tc.call_id, json.dumps(result))

        await asyncio.gather(*[_exec(tc) for tc in tool_calls])

    return "I wasn't able to complete that within the allowed steps."
```

### Tool Bridge (`ai/tool_bridge.py`)

Translates MCP tool schemas to Responses API function format. Uses `strict: True` by default so the model is guaranteed to produce schema-valid arguments. Falls back to `strict: False` only if the MCP tool's schema uses JSON Schema features unsupported by strict mode.

```python
def mcp_tool_to_responses_schema(server_name: str, tool) -> dict:
    _validate_name(server_name, tool.name)
    return {
        "type": "function",
        "name": f"{server_name}__{tool.name}",
        "description": tool.description or "",
        "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        "strict": True,
    }

def parse_function_name(name: str) -> tuple[str, str]:
    parts = name.split("__", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid namespaced tool name: {name!r} (expected 'server__tool')")
    return parts[0], parts[1]

def _validate_name(server_name: str, tool_name: str):
    if "__" in server_name:
        raise ValueError(f"Server name must not contain '__': {server_name!r}")
    if "__" in tool_name:
        raise ValueError(f"Tool name must not contain '__': {tool_name!r}")
```

### Chat Handler (`handlers/chat.py`)

The Telegram handler that ties it all together. Handles Markdown parse failures gracefully and splits long messages to stay within Telegram's 4096-character limit:

```python
TELEGRAM_MAX_LENGTH = 4096

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message — this is the main chat loop."""
    conversation: ConversationManager = context.bot_data["conversation"]
    registry: McpRegistry = context.bot_data["mcp_registry"]
    tools = registry.get_openai_tools()

    # Add user's message to conversation history
    conversation.add_user_message(update.message.text)

    # Show typing indicator while thinking
    await update.message.chat.send_action("typing")

    # Get Clawdia's response (may involve tool calls)
    response_text = await respond(conversation, tools, registry, settings)

    # Split and send — handles Telegram's 4096-char limit
    for chunk in _split_message(response_text, TELEGRAM_MAX_LENGTH):
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except telegram.error.BadRequest:
            # Malformed Markdown from the LLM — fall back to plain text
            await update.message.reply_text(chunk)


def _split_message(text: str, limit: int) -> list[str]:
    """Split text into chunks that fit within Telegram's message limit.

    Tries to break at paragraph boundaries, then sentence boundaries,
    then hard-wraps as a last resort.
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Try to split at last paragraph break within limit
        cut = text.rfind("\n\n", 0, limit)
        if cut == -1:
            cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = text.rfind(" ", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    return chunks
```

### MCP Registry (`mcp/registry.py`)

Connects to all servers listed in `config/mcp_servers.yaml` via Streamable HTTP. Discovers tools at startup, maintains sessions, routes `call_tool` requests.

The registry handles MCP server failures gracefully:
- **Connection errors during `call_tool`**: Attempts a single reconnect before failing. Returns a structured error to the AI so it can inform the user rather than crashing.
- **Startup**: If a server is unreachable at boot, the bot starts anyway with reduced tool availability and logs a warning. The `/status` admin command shows which servers are connected.
- **Tool rediscovery**: The `/reload` admin command re-connects to all servers and re-discovers tools, useful after an MCP server is restarted with new tools.

### Scheduler (`scheduler/jobs.py`)

Uses `python-telegram-bot`'s built-in `JobQueue` (APScheduler-backed). Morning briefing job calls calendar + weather MCP tools directly and sends a formatted summary. Schedule configurable via `schedule.yaml`.

## Security Model

| Concern | Mitigation |
|---|---|
| Unauthorized users | Single `telegram_user_id` check on every update; messages from other users silently ignored (no error response that leaks bot existence) |
| Group chats | Bot ignores all group/supergroup messages; only processes private chats from the authorized user |
| Secrets | `.env` file (gitignored), never baked into images; no secrets in docker-compose.yml or YAML configs |
| MCP blast radius | Each server in own container, `read_only: true`, no shell/exec tools, no network access except internal |
| API cost | `max_tool_rounds` cap (default 5); `reasoning.effort` tunable; per-user rate limiting not needed (single user) |
| Network | MCP servers on internal Docker network only, no published ports; bot has outbound-only access to Telegram and OpenAI APIs |
| No code execution | No shell/exec/eval tools in any MCP server; tool schemas are validated at discovery |
| Container hardening | All containers run read-only, `no-new-privileges: true`, dropped capabilities, tmpfs for writable paths |
| MCP tool output | Tool results are serialized to JSON strings before being passed to the model; no raw injection into prompts |
| Credential storage | Google Calendar OAuth credentials stored in a named Docker volume, mounted read-only; never committed to git |
| Logging | Secrets and API keys are never logged; structured logging redacts sensitive fields |

## Docker Compose Topology

```yaml
services:
  bot:
    build: ./bot
    depends_on:
      mcp-calendar:
        condition: service_healthy
      mcp-weather:
        condition: service_healthy
    env_file: .env
    networks: [clawdia-internal]
    read_only: true
    tmpfs: [/tmp]
    mem_limit: 512m
    cpus: 1.0
    security_opt: ["no-new-privileges:true"]
    restart: unless-stopped

  mcp-calendar:
    build: ./mcp-servers/calendar
    expose: ["8001"]
    volumes: [calendar-creds:/credentials:ro]
    networks: [clawdia-internal]
    read_only: true
    tmpfs: [/tmp]
    mem_limit: 128m
    cpus: 0.5
    security_opt: ["no-new-privileges:true"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  mcp-weather:
    build: ./mcp-servers/weather
    expose: ["8002"]
    networks: [clawdia-internal]
    read_only: true
    tmpfs: [/tmp]
    mem_limit: 128m
    cpus: 0.5
    security_opt: ["no-new-privileges:true"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped

networks:
  clawdia-internal:
    driver: bridge

volumes:
  calendar-creds:
```

## Dependencies

**Bot**: `python-telegram-bot[job-queue]~=22.0`, `openai>=1.75`, `mcp~=1.x`, `pydantic-settings~=2.x`, `pyyaml~=6.0`, `tiktoken~=0.8`
**Weather MCP**: `mcp~=1.x`, `httpx~=0.28`
**Calendar MCP**: `mcp~=1.x`, `google-api-python-client~=2.x`, `google-auth~=2.x`
**Test**: `pytest~=8.x`, `pytest-asyncio~=0.24`, `respx~=0.22` (httpx mocking)
**Base image**: `python:3.12-slim` (ARM64 available)

Note: `openai>=1.75` is pinned to a minimum that supports the Responses API and GPT-5.2 function calling. The `~=1.x` range is too broad and may pull in versions that predate these features.

## Google Calendar OAuth Setup

The Calendar MCP server needs Google OAuth2 credentials. Since the bot runs headless on a Raspberry Pi, the OAuth browser flow is performed once from a machine with a browser:

1. Create a Google Cloud project and enable the Calendar API.
2. Create OAuth2 credentials (Desktop app type) and download `client_secret.json`.
3. On a machine with a browser, run the included setup script:
   ```bash
   cd mcp-servers/calendar
   python setup_oauth.py  # opens browser, completes consent, writes token.json
   ```
4. Copy both `client_secret.json` and `token.json` into the Docker volume:
   ```bash
   docker volume create clawdia_calendar-creds
   docker run --rm -v clawdia_calendar-creds:/creds -v $(pwd):/src alpine \
     cp /src/client_secret.json /src/token.json /creds/
   ```
5. The MCP server mounts this volume read-only and refreshes the access token automatically using the stored refresh token.

These credential files must **never** be committed to git. The `.gitignore` includes `client_secret.json` and `token.json`.

## Graceful Shutdown

On `SIGTERM` / `SIGINT` (Docker stop), the bot:
1. Stops accepting new Telegram updates.
2. Waits for any in-flight OpenAI API call or MCP tool execution to complete (with a timeout).
3. Closes all MCP client sessions cleanly.
4. Exits.

`python-telegram-bot` handles most of this via its `Application.stop()` / `shutdown()` hooks. The MCP session cleanup is registered as a shutdown callback.

## Testing Strategy

### Unit Tests
- **Conversation manager**: Trimming logic, exchange boundary detection, token estimation.
- **Tool bridge**: Schema translation, namespace validation, `parse_function_name` edge cases.
- **Security gate**: Authorized user passes, unauthorized user rejected, group chats rejected.

### Integration Tests (mocked externals)
- **AI client loop**: Mock `AsyncOpenAI` to return canned responses with and without tool calls. Verify the loop executes tools, appends results, and terminates correctly.
- **MCP registry**: Mock HTTP responses to simulate tool discovery and `call_tool` round-trips.
- **Chat handler**: End-to-end with mocked OpenAI and MCP — verify Telegram reply, message splitting, Markdown fallback.

### Manual Smoke Tests
- `docker compose up -d` — all services start healthy.
- Send messages and verify conversational context is maintained.
- Trigger tool calls ("What's the weather?") and verify end-to-end.
- Kill an MCP server and verify the bot degrades gracefully.

Tests run with `pytest` from the repo root: `make test`.

## Implementation Phases

### Phase 1: Skeleton
- Project structure, docker-compose, Dockerfiles
- `config.py`, `security.py`, basic echo handler
- Verify bot starts and responds on Telegram from Pi

### Phase 2: Conversational AI
- `ai/client.py` using `AsyncOpenAI` and GPT-5.2 Responses API
- `conversation.py` with dual-limit sliding window (items + tokens)
- `ai/prompts.py` with Clawdia's persona/system prompt
- Error handling for OpenAI API failures (rate limits, timeouts)
- Back-and-forth chat working — no tools yet, just conversation

### Phase 3: MCP Infrastructure + Weather
- Weather MCP server with `/health` endpoint (simplest — free Open-Meteo API, no auth)
- `mcp/registry.py` with connection management and `ai/tool_bridge.py` with strict validation
- Parallel tool execution via `asyncio.gather`
- Telegram message splitting and Markdown fallback
- Full loop: Telegram → Responses API → MCP tool call → response
- End-to-end test: "What's the weather?"

### Phase 4: Calendar + Scheduler
- Google Calendar MCP server with OAuth setup script and `/health` endpoint
- `scheduler/jobs.py` with morning briefing job
- Schedule config via `schedule.yaml`

### Phase 5: Polish + Persistence
- Structured logging (with secret redaction)
- Optional SQLite conversation persistence (survives restarts)
- Graceful shutdown with MCP session cleanup
- Makefile convenience targets (`make up`, `make logs`, `make test`, `make restart`)
- Unit and integration test suite

## Future Phases (not in this build)

- **Vault integration**: Git-sync sidecar, vault MCP server with BM25 search
- **Task management**: Todoist or Linear MCP server
- **Comms**: Email summary MCP server, RSS feed reader

## Verification

1. `docker compose up -d` — all 3 services start healthy (health checks pass)
2. Send messages back and forth — Clawdia maintains context across messages
3. Ask "What's the weather?" → Clawdia calls weather MCP, returns forecast
4. Ask a follow-up like "And tomorrow?" → Clawdia uses conversation context
5. Send a message that triggers a very long response → bot splits into multiple Telegram messages
6. Morning briefing fires at configured time with calendar + weather
7. Message from unauthorized Telegram account → silently ignored
8. `docker compose restart mcp-weather` → bot logs warning, recovers on next tool call
9. `make test` → all unit and integration tests pass
