"""Main module that runs the Telegram bot."""

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from .config import TELEGRAM_BOT_TOKEN, logger
from .bot.handlers import (
    start,
    register,
    my_stats,
    group_stats,
    daily_group_stats,
    weekly_stats,
    help_command,
    button_callback,
    handle_group_update,
    create_group,
    join_group,
)


def handler(application: Application):
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("creategroup", create_group))
    application.add_handler(CommandHandler("joingroup", join_group))
    application.add_handler(CommandHandler("mystats", my_stats))
    application.add_handler(CommandHandler("groupstats", group_stats))
    application.add_handler(CommandHandler("daily", daily_group_stats))
    application.add_handler(CommandHandler("weekly", weekly_stats))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Add handler for group updates
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_group_update)
    )

    return application


def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file!")
        print("Please create .env file with your bot token.")
        return

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application = handler(application)

    # Start the bot with specific update types and settings
    application.run_polling(
        allowed_updates=[
            "message",
            "edited_message",
            "channel_post",
            "edited_channel_post",
            "callback_query",
            "chat_member",
            "my_chat_member",
            "chat_join_request",
        ],
        drop_pending_updates=True,  # Ignore any pending updates
    )


if __name__ == "__main__":
    main()
