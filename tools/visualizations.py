import plotext as plt
from datetime import datetime
import io


def create_progress_plot(history, username):
    """Create progress visualization."""
    plt.style.use("dark_background")
    fig, ax1 = plt.subplots(figsize=(15, 6))

    dates = [entry["date"] for entry in history]
    daily_completions = [entry["completed_katas"] for entry in history]

    # Calculate cumulative stats
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

    plt.suptitle(f"Codewars Progress for {username}")
    plt.tight_layout()

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=300)
    buf.seek(0)
    plt.close()

    return buf


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
    plt.style.use("dark_background")

    if label1 and label2:
        # Single plot with two side-by-side bar sets
        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(len(usernames))
        width = 0.35

        rects1 = ax.bar(x - width / 2, data1, width, label=label1)
        rects2 = ax.bar(x + width / 2, data2, width, label=label2)

        # Add value labels
        def autolabel(rects):
            for rect in rects:
                height = rect.get_height()
                ax.annotate(
                    f"{int(height)}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                )

        autolabel(rects1)
        autolabel(rects2)

        ax.set_title(title if title else "Group Comparison")
        ax.set_xlabel(xlabel if xlabel else "Users")
        ax.set_ylabel(ylabel if ylabel else "Count")
        ax.set_xticks(x)
        ax.set_xticklabels(usernames, rotation=45, ha="right")
        ax.legend()
    else:
        # Two separate plots (default behavior for katas and honor)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # Plot completed katas
        bars1 = ax1.bar(usernames, data1)
        ax1.set_title("Completed Katas")
        ax1.set_xlabel("Users")
        ax1.set_ylabel("Number of Katas")
        ax1.tick_params(axis="x", rotation=45)

        # Add value labels
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
        bars2 = ax2.bar(usernames, data2)
        ax2.set_title("Honor Points")
        ax2.set_xlabel("Users")
        ax2.set_ylabel("Honor")
        ax2.tick_params(axis="x", rotation=45)

        # Add value labels
        for bar in bars2:
            height = bar.get_height()
            ax2.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{int(height)}",
                ha="center",
                va="bottom",
            )

    plt.tight_layout()

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=300)
    buf.seek(0)
    plt.close()

    return buf


def create_weekly_activity_plot(member_stats, dates, group_name):
    """Create weekly activity visualization."""
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(15, 8))

    bar_width = 0.8 / len(member_stats)
    colors = plt.cm.Set3(np.linspace(0, 1, len(member_stats)))

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

        # Add value labels
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

    ax.set_ylabel("Completed Katas")
    ax.set_title(f"Weekly Kata Completions - {group_name}")
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

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=300)
    buf.seek(0)
    plt.close()

    return buf
