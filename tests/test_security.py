"""Tests for the Telegram user ID security gate."""

from unittest.mock import MagicMock

import pytest

from clawdia.security import UserGateFilter


AUTHORIZED_ID = 123456789
UNAUTHORIZED_ID = 987654321


@pytest.fixture
def gate():
    return UserGateFilter(AUTHORIZED_ID)


@pytest.fixture
def make_update():
    """Factory for mock Telegram updates."""

    def _make(user_id: int, chat_type: str = "private"):
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = user_id
        update.effective_chat = MagicMock()
        update.effective_chat.type = chat_type
        return update

    return _make


def test_authorized_user_passes(gate, make_update):
    update = make_update(AUTHORIZED_ID)
    assert gate.filter(update) is True


def test_unauthorized_user_rejected(gate, make_update):
    update = make_update(UNAUTHORIZED_ID)
    assert gate.filter(update) is False


def test_group_chat_rejected(gate, make_update):
    update = make_update(AUTHORIZED_ID, chat_type="group")
    assert gate.filter(update) is False


def test_supergroup_chat_rejected(gate, make_update):
    update = make_update(AUTHORIZED_ID, chat_type="supergroup")
    assert gate.filter(update) is False


def test_no_user_rejected(gate):
    update = MagicMock()
    update.effective_user = None
    update.effective_chat = MagicMock()
    update.effective_chat.type = "private"
    assert gate.filter(update) is False
