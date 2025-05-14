import io
import logging
import os
from matplotlib import pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import requests
from tinydb import TinyDB, Query
import json
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logging
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Initialize TinyDB
db = TinyDB("db.json")
users_table = db.table("users")
groups_table = db.table("groups")

# Codewars API
CODEWARS_API_BASE = "https://www.codewars.com/api/v1/users/"


async def reply_to_message(message, text=None, photo=None):
    """Helper function to reply to messages, handling both regular groups and forum topics."""
    try:
        kwargs = {
            "message_thread_id": (
                message.message_thread_id if message.is_topic_message else None
            ),
            "chat_id": message.chat_id,
            "reply_to_message_id": message.message_id,
        }

        if text:
            logger.debug(f"Sending text message: {text[:50]}...")
            await message.get_bot().send_message(text=text, **kwargs)
            logger.debug("Text message sent successfully")

        if photo:
            logger.debug("Attempting to send photo...")
            try:
                photo.seek(0)  # Ensure we're at the start of the buffer
                await message.get_bot().send_photo(photo=photo, **kwargs)
                logger.debug("Photo sent successfully")
            except Exception as photo_error:
                logger.error(f"Error sending photo: {photo_error}", exc_info=True)
                raise
    except Exception as e:
        logger.error(f"Error in reply_to_message: {e}", exc_info=True)
        raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message when the command /start is issued."""
    await reply_to_message(
        update.message,
        text="Welcome to the Codewars Tracker Bot! 🎯\n\n"
        "Available commands:\n"
        "/register [codewars_username] - Register your Codewars account\n"
        "/joingroup - See available groups to join\n"
        "/mystats - See your Codewars statistics\n"
        "/groupstats - See your group's statistics",
    )


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register a user with their Codewars username."""
    if len(context.args) != 1:
        await reply_to_message(
            update.message,
            text="Please provide your Codewars username: /register [username]",
        )
        return

    codewars_username = context.args[0]
    telegram_id = update.effective_user.id

    # Verify if the Codewars username exists
    try:
        response = requests.get(f"{CODEWARS_API_BASE}{codewars_username}")
        if response.status_code != 200:
            await reply_to_message(
                update.message,
                text="Invalid Codewars username. Please check and try again.",
            )
            return

        user_data = response.json()
        current_completed = user_data["codeChallenges"]["totalCompleted"]
        User = Query()

        # Get existing user data if any
        existing_user = users_table.get(User.telegram_id == telegram_id)
        history = []
        if existing_user and "history" in existing_user:
            history = existing_user["history"]

        # Add current stats to history
        from datetime import datetime

        current_date = datetime.now().strftime("%Y-%m-%d")
        history.append(
            {
                "date": current_date,
                "completed_katas": current_completed,
                "honor": user_data["honor"],
                "rank": user_data["ranks"]["overall"]["name"],
            }
        )

        users_table.upsert(
            {
                "telegram_id": telegram_id,
                "codewars_username": codewars_username,
                "completed_katas": current_completed,
                "history": history,
            },
            User.telegram_id == telegram_id,
        )

        await reply_to_message(
            update.message,
            text=f"Successfully registered with Codewars username: {codewars_username}",
        )

    except Exception as e:
        await update.message.reply_text(
            "Error occurred while registering. Please try again later."
        )


async def create_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new group."""
    if len(context.args) != 1:
        await reply_to_message(
            update.message, text="Please provide a group name: /creategroup [name]"
        )
        return

    group_name = context.args[0]
    creator_id = update.effective_user.id

    Group = Query()
    if groups_table.search(Group.name == group_name):
        await reply_to_message(
            update.message, text="A group with this name already exists!"
        )
        return

    groups_table.insert(
        {"name": group_name, "creator_id": creator_id, "members": [creator_id]}
    )

    await reply_to_message(
        update.message, text=f"Group '{group_name}' created successfully!"
    )


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
    """Show user's Codewars statistics with historical progress."""
    logger.debug("Starting my_stats command handling")

    try:
        user_id = update.effective_user.id
        User = Query()
        user = users_table.get(User.telegram_id == user_id)

        if not user:
            await reply_to_message(
                update.message,
                text="Please register first using /register [codewars_username]",
            )
            return

        # Fetch current Codewars data and completed challenges
        logger.debug(f"Fetching Codewars data for {user['codewars_username']}")
        # Get user profile data
        profile_response = requests.get(
            f"{CODEWARS_API_BASE}{user['codewars_username']}"
        )

        if profile_response.status_code != 200:
            logger.error(
                f"Failed to fetch Codewars data: {profile_response.status_code}"
            )
            await reply_to_message(
                update.message,
                text="Failed to fetch Codewars data. Please try again later.",
            )
            return

        data = profile_response.json()

        # Get completed challenges data
        logger.debug("Fetching completed challenges")
        completed_challenges = []
        page = 0

        while True:
            challenges_response = requests.get(
                f"{CODEWARS_API_BASE}{user['codewars_username']}/code-challenges/completed?page={page}"
            )
            if challenges_response.status_code != 200:
                break

            challenges_data = challenges_response.json()
            if not challenges_data["data"]:
                break

            completed_challenges.extend(challenges_data["data"])
            page += 1

            # Limit to last 100 challenges for performance
            if len(completed_challenges) >= 100:
                completed_challenges = completed_challenges[:100]
                break

        # Sort challenges by completion time
        completed_challenges.sort(key=lambda x: x["completedAt"])

        # Create history from completed challenges
        history = []
        from datetime import datetime

        for challenge in completed_challenges:
            completed_date = datetime.fromisoformat(
                challenge["completedAt"].replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")
            # Check if we already have an entry for this date
            date_entry = next(
                (entry for entry in history if entry["date"] == completed_date), None
            )
            if date_entry:
                date_entry["completed_katas"] += 1
            else:
                # For each kata, rough estimate of honor gained (typical kata gives 2-8 honor)
                kata_honor = challenge.get("honor", 4)  # default to 4 if not provided
                history.append(
                    {
                        "date": completed_date,
                        "completed_katas": 1,
                        "honor": kata_honor,
                        "rank": data["ranks"]["overall"]["name"],
                    }
                )

        # Prepare initial stats message
        current_stats = (
            f"📊 Your Codewars Statistics:\n\n"
            f"Username: {data['username']}\n"
            f"Rank: {data['ranks']['overall']['name']}\n"
            f"Honor: {data['honor']}\n"
            f"Total Completed Kata: {data['codeChallenges']['totalCompleted']}\n\n"
            f"Recent Completed Challenges:\n"
        )

        # Add most recent 5 challenges
        for challenge in completed_challenges[-5:]:
            completed_at = datetime.fromisoformat(
                challenge["completedAt"].replace("Z", "+00:00")
            ).strftime("%Y-%m-%d %H:%M")
            current_stats += f"• {challenge['name']} ({completed_at})\n"

        # Save stats for later - we'll combine with progress stats

        if not history:
            logger.debug("No history data available")
            return

        # Generate visualization
        logger.debug("Starting visualization generation")

        try:
            # Prepare plotting data
            dates = [entry["date"] for entry in history]
            katas = [entry["completed_katas"] for entry in history]
            honor = [entry["honor"] for entry in history]

            # Create plot with daily and cumulative stats
            plt.style.use("dark_background")
            fig, ax1 = plt.subplots(figsize=(15, 6))

            # Plot daily completed katas
            daily_completions = [entry["completed_katas"] for entry in history]
            cumulative_katas = []
            total = 0
            for count in daily_completions:
                total += count
                cumulative_katas.append(total)

            # Plot daily completions as bars
            ax1.bar(dates, daily_completions, color="cyan", alpha=0.5)
            ax1.set_title("Daily Completed Katas")
            ax1.set_xlabel("Date")
            ax1.set_ylabel("Katas Completed")
            ax1.tick_params(axis="x", rotation=45)

            # Add cumulative line
            ax1_twin = ax1.twinx()
            ax1_twin.plot(dates, cumulative_katas, color="yellow", linewidth=2)
            ax1_twin.set_ylabel("Total Katas", color="yellow")
            ax1_twin.tick_params(axis="y", colors="yellow")

            # Plot honor points
            cumulative_honor = []
            total_honor = 0
            for h in honor:
                total_honor += h
                cumulative_honor.append(total_honor)

            plt.suptitle(f'Codewars Progress for {data["username"]}')
            plt.tight_layout()

            # Save and send plot
            logger.debug("Saving plot to buffer")
            buf = io.BytesIO()
            plt.savefig(buf, format="png", bbox_inches="tight", dpi=300)
            buf.seek(0)

            # Calculate activity stats
            total_days = len(dates)
            active_days = len([k for k in daily_completions if k > 0])
            avg_per_active_day = (
                sum(daily_completions) / active_days if active_days > 0 else 0
            )
            max_day_katas = max(daily_completions)
            max_day_date = dates[daily_completions.index(max_day_katas)]

            # Combine all stats into one message
            complete_stats = (
                current_stats
                + "\n"
                + (
                    f"📈 Activity Statistics:\n\n"
                    f"Total Days Tracked: {total_days}\n"
                    f"Active Days: {active_days}\n"
                    f"Completion Rate: {(active_days/total_days*100):.1f}%\n"
                    f"Average Katas per Active Day: {avg_per_active_day:.1f}\n"
                    f"Most Productive Day: {max_day_date} ({max_day_katas} katas)\n\n"
                    f"Progress Summary:\n"
                    f"├ Total Katas Completed: {cumulative_katas[-1]}\n"
                    f"└ Total Honor Earned: {cumulative_honor[-1]} (Current: {data['honor']})"
                )
            )

            # Send combined stats and visualization
            await reply_to_message(update.message, text=complete_stats)
            logger.debug("Sending visualization")
            await reply_to_message(update.message, photo=buf)

        except Exception as viz_error:
            logger.error(f"Visualization error: {viz_error}", exc_info=True)
            await reply_to_message(
                update.message,
                text="❌ Failed to generate visualization. Please try again later.",
            )
        finally:
            plt.close("all")

    except Exception as e:
        logger.error(f"Error in my_stats: {e}", exc_info=True)
        await reply_to_message(
            update.message, text="❌ An error occurred. Please try again later."
        )


async def group_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group statistics with charts."""
    user_id = update.effective_user.id
    Group = Query()
    user_groups = groups_table.search(Group.members.any([user_id]))

    if not user_groups:
        await update.message.reply_text("You're not a member of any group!")
        return

    for group in user_groups:
        # Collect data for visualization
        usernames = []
        completed_katas = []
        honor_points = []

        # Get stats for each member
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
                        usernames.append(data["username"])
                        completed_katas.append(data["codeChallenges"]["totalCompleted"])
                        honor_points.append(data["honor"])
                except:
                    continue

        if not usernames:
            await update.message.reply_text(
                f"No data available for group: {group['name']}"
            )
            continue

        # Create the visualization
        plt.figure(figsize=(12, 6))
        plt.style.use("dark_background")  # Using dark theme for better visibility

        # Create subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # Plot completed katas
        bars1 = ax1.bar(usernames, completed_katas)
        ax1.set_title("Completed Katas")
        ax1.set_xlabel("Users")
        ax1.set_ylabel("Number of Katas")
        ax1.tick_params(axis="x", rotation=45)
        # Add value labels on the bars
        for bar in bars1:
            height = bar.get_height()
            ax1.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{int(height)}",
                ha="center",
                va="bottom",
            )

        # Plot honor points
        bars2 = ax2.bar(usernames, honor_points)
        ax2.set_title("Honor Points")
        ax2.set_xlabel("Users")
        ax2.set_ylabel("Honor")
        ax2.tick_params(axis="x", rotation=45)
        # Add value labels on the bars
        for bar in bars2:
            height = bar.get_height()
            ax2.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{int(height)}",
                ha="center",
                va="bottom",
            )

        plt.suptitle(f'Codewars Statistics for Group: {group["name"]}')
        plt.tight_layout()  # Adjust layout to prevent overlap

        # Save plot to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=300)
        buf.seek(0)
        plt.close()  # Close the figure to free memory

        # Send stats message
        stats = f"📊 Statistics for group: {group['name']}\n"
        for username, katas, honor in zip(usernames, completed_katas, honor_points):
            stats += f"\n{username}: {completed_katas}\n"

        # Send text stats and image
        await reply_to_message(update.message, text=stats)
        await reply_to_message(update.message, photo=buf)


async def handle_group_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when bot is added to a group or group is updated."""
    if update.message and update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:  # Bot was added to a group
                group_name = update.message.chat.title
                group_id = update.message.chat.id
                chat_type = update.message.chat.type

                Group = Query()
                # Check if group already exists
                if not groups_table.search(Group.group_id == group_id):
                    groups_table.insert(
                        {
                            "name": group_name,
                            "group_id": group_id,
                            "chat_type": chat_type,
                            "members": [],
                            "creator_id": update.message.from_user.id,
                            "is_forum": (
                                update.message.chat.is_forum
                                if hasattr(update.message.chat, "is_forum")
                                else False
                            ),
                        }
                    )

                    await reply_to_message(
                        f"Thanks for adding me to {group_name}! 🎯\n\n"
                        "Group members can use these commands:\n"
                        "/register [codewars_username] - Register your Codewars account\n"
                        "/mystats - See your Codewars statistics\n"
                        "/groupstats - See this group's statistics"
                    )


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
    # Add handler for group updates (when bot is added to group)
    application.add_handler(CommandHandler("help", start))  # Add help command
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_group_update)
    )

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
