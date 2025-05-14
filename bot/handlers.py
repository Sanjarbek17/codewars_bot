"""Handler functions for bot commands."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from handle_bot.codewars_bot.config import logger
from ..database.database import (
    get_user,
    update_user,
    get_user_groups,
    create_group as db_create_group,
    add_user_to_group,
    get_group,
)
from ..tools.api import get_user_profile, get_completed_challenges
from ..tools.visualizations import (
    create_progress_plot,
    create_group_comparison_plot,
    create_weekly_activity_plot,
)


async def reply_to_message(message, text=None, photo=None, reply_markup=None):
    """Helper function to reply to messages."""
    try:
        kwargs = {
            "message_thread_id": (
                message.message_thread_id if message.is_topic_message else None
            ),
            "chat_id": message.chat_id,
            "reply_to_message_id": message.message_id,
        }

        if reply_markup:
            kwargs["reply_markup"] = reply_markup

        if text:
            await message.get_bot().send_message(text=text, **kwargs)

        if photo:
            await message.get_bot().send_photo(photo=photo, **kwargs)

    except Exception as e:
        logger.error(f"Error in reply_to_message: {e}", exc_info=True)
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

    # Get user data from Codewars
    user_data = get_user_profile(codewars_username)
    if not user_data:
        await reply_to_message(
            update.message,
            text="Invalid Codewars username. Please check and try again.",
        )
        return

    # Update user data
    current_completed = user_data["codeChallenges"]["totalCompleted"]
    history = []

    # Get existing user data if any
    existing_user = get_user(telegram_id)
    if existing_user and "history" in existing_user:
        history = existing_user["history"]

    # Add current stats to history
    history.append(
        {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "completed_katas": current_completed,
            "honor": user_data["honor"],
            "rank": user_data["ranks"]["overall"]["name"],
        }
    )

    # Update database
    update_user(
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


async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's Codewars statistics with historical progress."""
    logger.debug("Starting my_stats command handling")

    try:
        user_id = update.effective_user.id
        user = get_user(user_id)

        if not user:
            await reply_to_message(
                update.message,
                text="Please register first using /register [codewars_username]",
            )
            return

        # Fetch current Codewars data
        logger.debug(f"Fetching Codewars data for {user['codewars_username']}")
        data = get_user_profile(user["codewars_username"])

        if not data:
            await reply_to_message(
                update.message,
                text="Failed to fetch Codewars data. Please try again later.",
            )
            return

        # Get completed challenges
        completed_challenges = get_completed_challenges(user["codewars_username"])
        completed_challenges.sort(key=lambda x: x["completedAt"])

        # Create history from completed challenges
        history = []
        for challenge in completed_challenges:
            completed_date = datetime.fromisoformat(
                challenge["completedAt"].replace("Z", "+00:00")
            ).strftime("%Y-%m-%d")

            date_entry = next(
                (entry for entry in history if entry["date"] == completed_date), None
            )
            if date_entry:
                date_entry["completed_katas"] += 1
            else:
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

        if not history:
            await reply_to_message(update.message, text=current_stats)
            return

        # Generate visualization
        buf = create_progress_plot(history, data["username"])

        # Calculate activity stats
        dates = [entry["date"] for entry in history]
        daily_completions = [entry["completed_katas"] for entry in history]
        total_days = len(dates)
        active_days = len([k for k in daily_completions if k > 0])
        avg_per_active_day = (
            sum(daily_completions) / active_days if active_days > 0 else 0
        )
        max_day_katas = max(daily_completions)
        max_day_date = dates[daily_completions.index(max_day_katas)]

        # Calculate total katas and honor
        total_katas = sum(daily_completions)
        total_honor = sum(entry["honor"] for entry in history)

        # Combine all stats into one message
        complete_stats = (
            current_stats + "\n" + f"📈 Activity Statistics:\n\n"
            f"Total Days Tracked: {total_days}\n"
            f"Active Days: {active_days}\n"
            f"Completion Rate: {(active_days/total_days*100):.1f}%\n"
            f"Average Katas per Active Day: {avg_per_active_day:.1f}\n"
            f"Most Productive Day: {max_day_date} ({max_day_katas} katas)\n\n"
            f"Progress Summary:\n"
            f"├ Total Katas Completed: {total_katas}\n"
            f"└ Total Honor Earned: {total_honor} (Current: {data['honor']})"
        )

        # Send combined stats and visualization
        await reply_to_message(update.message, text=complete_stats)
        await reply_to_message(update.message, photo=buf)

    except Exception as e:
        logger.error(f"Error in my_stats: {e}", exc_info=True)
        await reply_to_message(
            update.message, text="❌ An error occurred. Please try again later."
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

    if db_create_group(group_name, creator_id):
        await reply_to_message(
            update.message, text=f"Group '{group_name}' created successfully!"
        )
    else:
        await reply_to_message(
            update.message, text="A group with this name already exists!"
        )


async def join_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available groups to join."""
    groups = get_user_groups(update.effective_user.id)
    if not groups:
        await reply_to_message(update.message, text="No groups available to join!")
        return

    keyboard = []
    for group in groups:
        keyboard.append(
            [InlineKeyboardButton(group["name"], callback_data=f"join_{group['name']}")]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await reply_to_message(
        update.message, text="Select a group to join:", reply_markup=reply_markup
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("join_"):
        group_name = query.data[5:]
        user_id = query.from_user.id

        group = get_group(group_name)
        if not group:
            await query.edit_message_text("Group not found!")
            return

        if user_id in group["members"]:
            await query.edit_message_text(f"You're already a member of {group_name}!")
            return

        if add_user_to_group(group_name, user_id):
            await query.edit_message_text(f"Successfully joined {group_name}!")
        else:
            await query.edit_message_text("Failed to join group. Please try again.")


async def handle_group_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when bot is added to a group."""
    if update.message and update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:  # Bot was added to a group
                group_name = update.message.chat.title
                group_id = update.message.chat.id
                chat_type = update.message.chat.type

                if db_create_group(group_name, update.message.from_user.id):
                    welcome_text = (
                        f"Thanks for adding me to {group_name}! 🎯\n\n"
                        "Group members can use these commands:\n"
                        "/register [codewars_username] - Register your Codewars account\n"
                        "/mystats - See your Codewars statistics\n"
                        "/groupstats - See this group's statistics"
                    )
                    await reply_to_message(update.message, text=welcome_text)


async def group_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group statistics with charts."""
    user_id = update.effective_user.id
    user_groups = get_user_groups(user_id)

    if not user_groups:
        await reply_to_message(update.message, text="You're not a member of any group!")
        return

    for group in user_groups:
        # Collect data for visualization
        usernames = []
        completed_katas = []
        honor_points = []

        # Get stats for each member
        for member_id in group["members"]:
            user = get_user(member_id)
            if user:
                try:
                    data = get_user_profile(user["codewars_username"])
                    if data:
                        usernames.append(data["username"])
                        completed_katas.append(data["codeChallenges"]["totalCompleted"])
                        honor_points.append(data["honor"])
                except Exception as e:
                    logger.error(f"Error fetching stats for user: {e}")
                    continue

        if not usernames:
            await reply_to_message(
                update.message, text=f"No data available for group: {group['name']}"
            )
            continue

        # Create visualization
        buf = create_group_comparison_plot(usernames, completed_katas, honor_points)

        # Send stats message
        stats = f"📊 Statistics for group: {group['name']}\n"
        for username, katas, honor in zip(usernames, completed_katas, honor_points):
            stats += f"\n{username}: {katas} katas, {honor} honor"

        # Send text stats and image
        await reply_to_message(update.message, text=stats)
        await reply_to_message(update.message, photo=buf)


async def daily_group_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's and yesterday's kata completion statistics for group members."""
    user_id = update.effective_user.id
    user_groups = get_user_groups(user_id)

    if not user_groups:
        await reply_to_message(update.message, text="You're not a member of any group!")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    for group in user_groups:
        # Initialize data collection
        member_stats = []

        # Get stats for each member
        for member_id in group["members"]:
            user = get_user(member_id)
            if user:
                try:
                    data = get_user_profile(user["codewars_username"])
                    if data:
                        # Get completed challenges for today and yesterday
                        challenges = get_completed_challenges(user["codewars_username"])

                        today_completed = sum(
                            1 for c in challenges if c["completedAt"].startswith(today)
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

        # Prepare visualization data
        usernames = [stat["username"] for stat in member_stats]
        today_katas = [stat["today"] for stat in member_stats]
        yesterday_katas = [stat["yesterday"] for stat in member_stats]

        # Create visualization
        buf = create_group_comparison_plot(
            usernames,
            today_katas,
            yesterday_katas,
            title=f"Daily Kata Completions - {group['name']}",
            xlabel="Members",
            ylabel="Completed Katas",
            label1="Today",
            label2="Yesterday",
        )

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
    user_groups = get_user_groups(user_id)

    if not user_groups:
        await reply_to_message(update.message, text="You're not a member of any group!")
        return

    # Get dates for the last 7 days
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    dates.reverse()  # Show oldest to newest

    for group in user_groups:
        # Initialize data collection
        member_stats = []

        # Get stats for each member
        for member_id in group["members"]:
            user = get_user(member_id)
            if user:
                try:
                    data = get_user_profile(user["codewars_username"])
                    if data:
                        # Get completed challenges and count by day
                        challenges = get_completed_challenges(user["codewars_username"])

                        # Count completions for each day
                        daily_counts = {date: 0 for date in dates}
                        for challenge in challenges:
                            completed_date = challenge["completedAt"][:10]  # YYYY-MM-DD
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
        buf = create_weekly_activity_plot(member_stats, dates, group["name"])

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
    await reply_to_message(update.message, text=help_text)
