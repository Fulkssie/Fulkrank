import argparse
import csv
from datetime import date

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


# =========================
# COLORS
# =========================

# ETSU
ETSU_BLUE = "#041E42"
ETSU_GOLD = "#FFC72C"

# UTK
UTK_ORANGE = "#FF8200"
UTK_DARK = "#58595B"
UTK_LIGHT_SMOKE = "#E5E5E5"
UTK_ROW_DARK = "#4A4B4D"
UTK_SMOKE = "#66676A"

# Shared
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
# COLOR SCHEMES
# =========================

def get_color_scheme(color_scheme):
    color_scheme = color_scheme.upper()

    if color_scheme == "ETSU":
        return {
            "primary": ETSU_GOLD,
            "background": ETSU_BLUE,
            "text": WHITE,
            "muted_text": LIGHT_GRAY,
            "row_color": ROW_BLUE,
            "subtle_color": SUBTLE_BLUE,
            "title": "TRICOT",
        }

    if color_scheme == "UTK":
        return {
            "primary": UTK_ORANGE,
            "background": UTK_DARK,
            "text": WHITE,
            "muted_text": UTK_LIGHT_SMOKE,
            "row_color": UTK_ROW_DARK,
            "subtle_color": UTK_SMOKE,
            "title": "KNOXVILLE",
        }

    raise ValueError("No Color Scheme Given")


# =========================
# GRAPHIC
# =========================

def make_graphic(rows, output, color_scheme, top_n=None):

    colors = get_color_scheme(color_scheme)

    PRIMARY = colors["primary"]
    BACKGROUND = colors["background"]
    TEXT = colors["text"]
    MUTED_TEXT = colors["muted_text"]
    ROW_COLOR = colors["row_color"]
    SUBTLE_COLOR = colors["subtle_color"]
    TITLE = colors["title"]

    if top_n is not None:
        rows = rows[:top_n]

    if not rows:
        raise ValueError("No players found in rankings.csv.")

    # =========================
    # IMAGE SIZE
    # =========================

    row_height = 0.0275
    header_space = 0.20

    height = (
        header_space
        + (len(rows) * row_height)
        + 0.02
    )

    height = max(height, 10.8)

    fig = plt.figure(
        figsize=(19.2, height),
        dpi=100,
    )

    fig.patch.set_facecolor(BACKGROUND)

    ax = fig.add_axes([0, 0, 1, 1])

    ax.set_facecolor(BACKGROUND)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # =========================
    # HEADER
    # =========================

    ax.text(
        0.055,
        0.97,
        f"FULKRANK {TITLE}",
        fontsize=36,
        fontweight="bold",
        color=PRIMARY,
        va="top",
    )

    ax.text(
        0.055,
        0.925,
        "Competitive Player Rankings",
        fontsize=18,
        color=TEXT,
        va="top",
    )

    ax.text(
        0.945,
        0.97,
        date.today().strftime("%B %d, %Y"),
        fontsize=14,
        color=TEXT,
        ha="right",
        va="top",
    )

    ax.text(
        0.945,
        0.935,
        f"{len(rows):,} players",
        fontsize=13,
        color=MUTED_TEXT,
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
        color=PRIMARY,
    )

    ax.text(
        0.135,
        header_y,
        "PLAYER",
        fontsize=11,
        fontweight="bold",
        color=PRIMARY,
    )

    ax.text(
        0.690,
        header_y,
        "RATING",
        fontsize=11,
        fontweight="bold",
        color=PRIMARY,
        ha="right",
    )

    ax.text(
        0.785,
        header_y,
        "MATCHES",
        fontsize=11,
        fontweight="bold",
        color=PRIMARY,
        ha="right",
    )

    ax.text(
        0.865,
        header_y,
        "W",
        fontsize=11,
        fontweight="bold",
        color=PRIMARY,
        ha="right",
    )

    ax.text(
        0.915,
        header_y,
        "L",
        fontsize=11,
        fontweight="bold",
        color=PRIMARY,
        ha="right",
    )

    ax.plot(
        [0.055, 0.945],
        [0.855, 0.855],
        linewidth=2,
        color=PRIMARY,
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

        actual_row_height = (
            top_y - bottom_y
        ) / len(rows)

    else:

        top_y = 0.825
        bottom_y = 0.025

        actual_row_height = (
            top_y - bottom_y
        ) / len(rows)

    # =========================
    # PLAYER ROWS
    # =========================

    for index, row in enumerate(rows):

        y = (
            top_y
            - index * actual_row_height
        )

        rank = int(row["rank"])
        player = row["player"]
        rating = float(row["rating"])
        matches = int(row["matches"])
        wins = int(row["wins"])
        losses = int(row["losses"])

        # =========================
        # ALTERNATING ROWS
        # =========================

        if index % 2 == 1:

            ax.add_patch(
                Rectangle(
                    (
                        0.055,
                        y
                        - actual_row_height / 2,
                    ),
                    0.89,
                    actual_row_height,
                    facecolor=ROW_COLOR,
                    alpha=0.85,
                    transform=ax.transAxes,
                    clip_on=False,
                )
            )

        # =========================
        # FONT SIZE
        # =========================

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

        # =========================
        # TOP THREE
        # =========================

        if rank == 1:

            rank_color = PRIMARY
            rank_size = font_size + 5
            player_weight = "bold"

        elif rank == 2:

            rank_color = TEXT
            rank_size = font_size + 3
            player_weight = "bold"

        elif rank == 3:

            rank_color = MUTED_TEXT
            rank_size = font_size + 2
            player_weight = "bold"

        else:

            rank_color = TEXT
            rank_size = font_size
            player_weight = "normal"

        # =========================
        # RANK
        # =========================

        ax.text(
            0.065,
            y,
            str(rank),
            fontsize=rank_size,
            fontweight=(
                "bold"
                if rank <= 3
                else "normal"
            ),
            color=rank_color,
            va="center",
        )

        # =========================
        # PLAYER
        # =========================

        ax.text(
            0.135,
            y,
            player,
            fontsize=(
                font_size + 1
                if rank <= 3
                else font_size
            ),
            fontweight=player_weight,
            color=TEXT,
            va="center",
        )

        # =========================
        # RATING
        # =========================

        ax.text(
            0.690,
            y,
            f"{rating:.0f}",
            fontsize=(
                font_size + 1
                if rank <= 3
                else font_size
            ),
            fontweight=(
                "bold"
                if rank <= 3
                else "normal"
            ),
            color=PRIMARY,
            ha="right",
            va="center",
        )

        # =========================
        # MATCHES
        # =========================

        ax.text(
            0.785,
            y,
            f"{matches:,}",
            fontsize=font_size,
            color=MUTED_TEXT,
            ha="right",
            va="center",
        )

        # =========================
        # WINS
        # =========================

        ax.text(
            0.865,
            y,
            f"{wins:,}",
            fontsize=font_size,
            color=TEXT,
            ha="right",
            va="center",
        )

        # =========================
        # LOSSES
        # =========================

        ax.text(
            0.915,
            y,
            f"{losses:,}",
            fontsize=font_size,
            color=MUTED_TEXT,
            ha="right",
            va="center",
        )

    # =========================
    # SAVE
    # =========================

    fig.savefig(
        output,
        dpi=100,
        facecolor=BACKGROUND,
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
        help=(
            "Only show the top N players. "
            "Default: all players."
        ),
    )

    parser.add_argument(
        "--color-scheme",
        "-c",
        choices=[
            "ETSU",
            "UTK",
            "etsu",
            "utk",
        ],
        default="UTK",
        help=(
            "Color scheme to use. "
            "Options: ETSU or UTK. "
            "Default: UTK."
        ),
    )

    args = parser.parse_args()

    rows = load_rankings(args.input)

    if not rows:
        raise ValueError(
            "rankings.csv contains no players."
        )

    make_graphic(
        rows,
        args.output,
        args.color_scheme,
        args.top,
    )

    shown = (
        len(rows)
        if args.top is None
        else min(args.top, len(rows))
    )

    print(
        f"Graphic written to {args.output}"
    )

    print(
        f"Players shown: {shown:,}"
    )

    print(
        f"Color Scheme: "
        f"{args.color_scheme.upper()}"
    )


if __name__ == "__main__":
    main()