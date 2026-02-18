"""Tests for Codex OAuth credential loading."""

import json
from pathlib import Path

import pytest

from clawdia.auth import load_codex_credentials


@pytest.fixture
def auth_json(tmp_path):
    """Write a mock auth.json and return its path."""

    def _write(data):
        p = tmp_path / "auth.json"
        p.write_text(json.dumps(data))
        return p

    return _write


def test_load_valid_credentials(auth_json):
    data = {
        "openai-codex": {
            "type": "oauth",
            "access": "eyJ_access_token",
            "refresh": "rt_refresh_token",
            "expires": 1761735358000,
        },
        "https://api.openai.com/auth": {
            "chatgpt_account_id": "acct-123",
            "chatgpt_plan_type": "plus",
        },
    }
    creds = load_codex_credentials(auth_json(data))
    assert creds is not None
    assert creds.access_token == "eyJ_access_token"
    assert creds.refresh_token == "rt_refresh_token"
    assert creds.account_id == "acct-123"
    assert creds.expires == pytest.approx(1761735358.0)


def test_missing_file_returns_none():
    creds = load_codex_credentials(Path("/nonexistent/auth.json"))
    assert creds is None


def test_no_oauth_entry_returns_none(auth_json):
    data = {"openai-codex-api": {"type": "api", "key": "sk-123"}}
    creds = load_codex_credentials(auth_json(data))
    assert creds is None


def test_wrong_type_returns_none(auth_json):
    data = {"openai-codex": {"type": "api", "key": "sk-123"}}
    creds = load_codex_credentials(auth_json(data))
    assert creds is None


def test_missing_account_id_defaults_empty(auth_json):
    data = {
        "openai-codex": {
            "type": "oauth",
            "access": "tok",
            "refresh": "rt",
            "expires": 1000000000000,
        },
    }
    creds = load_codex_credentials(auth_json(data))
    assert creds is not None
    assert creds.account_id == ""
