import argparse
import csv
from datetime import date

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


# =========================
# COLORS
# =========================

ETSU_BLUE = "#00053E"
ETSU_GOLD = "#FFC72C"
WHITE = "#FFFFFF"
LIGHT_GRAY = "#D9DDE5"
ROW_BLUE = "#07144F"
SUBTLE_BLUE = "#0B1758"


# =========================
# DATA
# =========================

def load_rankings(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# =========================
# GRAPHIC
# =========================

def make_graphic(rows, output, top_n=None):
    if top_n is not None:
        rows = rows[:top_n]

    if not rows:
        raise ValueError("No players found in rankings.csv.")

    # Make the image taller when there are many players.
    row_height = 0.0275
    header_space = 0.20
    height = header_space + (len(rows) * row_height) + 0.02
    height = max(height, 10.8)

    fig = plt.figure(figsize=(19.2, height), dpi=100)
    fig.patch.set_facecolor(ETSU_BLUE)

    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(ETSU_BLUE)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # =========================
    # HEADER
    # =========================

    ax.text(
        0.055,
        0.97,
        "FULKRANK",
        fontsize=36,
        fontweight="bold",
        color=ETSU_GOLD,
        va="top",
    )

    ax.text(
        0.055,
        0.925,
        "Competitive Player Rankings",
        fontsize=18,
        color=WHITE,
        va="top",
    )

    ax.text(
        0.945,
        0.97,
        date.today().strftime("%B %d, %Y"),
        fontsize=14,
        color=WHITE,
        ha="right",
        va="top",
    )

    ax.text(
        0.945,
        0.935,
        f"{len(rows):,} players",
        fontsize=13,
        color=LIGHT_GRAY,
        ha="right",
        va="top",
    )

    # =========================
    # TABLE HEADER
    # =========================

    header_y = 0.875

    ax.text(
        0.065,
        header_y,
        "RANK",
        fontsize=11,
        fontweight="bold",
        color=ETSU_GOLD,
    )

    ax.text(
        0.135,
        header_y,
        "PLAYER",
        fontsize=11,
        fontweight="bold",
        color=ETSU_GOLD,
    )

    ax.text(
        0.690,
        header_y,
        "RATING",
        fontsize=11,
        fontweight="bold",
        color=ETSU_GOLD,
        ha="right",
    )

    ax.text(
        0.785,
        header_y,
        "MATCHES",
        fontsize=11,
        fontweight="bold",
        color=ETSU_GOLD,
        ha="right",
    )

    ax.text(
        0.865,
        header_y,
        "W",
        fontsize=11,
        fontweight="bold",
        color=ETSU_GOLD,
        ha="right",
    )

    ax.text(
        0.915,
        header_y,
        "L",
        fontsize=11,
        fontweight="bold",
        color=ETSU_GOLD,
        ha="right",
    )

    ax.plot(
        [0.055, 0.945],
        [0.855, 0.855],
        linewidth=2,
        color=ETSU_GOLD,
    )

    # =========================
    # ROW SIZING
    # =========================

    if len(rows) <= 25:
        top_y = 0.825
        actual_row_height = 0.0275

    elif len(rows) <= 100:
        top_y = 0.825
        bottom_y = 0.035
        actual_row_height = (top_y - bottom_y) / len(rows)

    else:
        top_y = 0.825
        bottom_y = 0.025
        actual_row_height = (top_y - bottom_y) / len(rows)

    # =========================
    # PLAYER ROWS
    # =========================

    for index, row in enumerate(rows):
        y = top_y - index * actual_row_height

        rank = int(row["rank"])
        player = row["player"]
        rating = float(row["rating"])
        matches = int(row["matches"])
        wins = int(row["wins"])
        losses = int(row["losses"])

        # Alternating rows.
        if index % 2 == 1:
            ax.add_patch(
                Rectangle(
                    (0.055, y - actual_row_height / 2),
                    0.89,
                    actual_row_height,
                    facecolor=ROW_BLUE,
                    alpha=0.85,
                    transform=ax.transAxes,
                    clip_on=False,
                )
            )

        # Scale text depending on number of players.
        if len(rows) <= 50:
            font_size = 12
        elif len(rows) <= 100:
            font_size = 9.5
        elif len(rows) <= 200:
            font_size = 7.5
        elif len(rows) <= 500:
            font_size = 6
        else:
            font_size = 4.5

        # Top three styling.
        if rank == 1:
            rank_color = ETSU_GOLD
            rank_size = font_size + 5
            player_weight = "bold"
        elif rank == 2:
            rank_color = WHITE
            rank_size = font_size + 3
            player_weight = "bold"
        elif rank == 3:
            rank_color = LIGHT_GRAY
            rank_size = font_size + 2
            player_weight = "bold"
        else:
            rank_color = WHITE
            rank_size = font_size
            player_weight = "normal"

        # Rank.
        ax.text(
            0.065,
            y,
            str(rank),
            fontsize=rank_size,
            fontweight="bold" if rank <= 3 else "normal",
            color=rank_color,
            va="center",
        )

        # Player name.
        ax.text(
            0.135,
            y,
            player,
            fontsize=font_size + 1 if rank <= 3 else font_size,
            fontweight=player_weight,
            color=WHITE,
            va="center",
        )

        # Rating.
        ax.text(
            0.690,
            y,
            f"{rating:.0f}",
            fontsize=font_size + 1 if rank <= 3 else font_size,
            fontweight="bold" if rank <= 3 else "normal",
            color=ETSU_GOLD,
            ha="right",
            va="center",
        )

        # Matches.
        ax.text(
            0.785,
            y,
            f"{matches:,}",
            fontsize=font_size,
            color=LIGHT_GRAY,
            ha="right",
            va="center",
        )

        # Wins.
        ax.text(
            0.865,
            y,
            f"{wins:,}",
            fontsize=font_size,
            color=WHITE,
            ha="right",
            va="center",
        )

        # Losses.
        ax.text(
            0.915,
            y,
            f"{losses:,}",
            fontsize=font_size,
            color=LIGHT_GRAY,
            ha="right",
            va="center",
        )

    # =========================
    # SAVE
    # =========================

    fig.savefig(
        output,
        dpi=100,
        facecolor=ETSU_BLUE,
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0,
    )

    plt.close(fig)


# =========================
# MAIN
# =========================

def main():
    parser = argparse.ArgumentParser(
        description="Generate a Fulkrank leaderboard graphic."
    )

    parser.add_argument(
        "--input",
        "-i",
        default="rankings.csv",
        help="Input rankings CSV.",
    )

    parser.add_argument(
        "--output",
        "-o",
        default="rankings.png",
        help="Output PNG.",
    )

    parser.add_argument(
        "--top",
        "-n",
        type=int,
        default=None,
        help="Only show the top N players. Default: all players.",
    )

    args = parser.parse_args()

    rows = load_rankings(args.input)

    if not rows:
        raise ValueError("rankings.csv contains no players.")

    make_graphic(
        rows,
        args.output,
        args.top,
    )

    shown = len(rows) if args.top is None else min(args.top, len(rows))

    print(f"Graphic written to {args.output}")
    print(f"Players shown: {shown:,}")


if __name__ == "__main__":
    main()