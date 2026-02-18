"""OAuth token management for ChatGPT plan authentication.

Reads credentials from Codex CLI's auth.json (produced by `codex login`)
and refreshes access tokens automatically. Falls back to a standard API key
if no Codex credentials are available.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TOKEN_ENDPOINT = "https://auth.openai.com/oauth/token"
CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CHATGPT_BASE_URL = "https://chatgpt.com/backend-api/codex"
REFRESH_MARGIN_S = 5 * 60  # refresh 5 minutes before expiry


@dataclass
class CodexCredentials:
    """Credentials loaded from Codex auth.json."""

    access_token: str
    refresh_token: str
    account_id: str
    expires: float  # unix timestamp in seconds


def load_codex_credentials(path: Path) -> CodexCredentials | None:
    """Read Codex auth.json and extract ChatGPT OAuth credentials.

    Returns None if the file doesn't exist or lacks OAuth credentials.
    """
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read codex auth.json: %s", e)
        return None

    oauth = data.get("openai-codex")
    if not oauth or oauth.get("type") != "oauth":
        return None

    access = oauth.get("access")
    refresh = oauth.get("refresh")
    expires = oauth.get("expires")

    if not access or not refresh:
        logger.warning("Codex auth.json missing access or refresh token")
        return None

    if not isinstance(expires, (int, float)):
        logger.warning("Codex auth.json has invalid expires value: %r", expires)
        return None

    auth_meta = data.get("https://api.openai.com/auth", {})
    account_id = auth_meta.get("chatgpt_account_id", "")

    return CodexCredentials(
        access_token=access,
        refresh_token=refresh,
        account_id=account_id,
        expires=expires / 1000,  # ms → seconds
    )


async def refresh_access_token(creds: CodexCredentials) -> CodexCredentials:
    """Refresh the access token using the refresh token."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as client:
        resp = await client.post(
            TOKEN_ENDPOINT,
            data={
                "grant_type": "refresh_token",
                "client_id": CODEX_CLIENT_ID,
                "refresh_token": creds.refresh_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    creds.access_token = data["access_token"]
    if "refresh_token" in data:
        creds.refresh_token = data["refresh_token"]
    # expires_in is in seconds
    creds.expires = time.time() + data.get("expires_in", 3600)
    logger.info("Refreshed ChatGPT access token")
    return creds


async def ensure_valid_token(creds: CodexCredentials) -> CodexCredentials:
    """Refresh the token if it's expired or about to expire."""
    if time.time() + REFRESH_MARGIN_S >= creds.expires:
        return await refresh_access_token(creds)
    return creds
