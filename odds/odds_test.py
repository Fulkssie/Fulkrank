import pandas as pd
import numpy as np
import os
import glob
import Fulkrank.odds.odds_ds as odds_ds

def load_ranking(input_csv):
    df = pd.read_csv(input_csv)

    return df

def get_previous_ranking(latest_dir="rankings"):
    """Returns the most recent ranking file as a DataFrame, or None."""
    if not os.path.exists(latest_dir):
        return None

    files = sorted(glob.glob(f"{latest_dir}/*.csv"))
    if len(files) == 0:
        return None

    return pd.read_csv(files[-1]) 

def calculate_odds(p1_elo,  p2_elo, player1_wins, player2_wins, w=0.25):
    margin = 0.05

    elo_diff = p2_elo - p1_elo
    prob_a_elo = 1 / (1 + np.power(10, elo_diff / 300))

    total_h2h = player1_wins + player2_wins
    if total_h2h > 0:
        prob_a_h2h = player1_wins / total_h2h

        effective_weight = w * min(1, total_h2h / 3)

        prob_a = ((1 - effective_weight) * prob_a_elo) + (effective_weight * prob_a_h2h)
    else:
        prob_a = prob_a_elo

    prob_b = 1 - prob_a

    odds_a = 1 / prob_a
    odds_b = 1 / prob_b

    odds_a *= (1 + margin)
    odds_b *= (1 + margin)

    prob_a_final = 1 / odds_a
    prob_b_final = 1 / odds_b

    return(prob_a_final, prob_b_final, odds_a, odds_b)

def to_american(p, cap_long = 5000, cap_fav = -5000):
    if p > 0.5:
        x = -100 * p / (1 - p)
        return max(x, cap_fav)
    else:
        x = 100 * (1 - p) / p
        return min(x, cap_long)

def get_elo(player_name, df):
    for _, row in df.iterrows():
        if player_name == row["Player"]:
            return row["Elo"]
    return None
            
player1ID = 1152280
player2ID = 64572
player1 = "BOTS | pp | Canis"
player2 = "BRAVO | ishy"

player1_h2h, player2_h2h = odds_ds.get_h2h("sets_dataset.csv", player1ID, player2ID)

prev_df = get_previous_ranking("rankings")

player1_elo = get_elo(player1, prev_df)
player2_elo = get_elo(player2, prev_df)

prob1, prob2, odds1, odds2 = calculate_odds(player1_elo, player2_elo, player1_h2h, player2_h2h)
print(f"Player1 Elo: {player1_elo}")
print(f"Player2 Elo: {player2_elo}")
print(f"Player1 Odds: {odds1}")
print(f"Player2 Odds: {odds2}")
print(f"Total Odds {odds1 + odds2}")
print(f"Player1 Probability: {prob1}")
print(f"Player2 Probability: {prob2}")
print(f"Total Probability {prob1 + prob2}")
print(f"Player1: {round(to_american(prob1))}, Player2: {round(to_american(prob2))}")