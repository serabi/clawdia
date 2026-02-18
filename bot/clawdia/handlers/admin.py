"""Admin command handlers."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status — report bot health."""
    if not update.message:
        return
    await update.message.reply_text("Bot is running.")
