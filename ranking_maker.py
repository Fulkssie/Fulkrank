# =========================
# IMPORTS
# =========================
import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime


# =========================
# GLOBALS
# =========================
MIN_SETS = 25

BASE_K = 32
MAX_K = 40

INITIAL_RATING = 1500
INITIAL_RD = 350
MIN_RD = 50
RD_DECAY_PER_DAY = 1.2


MERGE_MAP = {
    1317379: 1278949,
    4956095: 1152280,
    4936088: 1029144,
    328976: 2435358,
    3599805: 2435358,
}

BLACKLIST = [1962010]


# =========================
# DATA LOADING
# =========================
def load_and_clean(input_csv):
    df = pd.read_csv(input_csv)

    df["Player1ID"] = df["Player1ID"].replace(MERGE_MAP)
    df["Player2ID"] = df["Player2ID"].replace(MERGE_MAP)

    df = df[~df["Player1ID"].isin(BLACKLIST)]
    df = df[~df["Player2ID"].isin(BLACKLIST)]

    df = df[(df["Player1Score"] >= 0) & (df["Player2Score"] >= 0)]

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")

    return df


# =========================
# ELO CORE
# =========================
def expected_score(r1, r2):
    return 1 / (1 + 10 ** ((r2 - r1) / 400))


def update_elo(r1, r2, score1, k):
    exp1 = expected_score(r1, r2)

    new_r1 = r1 + k * (score1 - exp1)
    new_r2 = r2 + k * ((1 - score1) - (1 - exp1))

    return new_r1, new_r2


def compute_k(rd):
    k = BASE_K * (rd / INITIAL_RD)
    return min(k, MAX_K)


# =========================
# BUILD ELIGIBILITY MAP (PASS 1)
# =========================
def build_match_counts(df):
    counts = {}

    for row in df.itertuples():
        counts[row.Player1ID] = counts.get(row.Player1ID, 0) + 1
        counts[row.Player2ID] = counts.get(row.Player2ID, 0) + 1

    return counts


def get_eligible_players(match_counts):
    return {pid for pid, c in match_counts.items() if c >= MIN_SETS}


# =========================
# RANKING SYSTEM
# =========================
def generate_rankings(input_csv, output_dir="rankings"):
    os.makedirs(output_dir, exist_ok=True)
    df = load_and_clean(input_csv)

    # =========================
    # PASS 1: eligibility
    # =========================
    match_counts = build_match_counts(df)
    eligible_players = get_eligible_players(match_counts)

    # =========================
    # INIT STATE
    # =========================
    ratings = {}
    rd = {}
    last_played = {}
    names = {}

    history = []

    # =========================
    # PASS 2: SIMULATION
    # =========================
    for row in df.itertuples():
        p1, p2 = row.Player1ID, row.Player2ID

        # HARD FILTER RULE
        if p1 not in eligible_players or p2 not in eligible_players:
            continue

        for p in [p1, p2]:
            if p not in ratings:
                ratings[p] = INITIAL_RATING
                rd[p] = INITIAL_RD

        # inactivity RD inflation
        for p in [p1, p2]:
            if p in last_played:
                days_inactive = (row.Date - last_played[p]).days
                rd[p] = min(
                    INITIAL_RD,
                    rd[p] + RD_DECAY_PER_DAY * days_inactive
                )

        last_played[p1] = row.Date
        last_played[p2] = row.Date

        total = row.Player1Score + row.Player2Score
        if total <= 0:
            continue

        s1 = row.Player1Score / total

        r1, r2 = ratings[p1], ratings[p2]

        k = (compute_k(rd[p1]) + compute_k(rd[p2])) / 2

        new_r1, new_r2 = update_elo(r1, r2, s1, k)

        ratings[p1], ratings[p2] = new_r1, new_r2

        rd[p1] = max(MIN_RD, rd[p1] * 0.9)
        rd[p2] = max(MIN_RD, rd[p2] * 0.9)

        names[p1] = row.Player1
        names[p2] = row.Player2

        # history
        history.append({
            "Date": row.Date,
            "Id": p1,
            "Player": names.get(p1, "Unknown"),
            "Rating": ratings[p1],
            "Sets": match_counts.get(p1, 0)
        })

        history.append({
            "Date": row.Date,
            "Id": p2,
            "Player": names.get(p2, "Unknown"),
            "Rating": ratings[p2],
            "Sets": match_counts.get(p2, 0)
        })

    # =========================
    # HISTORY DF
    # =========================
    history_df = pd.DataFrame(history)
    history_df["Date"] = pd.to_datetime(history_df["Date"])

    # =========================
    # FINAL RANKINGS
    # =========================
    rank_data = []

    for pid in ratings:
        if pid not in eligible_players:
            continue

        rank_data.append({
            "Id": pid,
            "Player": names.get(pid, "Unknown"),
            "Elo": round(ratings[pid], 2),
            "Sets": match_counts.get(pid, 0),
            "LastMatch": last_played.get(pid, pd.NaT)
        })

    rank_df = pd.DataFrame(rank_data)
    rank_df = rank_df.sort_values("Elo", ascending=False)
    rank_df.insert(0, "Rank", range(1, len(rank_df) + 1))

    # save
    output_csv = f"{output_dir}/{datetime.now().strftime('%Y-%m-%d')}.csv"
    rank_df.to_csv(output_csv, index=False)

    print(f"Saved rankings: {output_csv}")
    print(f"Eligible players: {len(rank_df)}")

    return rank_df, history_df


# =========================
# RUN
# =========================
if __name__ == "__main__":
    generate_rankings("sets_dataset.csv")
