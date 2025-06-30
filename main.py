"""Main module that runs the Telegram bot."""

from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
)
from config import TELEGRAM_BOT_TOKEN, logger
from bot.handlers import (
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


def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file!")
        print("Please create .env file with your bot token.")
        return

    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("register", register))
    dp.add_handler(CommandHandler("creategroup", create_group))
    dp.add_handler(CommandHandler("joingroup", join_group))
    dp.add_handler(CommandHandler("mystats", my_stats))
    dp.add_handler(CommandHandler("groupstats", group_stats))
    dp.add_handler(CommandHandler("daily", daily_group_stats))
    dp.add_handler(CommandHandler("weekly", weekly_stats))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CallbackQueryHandler(button_callback))

    # Add handler for group updates
    dp.add_handler(
        MessageHandler(Filters.status_update.new_chat_members, handle_group_update)
    )

    updater.start_polling(drop_pending_updates=True)
    updater.idle()


if __name__ == "__main__":
    main()
