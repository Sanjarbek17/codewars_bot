import plotext as plt
from datetime import datetime
import io

def create_group_comparison_plot(
    usernames,
    data1,
    data2,
    title=None,
    xlabel=None,
    ylabel=None,
    label1=None,
    label2=None,
):
    """Create group comparison visualization."""
    plt.clear_figure()
    plt.theme("dark")

    if label1 and label2:
        # Single plot with side-by-side data
        plt.multiple_bar(
            [usernames, usernames], [data1, data2], labels=[label1, label2], width=0.15
        )
    else:
        # Two plots for katas and honor
        plt.subplot(121)  # First subplot
        plt.bar(usernames, data1, width=0.3)
        plt.title("Completed Katas")
        plt.xlabel("Users")
        plt.ylabel("Number of Katas")

        plt.subplot(122)  # Second subplot
        plt.bar(usernames, data2, width=0.3)
        plt.title("Honor Points")
        plt.xlabel("Users")
        plt.ylabel("Honor")

    plt.title(title if title else "Group Comparison")

    # Generate plot as string
    plot_str = plt.build()

    # Create a text buffer with the ASCII plot
    buf = io.StringIO()
    buf.write(f"```\n{plot_str}\n```")
    return buf.getvalue()


def create_weekly_activity_plot(member_stats, dates, group_name):
    """Create weekly activity visualization."""
    plt.clear_figure()
    plt.theme("dark")

    # Create a subplot for each member
    for idx, member in enumerate(member_stats):
        daily_values = [member["daily_counts"][date] for date in dates]
        plt.bar(dates, daily_values, label=member["username"])

    plt.title(f"Weekly Kata Completions - {group_name}")
    plt.xlabel("Date")
    plt.ylabel("Completed Katas")
    plt.show_legend()

    # Generate plot as string
    plot_str = plt.build()

    # Create a text buffer with the ASCII plot
    buf = io.StringIO()
    buf.write(f"```\n{plot_str}\n```")
    return buf.getvalue()
