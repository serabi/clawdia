"""Clawdia bot entrypoint — wires everything together."""

import logging

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from clawdia.config import Settings
from clawdia.handlers.admin import status_command
from clawdia.handlers.chat import handle_message
from clawdia.security import UserGateFilter

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    settings = Settings()
    logger.info("Starting Clawdia bot (model=%s, user_id=%s)", settings.openai_model, settings.telegram_user_id)

    gate = UserGateFilter(settings.telegram_user_id)

    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .build()
    )

    app.add_handler(CommandHandler("status", status_command, filters=gate))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & gate, handle_message)
    )

    logger.info("Bot is ready — polling for updates")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
