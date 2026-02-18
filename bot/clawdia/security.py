"""Telegram user ID gate — single-user authorization."""

import logging

from telegram import Update
from telegram.ext import filters

logger = logging.getLogger(__name__)


class UserGateFilter(filters.UpdateFilter):
    """Filter that only passes updates from the authorized user in private chats."""

    def __init__(self, authorized_user_id: int):
        super().__init__()
        self.authorized_user_id = authorized_user_id

    def filter(self, update: Update) -> bool:
        # Reject non-private chats (groups, supergroups, channels)
        if update.effective_chat and update.effective_chat.type != "private":
            return False

        user = update.effective_user
        if user is None or user.id != self.authorized_user_id:
            return False

        return True
