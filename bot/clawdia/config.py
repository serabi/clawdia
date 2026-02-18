"""Configuration loader using pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Bot configuration loaded from environment variables."""

    telegram_bot_token: str
    telegram_user_id: int
    openai_api_key: str
    openai_model: str = "gpt-5.2"
    reasoning_effort: str = "medium"
    max_tool_rounds: int = 5
    mcp_config_path: Path = Path("/app/config/mcp_servers.yaml")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
