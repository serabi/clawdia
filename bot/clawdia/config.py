"""Configuration loader using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Bot configuration loaded from environment variables."""

    telegram_bot_token: str
    telegram_user_id: int

    # Auth: Codex auth.json from ChatGPT plan (primary), or API key (fallback).
    # Run `codex login` on a machine with a browser, then copy ~/.codex/auth.json
    # into the codex-auth Docker volume.
    codex_auth_path: Path = Path("/credentials/codex/auth.json")
    openai_api_key: str | None = None

    openai_model: str = "gpt-5.2"
    reasoning_effort: str = "medium"
    max_tool_rounds: int = 5
    mcp_config_path: Path = Path("/app/config/mcp_servers.yaml")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
