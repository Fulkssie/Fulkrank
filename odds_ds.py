import pandas as pd

MERGE_MAP = {
    4956095: 1152280,
    4936088: 1029144,
    328976: 2435358, # Cee
    3599805: 2435358, # Cee
}

BLACKLIST = [1962010] # Alight

def load_and_clean(input_csv):
    df = pd.read_csv(input_csv)

    df["Player1ID"] = df["Player1ID"].replace(MERGE_MAP)
    df["Player2ID"] = df["Player2ID"].replace(MERGE_MAP)
    df = df[~df["Player1ID"].isin(BLACKLIST)]
    df = df[~df["Player2ID"].isin(BLACKLIST)]
    df = df[(df["Player1Score"] != -1) & (df["Player2Score"] != -1)]

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Timestamp")

    return df

def get_h2h(input_csv, player1, player2):
    df = load_and_clean(input_csv)

    mask = (
        ((df["Player1ID"] == player1) & (df["Player2ID"] == player2)) |
        ((df["Player1ID"] == player2) & (df["Player2ID"] == player1))
    )
    h2h_df = df[mask]

    if h2h_df.empty:
        return 0, 0

    player1_wins, player2_wins = 0, 0

    for _, row in h2h_df.iterrows():
        if row["Player1ID"] == player1:
            p1 = row["Player1"]
        else:
            p1 = row["Player2"]

        if row["Winner"] == p1:
            player1_wins += 1
        else:
            player2_wins += 1

    return player1_wins, player2_wins