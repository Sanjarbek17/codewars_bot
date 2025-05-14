import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import requests
from tinydb import TinyDB, Query
import json
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Initialize TinyDB
db = TinyDB("db.json")
users_table = db.table("users")
groups_table = db.table("groups")

# Codewars API
CODEWARS_API_BASE = "https://www.codewars.com/api/v1/users/"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when the command /start is issued."""
    await update.message.reply_text(
        "Welcome to the Codewars Tracker Bot! 🎯\n\n"
        "Available commands:\n"
        "/register [codewars_username] - Register your Codewars account\n"
        "/creategroup [group_name] - Create a new group\n"
        "/joingroup - See available groups to join\n"
        "/mystats - See your Codewars statistics\n"
        "/groupstats - See your group's statistics"
    )


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register a user with their Codewars username."""
    if len(context.args) != 1:
        await update.message.reply_text(
            "Please provide your Codewars username: /register [username]"
        )
        return

    codewars_username = context.args[0]
    telegram_id = update.effective_user.id

    # Verify if the Codewars username exists
    try:
        response = requests.get(f"{CODEWARS_API_BASE}{codewars_username}")
        if response.status_code != 200:
            await update.message.reply_text(
                "Invalid Codewars username. Please check and try again."
            )
            return

        user_data = response.json()
        User = Query()
        users_table.upsert(
            {
                "telegram_id": telegram_id,
                "codewars_username": codewars_username,
                "completed_katas": user_data["codeChallenges"]["totalCompleted"],
            },
            User.telegram_id == telegram_id,
        )

        await update.message.reply_text(
            f"Successfully registered with Codewars username: {codewars_username}"
        )

    except Exception as e:
        await update.message.reply_text(
            "Error occurred while registering. Please try again later."
        )


async def create_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new group."""
    if len(context.args) != 1:
        await update.message.reply_text(
            "Please provide a group name: /creategroup [name]"
        )
        return

    group_name = context.args[0]
    creator_id = update.effective_user.id

    Group = Query()
    if groups_table.search(Group.name == group_name):
        await update.message.reply_text("A group with this name already exists!")
        return

    groups_table.insert(
        {"name": group_name, "creator_id": creator_id, "members": [creator_id]}
    )

    await update.message.reply_text(f"Group '{group_name}' created successfully!")


async def join_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available groups to join."""
    groups = groups_table.all()
    if not groups:
        await update.message.reply_text("No groups available to join!")
        return

    keyboard = []
    for group in groups:
        keyboard.append(
            [InlineKeyboardButton(group["name"], callback_data=f"join_{group['name']}")]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Select a group to join:", reply_markup=reply_markup
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("join_"):
        group_name = query.data[5:]
        user_id = query.from_user.id

        Group = Query()
        group = groups_table.get(Group.name == group_name)

        if user_id in group["members"]:
            await query.edit_message_text(f"You're already a member of {group_name}!")
            return

        group["members"].append(user_id)
        groups_table.update(group, Group.name == group_name)
        await query.edit_message_text(f"Successfully joined {group_name}!")


async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's Codewars statistics."""
    user_id = update.effective_user.id
    User = Query()
    user = users_table.get(User.telegram_id == user_id)

    if not user:
        await update.message.reply_text(
            "Please register first using /register [codewars_username]"
        )
        return

    try:
        response = requests.get(f"{CODEWARS_API_BASE}{user['codewars_username']}")
        if response.status_code == 200:
            data = response.json()
            stats = (
                f"📊 Your Codewars Statistics:\n\n"
                f"Username: {data['username']}\n"
                f"Rank: {data['ranks']['overall']['name']}\n"
                f"Honor: {data['honor']}\n"
                f"Total Completed Kata: {data['codeChallenges']['totalCompleted']}\n"
            )
            await update.message.reply_text(stats)
        else:
            await update.message.reply_text("Error fetching your Codewars statistics.")
    except Exception as e:
        await update.message.reply_text("Error occurred while fetching stats.")


async def group_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group statistics."""
    user_id = update.effective_user.id
    Group = Query()
    user_groups = groups_table.search(Group.members.any([user_id]))

    if not user_groups:
        await update.message.reply_text("You're not a member of any group!")
        return

    for group in user_groups:
        stats = f"📈 Statistics for group: {group['name']}\n\n"
        for member_id in group["members"]:
            User = Query()
            user = users_table.get(User.telegram_id == member_id)
            if user:
                try:
                    response = requests.get(
                        f"{CODEWARS_API_BASE}{user['codewars_username']}"
                    )
                    if response.status_code == 200:
                        data = response.json()
                        stats += (
                            f"User: {data['username']}\n"
                            f"Completed Kata: {data['codeChallenges']['totalCompleted']}\n"
                            f"Rank: {data['ranks']['overall']['name']}\n\n"
                        )
                except:
                    stats += f"Error fetching stats for {user['codewars_username']}\n\n"

        await update.message.reply_text(stats)


def main():
    """Start the bot."""
    # Load environment variables from .env file
    load_dotenv()

    # Get the token from environment variable
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file!")
        print("Please create .env file with your bot token.")
        return

    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("creategroup", create_group))
    application.add_handler(CommandHandler("joingroup", join_group))
    application.add_handler(CommandHandler("mystats", my_stats))
    application.add_handler(CommandHandler("groupstats", group_stats))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
