import io
import logging
import os
import numpy as np  # Add numpy import
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
            text=(
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
            ),
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

        # Prepare success message with next steps
        success_message = (
            f"✅ Successfully registered with Codewars username: {codewars_username}\n\n"
            "What's next?\n"
            "• Use /mystats to see your progress\n"
            "• Use /joingroup to join a group and compare stats with others\n"
            "• Complete more katas on codewars.com to see your progress!\n\n"
            "Your stats will be automatically tracked and updated."
        )
        await reply_to_message(update.message, text=success_message)

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
            stats += f"\n{username}: {katas}"

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


async def daily_group_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's and yesterday's kata completion statistics for group members."""
    user_id = update.effective_user.id
    Group = Query()
    user_groups = groups_table.search(Group.members.any([user_id]))

    if not user_groups:
        await reply_to_message(update.message, text="You're not a member of any group!")
        return

    from datetime import datetime, timedelta

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    for group in user_groups:
        # Initialize data collection
        member_stats = []

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

                        # Get completed challenges for today and yesterday
                        challenges_response = requests.get(
                            f"{CODEWARS_API_BASE}{user['codewars_username']}/code-challenges/completed"
                        )

                        if challenges_response.status_code == 200:
                            challenges = challenges_response.json()["data"]
                            today_completed = sum(
                                1
                                for c in challenges
                                if c["completedAt"].startswith(today)
                            )
                            yesterday_completed = sum(
                                1
                                for c in challenges
                                if c["completedAt"].startswith(yesterday)
                            )

                            member_stats.append(
                                {
                                    "username": data["username"],
                                    "today": today_completed,
                                    "yesterday": yesterday_completed,
                                    "rank": data["ranks"]["overall"]["name"],
                                    "honor": data["honor"],
                                }
                            )
                except Exception as e:
                    logger.error(f"Error fetching stats for user: {e}")
                    continue

        if not member_stats:
            await reply_to_message(
                update.message, text=f"No data available for group: {group['name']}"
            )
            continue

        # Sort members by today's completions
        member_stats.sort(key=lambda x: (-x["today"], -x["yesterday"], -x["honor"]))

        # Create visualization
        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=(12, 6))

        # Prepare data for plotting
        usernames = [stat["username"] for stat in member_stats]
        today_katas = [stat["today"] for stat in member_stats]
        yesterday_katas = [stat["yesterday"] for stat in member_stats]

        # Set the positions of the bars
        x = range(len(usernames))
        width = 0.35

        # Create bars
        today_bars = ax.bar(
            [i - width / 2 for i in x],
            today_katas,
            width,
            label="Today",
            color="cyan",
            alpha=0.8,
        )
        yesterday_bars = ax.bar(
            [i + width / 2 for i in x],
            yesterday_katas,
            width,
            label="Yesterday",
            color="yellow",
            alpha=0.5,
        )

        # Customize the plot
        ax.set_ylabel("Completed Katas")
        ax.set_title(f"Daily Kata Completions - {group['name']}")
        ax.set_xticks(x)
        ax.set_xticklabels(usernames, rotation=45, ha="right")
        ax.legend()

        # Add value labels on bars
        def autolabel(bars):
            for bar in bars:
                height = bar.get_height()
                if height > 0:  # Only show label if there are completed katas
                    ax.annotate(
                        f"{int(height)}",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha="center",
                        va="bottom",
                    )

        autolabel(today_bars)
        autolabel(yesterday_bars)

        plt.tight_layout()

        # Save plot to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=300)
        buf.seek(0)
        plt.close()

        # Prepare stats message
        stats_msg = f"📊 Daily Statistics for {group['name']}\n\n"
        stats_msg += f"Date: {today}\n\n"

        for stat in member_stats:
            stats_msg += (
                f"👤 {stat['username']} ({stat['rank']})\n"
                f"├ Today: {stat['today']} katas\n"
                f"├ Yesterday: {stat['yesterday']} katas\n"
                f"└ Honor: {stat['honor']}\n\n"
            )

        # Add group summary
        total_today = sum(stat["today"] for stat in member_stats)
        total_yesterday = sum(stat["yesterday"] for stat in member_stats)
        change = total_today - total_yesterday
        change_symbol = "📈" if change > 0 else "📉" if change < 0 else "➖"

        stats_msg += (
            f"📈 Group Summary:\n"
            f"├ Total Today: {total_today} katas\n"
            f"├ Total Yesterday: {total_yesterday} katas\n"
            f"└ Day-over-day change: {change_symbol} {abs(change)} katas\n"
        )

        # Send stats and visualization
        await reply_to_message(update.message, text=stats_msg)
        await reply_to_message(update.message, photo=buf)


async def weekly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show weekly kata completion statistics for group members."""
    user_id = update.effective_user.id
    Group = Query()
    user_groups = groups_table.search(Group.members.any([user_id]))

    if not user_groups:
        await reply_to_message(update.message, text="You're not a member of any group!")
        return

    from datetime import datetime, timedelta

    # Get dates for the last 7 days
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    dates.reverse()  # So we show oldest to newest

    for group in user_groups:
        # Initialize data collection
        member_stats = []

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

                        # Get completed challenges
                        challenges_response = requests.get(
                            f"{CODEWARS_API_BASE}{user['codewars_username']}/code-challenges/completed"
                        )

                        if challenges_response.status_code == 200:
                            challenges = challenges_response.json()["data"]

                            # Count completions for each day
                            daily_counts = {date: 0 for date in dates}
                            for challenge in challenges:
                                completed_date = challenge["completedAt"][
                                    :10
                                ]  # YYYY-MM-DD
                                if completed_date in daily_counts:
                                    daily_counts[completed_date] += 1

                            member_stats.append(
                                {
                                    "username": data["username"],
                                    "rank": data["ranks"]["overall"]["name"],
                                    "honor": data["honor"],
                                    "daily_counts": daily_counts,
                                    "total_week": sum(daily_counts.values()),
                                }
                            )
                except Exception as e:
                    logger.error(f"Error fetching stats for user: {e}")
                    continue

        if not member_stats:
            await reply_to_message(
                update.message, text=f"No data available for group: {group['name']}"
            )
            continue

        # Sort members by total weekly completions
        member_stats.sort(key=lambda x: (-x["total_week"], -x["honor"]))

        # Create visualization
        plt.style.use("dark_background")
        fig, ax = plt.subplots(figsize=(15, 8))

        # Set up the plot
        bar_width = 0.8 / len(member_stats)
        colors = plt.cm.Set3(np.linspace(0, 1, len(member_stats)))

        # Plot bars for each member
        for idx, member in enumerate(member_stats):
            daily_values = [member["daily_counts"][date] for date in dates]
            x = np.arange(len(dates))
            bars = ax.bar(
                x + idx * bar_width,
                daily_values,
                bar_width,
                label=member["username"],
                color=colors[idx],
                alpha=0.8,
            )

            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.annotate(
                        f"{int(height)}",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                    )

        # Customize the plot
        ax.set_ylabel("Completed Katas")
        ax.set_title(f"Weekly Kata Completions - {group['name']}")
        ax.set_xticks(
            np.arange(len(dates)) + (bar_width * len(member_stats)) / 2 - bar_width / 2
        )
        ax.set_xticklabels(
            [datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") for d in dates],
            rotation=45,
            ha="right",
        )
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.tight_layout()

        # Save plot to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=300)
        buf.seek(0)
        plt.close()

        # Prepare stats message
        stats_msg = f"📊 Weekly Statistics for {group['name']}\n\n"
        stats_msg += f"Period: {dates[0]} to {dates[-1]}\n\n"

        for member in member_stats:
            daily_counts = member["daily_counts"]
            stats_msg += (
                f"👤 {member['username']} ({member['rank']})\n"
                f"├ Total this week: {member['total_week']} katas\n"
                f"├ Daily breakdown:\n"
            )
            for date in dates:
                count = daily_counts[date]
                day_name = datetime.strptime(date, "%Y-%m-%d").strftime("%a %b %d")
                bar = "█" * count if count > 0 else "░"
                stats_msg += f"│  {day_name}: {bar} {count}\n"
            stats_msg += f"└ Honor: {member['honor']}\n\n"

        # Add group summary
        total_week = sum(member["total_week"] for member in member_stats)
        daily_totals = {
            date: sum(member["daily_counts"][date] for member in member_stats)
            for date in dates
        }
        max_day = max(daily_totals.items(), key=lambda x: x[1])
        max_day_name = datetime.strptime(max_day[0], "%Y-%m-%d").strftime("%a %b %d")

        stats_msg += (
            f"📈 Group Summary:\n"
            f"├ Total Katas This Week: {total_week}\n"
            f"├ Average per Day: {total_week/7:.1f}\n"
            f"└ Most Active Day: {max_day_name} ({max_day[1]} katas)\n"
        )

        # Send stats and visualization
        await reply_to_message(update.message, text=stats_msg)
        await reply_to_message(update.message, photo=buf)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of commands."""
    help_text = """
🤖 Available Commands:

/register [username] - Register your Codewars account
/stats - View your Codewars statistics
/group - View group leaderboard
/daily - View today's and yesterday's kata completions
/weekly - View last 7 days of kata completions
/join [group_name] - Join or create a group
/groups - List all groups
/help - Show this help message

Need help? Message @YourAdminUsername
"""
    await update.message.reply_text(help_text)


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
    application.add_handler(CommandHandler("daily", daily_group_stats))
    application.add_handler(CommandHandler("weekly", weekly_stats))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    # Add handler for group updates (when bot is added to group)
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
