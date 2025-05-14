from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
import config
import database as db
import api
import visualizations as viz


async def reply_to_message(message, text=None, photo=None):
    """Helper function to reply to messages."""
    try:
        kwargs = {
            "message_thread_id": (
                message.message_thread_id if message.is_topic_message else None
            ),
            "chat_id": message.chat_id,
            "reply_to_message_id": message.message_id,
        }

        if text:
            await message.get_bot().send_message(text=text, **kwargs)

        if photo:
            await message.get_bot().send_photo(photo=photo, **kwargs)

    except Exception as e:
        config.logger.error(f"Error in reply_to_message: {e}", exc_info=True)
        raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when the command /start is issued."""
    welcome_text = (
        "Welcome to the Codewars Tracker Bot! 🎯\n\n"
        "Available commands:\n"
        "/register [codewars_username] - Register your Codewars account\n"
        "/joingroup - See available groups to join\n"
        "/mystats - See your Codewars statistics\n"
        "/groupstats - See your group's statistics"
    )
    await reply_to_message(update.message, text=welcome_text)


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register a user with their Codewars username."""
    if len(context.args) != 1:
        help_text = (
            "📝 How to register:\n\n"
            "Use the command: /register [username]\n\n"
            "Examples:\n"
            "• /register john_doe\n"
            "• /register codewars_ninja\n\n"
            "To find your Codewars username:\n"
            "1. Log in to codewars.com\n"
            "2. Click your profile picture\n"
            "3. Your username is in the URL: codewars.com/users/[username]\n\n"
            "Note: Use your exact Codewars username, it's case-sensitive!"
        )
        await reply_to_message(update.message, text=help_text)
        return

    codewars_username = context.args[0]
    telegram_id = update.effective_user.id

    # Verify username and get data
    user_data = api.get_user_profile(codewars_username)
    if not user_data:
        await reply_to_message(
            update.message,
            text="Invalid Codewars username. Please check and try again.",
        )
        return

    # Update user data
    current_completed = user_data["codeChallenges"]["totalCompleted"]
    today = datetime.now().strftime("%Y-%m-%d")

    # Get existing user data and update history
    existing_user = db.get_user(telegram_id)
    history = []
    if existing_user and "history" in existing_user:
        history = existing_user["history"]

    history.append(
        {
            "date": today,
            "completed_katas": current_completed,
            "honor": user_data["honor"],
            "rank": user_data["ranks"]["overall"]["name"],
        }
    )

    # Save updated user data
    db.update_user(
        telegram_id,
        {
            "telegram_id": telegram_id,
            "codewars_username": codewars_username,
            "completed_katas": current_completed,
            "history": history,
        },
    )

    success_message = (
        f"✅ Successfully registered with Codewars username: {codewars_username}\n\n"
        "What's next?\n"
        "• Use /mystats to see your progress\n"
        "• Use /joingroup to join a group and compare stats with others\n"
        "• Complete more katas on codewars.com to see your progress!\n\n"
        "Your stats will be automatically tracked and updated."
    )
    await reply_to_message(update.message, text=success_message)


# Add other command handlers here (my_stats, group_stats, etc.)
# They would follow a similar pattern of:
# 1. Get data from database
# 2. Call API if needed
# 3. Create visualizations
# 4. Send response
