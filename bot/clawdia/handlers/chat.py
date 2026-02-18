"""Chat message handler — Phase 1 echo stub."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo the user's message back. Replaced with AI handler in Phase 2."""
    if not update.message or not update.message.text:
        return
    await update.message.reply_text(update.message.text)
