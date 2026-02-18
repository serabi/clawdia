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
  OpenAI Responses API call with:
    - instructions (Clawdia's persona/system prompt)
    - input (full conversation history)
    - tools (discovered MCP tools as function definitions)
    - reasoning.effort = "medium" (configurable)
        ↓
  Response contains output items:
    ├─ function_call items → route to MCP server → append result → loop back
    └─ message item → send text to Telegram, save to history
```

Conversation history persists in memory for the session. The sliding window keeps the last N exchanges so context stays relevant without blowing up token usage.

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
    "strict": True,
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

Tools namespaced as `servername__toolname` to avoid collisions across MCP servers. The bot discovers tools at startup and translates MCP schemas to Responses API format.

### 6. YAML-driven MCP registry

Adding a new MCP server = new Docker service + one YAML entry. No bot code changes.

## Project Structure

```
clawdia-serabi/
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
│       │   └── conversation.py  # sliding window conversation history
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
└── config/
    ├── mcp_servers.yaml        # MCP server URLs and descriptions
    └── schedule.yaml           # cron-like job schedule config
```

## Core Components

### Conversation Manager (`ai/conversation.py`)

This is what makes Clawdia conversational. It maintains the full `input` items list:

```python
class ConversationManager:
    """Maintains back-and-forth chat history for the Responses API."""

    def __init__(self, max_items: int = 80):
        self._items: list = []
        self._max_items = max_items

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

    def _trim(self):
        """Drop oldest exchanges, keeping tool call/result pairs intact."""
        while len(self._items) > self._max_items:
            self._items.pop(0)
```

### AI Client Loop (`ai/client.py`)

```python
async def respond(conversation: ConversationManager, tools: list,
                  registry: McpRegistry, settings: Settings) -> str:
    for _ in range(settings.max_tool_rounds):
        response = client.responses.create(
            model=settings.openai_model,  # "gpt-5.2"
            instructions=SYSTEM_PROMPT,
            input=conversation.get_input(),
            tools=tools,
            reasoning={"effort": settings.reasoning_effort},  # "medium"
        )
        conversation.add_response_output(response.output)

        tool_calls = [i for i in response.output if i.type == "function_call"]
        if not tool_calls:
            return response.output_text  # final text answer

        for tc in tool_calls:
            server, tool = parse_function_name(tc.name)
            result = await registry.call_tool(server, tool, json.loads(tc.arguments))
            conversation.add_tool_result(tc.call_id, json.dumps(result))

    return "I wasn't able to complete that within the allowed steps."
```

### Tool Bridge (`ai/tool_bridge.py`)

Translates MCP tool schemas to Responses API function format:

```python
def mcp_tool_to_responses_schema(server_name: str, tool) -> dict:
    return {
        "type": "function",
        "name": f"{server_name}__{tool.name}",
        "description": tool.description or "",
        "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        "strict": False,
    }

def parse_function_name(name: str) -> tuple[str, str]:
    return name.split("__", 1)
```

### Chat Handler (`handlers/chat.py`)

The Telegram handler that ties it all together:

```python
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

    # Send back to Telegram
    await update.message.reply_text(response_text, parse_mode="Markdown")
```

### MCP Registry (`mcp/registry.py`)

Connects to all servers listed in `config/mcp_servers.yaml` via Streamable HTTP. Discovers tools at startup, maintains sessions, routes `call_tool` requests.

### Scheduler (`scheduler/jobs.py`)

Uses `python-telegram-bot`'s built-in `JobQueue` (APScheduler-backed). Morning briefing job calls calendar + weather MCP tools directly and sends a formatted summary. Schedule configurable via `schedule.yaml`.

## Security Model

| Concern | Mitigation |
|---|---|
| Unauthorized users | Single `telegram_user_id` check on every update |
| Secrets | `.env` file (gitignored), never baked into images |
| MCP blast radius | Each server in own container, `read_only: true`, no shell/exec tools |
| API cost | `max_tool_rounds` cap (default 5); `reasoning.effort` tunable |
| Network | MCP servers on internal Docker network only, no published ports |
| No code execution | No shell/exec/eval tools in any MCP server |

## Docker Compose Topology

```yaml
services:
  bot:
    build: ./bot
    depends_on: [mcp-calendar, mcp-weather]
    env_file: .env
    networks: [clawdia-internal]
    restart: unless-stopped

  mcp-calendar:
    build: ./mcp-servers/calendar
    expose: ["8001"]
    volumes: [calendar-creds:/credentials:ro]
    networks: [clawdia-internal]
    read_only: true
    tmpfs: [/tmp]
    restart: unless-stopped

  mcp-weather:
    build: ./mcp-servers/weather
    expose: ["8002"]
    networks: [clawdia-internal]
    read_only: true
    tmpfs: [/tmp]
    restart: unless-stopped

networks:
  clawdia-internal:
    driver: bridge

volumes:
  calendar-creds:
```

## Dependencies

**Bot**: `python-telegram-bot[job-queue]~=22.x`, `openai~=1.x`, `mcp~=1.x`, `pydantic-settings~=2.x`, `pyyaml~=6.0`
**Weather MCP**: `mcp~=1.x`, `httpx~=0.28`
**Calendar MCP**: `mcp~=1.x`, `google-api-python-client~=2.x`, `google-auth~=2.x`
**Base image**: `python:3.12-slim` (ARM64 available)

## Implementation Phases

### Phase 1: Skeleton
- Project structure, docker-compose, Dockerfiles
- `config.py`, `security.py`, basic echo handler
- Verify bot starts and responds on Telegram from Pi

### Phase 2: Conversational AI
- `ai/client.py` using GPT-5.2 Responses API
- `conversation.py` with sliding window history
- Back-and-forth chat working — no tools yet, just conversation
- System prompt with Clawdia's persona

### Phase 3: MCP Infrastructure + Weather
- Weather MCP server (simplest — free Open-Meteo API, no auth)
- `mcp/registry.py` and `ai/tool_bridge.py`
- Full loop: Telegram → Responses API → MCP tool call → response
- End-to-end test: "What's the weather?"

### Phase 4: Calendar + Scheduler
- Google Calendar MCP server (one-time OAuth browser flow for credentials)
- `scheduler/jobs.py` with morning briefing job
- Schedule config via `schedule.yaml`

### Phase 5: Polish
- Error handling, graceful degradation when MCP server is down
- Structured logging
- Makefile convenience targets

## Future Phases (not in this build)

- **Vault integration**: Git-sync sidecar, vault MCP server with BM25 search
- **Task management**: Todoist or Linear MCP server
- **Comms**: Email summary MCP server, RSS feed reader

## Verification

1. `docker compose up -d` — all 3 services start healthy
2. Send messages back and forth — Clawdia maintains context across messages
3. Ask "What's the weather?" → Clawdia calls weather MCP, returns forecast
4. Ask a follow-up like "And tomorrow?" → Clawdia uses conversation context
5. Morning briefing fires at configured time with calendar + weather
6. Message from unauthorized Telegram account → silently ignored
