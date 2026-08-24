# =========================
# FULKRANK RANKING MAKER
# =========================
#
# COMMAND EXAMPLES
#
# Build rankings using the optimized default parameters:
#
#   python ranking_maker.py -m sets_dataset.csv -o rankings.csv
#
# Build rankings with custom parameters:
#
#   python ranking_maker.py -m sets_dataset.csv -o rankingsKnox.csv --k 36 --k-provisional 400 --provisional-matches 5 --half-life 0
#
# Build rankings AND per-match history:
#
#   python ranking_maker.py -m sets_dataset.csv -o rankings.csv --match-history match_history.csv
#
# Run parameter optimization with an 80/20 chronological split:
#
#   python ranking_maker.py -m sets_dataset.csv --optimize --split 0.2
#
# Run a custom optimization grid:
#
#   python ranking_maker.py -m sets_dataset.csv --optimize --split 0.2 --k-grid 24,26,28,30,32,34,36 --k-provisional-grid 250,275,300,325,350,375,400,450,500,600 --provisional-matches-grid 25,30,35 --half-life-grid 0
#
# Run the three-way train / validation / test comparison:
#
#   python ranking_maker.py -m sets_dataset.csv --three-way-test
#
# Build rankings as of a specific date:
#
#   python ranking_maker.py -m sets_dataset.csv -o rankings.csv --as-of 2026-08-24
#
# =========================

from __future__ import annotations

import argparse
import csv

from datetime import date, datetime, timedelta, timezone
from math import log


# =========================
# GLOBALS
# =========================

MERGE_MAP = {
    1317379: 1278949,
    4956095: 1152280,
    4936088: 1029144,
    328976: 2435358,
    3599805: 2435358,
}

BLACKLIST = [1962010]

ACTIVITY_WINDOW_DAYS = 365

BASELINE_K = 24.0
BASELINE_K_PROVISIONAL = 40.0
BASELINE_PROVISIONAL_MATCHES = 20
BASELINE_HALF_LIFE = 0.0

OPTIMIZED_K = 32.0
OPTIMIZED_K_PROVISIONAL = 400.0
OPTIMIZED_PROVISIONAL_MATCHES = 5
OPTIMIZED_HALF_LIFE = 0.0


# =========================
# HELPERS
# =========================

def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def new_record() -> dict[str, int]:
    return {
        "wins": 0,
        "losses": 0,
        "matches": 0,
    }


def parse_date(raw: str) -> date:
    return datetime.strptime(raw, "%Y-%m-%d").date()


def timestamp_to_date(raw: str) -> date:
    return datetime.fromtimestamp(
        int(raw),
        tz=timezone.utc,
    ).date()


def normalize_id(player_id: str) -> str:
    numeric_id = int(player_id)

    while numeric_id in MERGE_MAP:
        numeric_id = MERGE_MAP[numeric_id]

    return str(numeric_id)


def recency_weight(
    match_date: date,
    as_of: date,
    half_life_days: float,
) -> float:
    if half_life_days <= 0:
        return 1.0

    age_days = (as_of - match_date).days

    if age_days <= 0:
        return 1.0

    return 0.5 ** (age_days / half_life_days)


def k_factor(
    matches_played: int,
    k: float,
    k_provisional: float,
    provisional_matches: int,
) -> float:
    if (
        provisional_matches > 0
        and matches_played < provisional_matches
    ):
        return k_provisional

    return k


def resolve_outcome(
    row: dict[str, str],
    player_1: str,
    player_2: str,
) -> tuple[str, str]:
    score_1 = float(row["Player1Score"])
    score_2 = float(row["Player2Score"])

    if score_1 == score_2:
        raise ValueError("Scores are tied.")

    if score_1 > score_2:
        return player_1, player_2

    return player_2, player_1


# =========================
# DATA LOADING
# =========================

def load_matches(
    path: str,
) -> tuple[list[dict[str, str]], int]:

    with open(
        path,
        newline="",
        encoding="utf-8",
    ) as handle:

        reader = csv.DictReader(handle)

        required = {
            "Timestamp",
            "Player1ID",
            "Player1",
            "Player2ID",
            "Player2",
            "Player1Score",
            "Player2Score",
            "Tournament",
        }

        missing = required - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"Missing required columns: "
                f"{', '.join(sorted(missing))}"
            )

        rows: list[dict[str, str]] = []

        removed_blacklisted = 0

        for row in reader:

            if (
                not row["Player1Score"].strip()
                or not row["Player2Score"].strip()
            ):
                continue

            score_1 = float(row["Player1Score"])
            score_2 = float(row["Player2Score"])

            if score_1 < 0 or score_2 < 0:
                continue

            id_1 = normalize_id(row["Player1ID"])
            id_2 = normalize_id(row["Player2ID"])

            if (
                int(id_1) in BLACKLIST
                or int(id_2) in BLACKLIST
            ):
                removed_blacklisted += 1
                continue

            row["Player1ID"] = id_1
            row["Player2ID"] = id_2

            rows.append(row)

    rows.sort(
        key=lambda row: int(row["Timestamp"])
    )

    return rows, removed_blacklisted


# =========================
# MATCH PROCESSING
# =========================

def apply_matches(
    rows: list[dict[str, str]],
    ratings: dict[str, float],
    records: dict[str, dict[str, int]],
    k: float,
    base: float,
    k_provisional: float,
    provisional_matches: int,
    half_life_days: float = 0.0,
    as_of: date | None = None,
    predictions: list[
        tuple[float, float, date, str, str]
    ] | None = None,
    names: dict[str, str] | None = None,
) -> None:

    if not rows:
        return

    if as_of is None:
        as_of = max(
            timestamp_to_date(row["Timestamp"])
            for row in rows
        )

    for row in rows:

        id_1 = row["Player1ID"]
        id_2 = row["Player2ID"]

        if names is not None:
            names[id_1] = row["Player1"]
            names[id_2] = row["Player2"]

        winner, loser = resolve_outcome(
            row,
            id_1,
            id_2,
        )

        ratings.setdefault(winner, base)
        ratings.setdefault(loser, base)

        records.setdefault(
            winner,
            new_record(),
        )

        records.setdefault(
            loser,
            new_record(),
        )

        match_date = timestamp_to_date(
            row["Timestamp"]
        )

        if predictions is not None:

            prediction = expected_score(
                ratings[id_1],
                ratings[id_2],
            )

            actual = (
                1.0
                if winner == id_1
                else 0.0
            )

            predictions.append(
                (
                    prediction,
                    actual,
                    match_date,
                    id_1,
                    id_2,
                )
            )

        weight = recency_weight(
            match_date,
            as_of,
            half_life_days,
        )

        winner_k = (
            k_factor(
                records[winner]["matches"],
                k,
                k_provisional,
                provisional_matches,
            )
            * weight
        )

        loser_k = (
            k_factor(
                records[loser]["matches"],
                k,
                k_provisional,
                provisional_matches,
            )
            * weight
        )

        expected_winner = expected_score(
            ratings[winner],
            ratings[loser],
        )

        ratings[winner] += (
            winner_k
            * (1.0 - expected_winner)
        )

        ratings[loser] -= (
            loser_k
            * (1.0 - expected_winner)
        )

        records[winner]["matches"] += 1
        records[winner]["wins"] += 1

        records[loser]["matches"] += 1
        records[loser]["losses"] += 1


# =========================
# MATCH HISTORY OUTPUT
# =========================

def write_match_history(
    path: str,
    rows: list[dict[str, str]],
    player: str,
    k: float,
    base: float,
    k_provisional: float,
    provisional_matches: int,
    half_life_days: float,
    as_of: date,
) -> None:

    ratings: dict[str, float] = {}
    records: dict[str, dict[str, int]] = {}

    # Normalize the requested player if they supplied an ID.
    normalized_player_id = None

    try:
        normalized_player_id = normalize_id(player)
    except ValueError:
        pass

    found_player = False

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:

        writer = csv.writer(handle)

        writer.writerow([
            "date",
            "opponent",
            "tournament",
            "score",
            "elo_change",
        ])

        for row in rows:

            id_1 = row["Player1ID"]
            id_2 = row["Player2ID"]

            ratings.setdefault(id_1, base)
            ratings.setdefault(id_2, base)

            records.setdefault(
                id_1,
                new_record(),
            )

            records.setdefault(
                id_2,
                new_record(),
            )

            match_date = timestamp_to_date(
                row["Timestamp"]
            )

            winner, loser = resolve_outcome(
                row,
                id_1,
                id_2,
            )

            weight = recency_weight(
                match_date,
                as_of,
                half_life_days,
            )

            winner_k = (
                k_factor(
                    records[winner]["matches"],
                    k,
                    k_provisional,
                    provisional_matches,
                )
                * weight
            )

            loser_k = (
                k_factor(
                    records[loser]["matches"],
                    k,
                    k_provisional,
                    provisional_matches,
                )
                * weight
            )

            expected_winner = expected_score(
                ratings[winner],
                ratings[loser],
            )

            winner_change = (
                winner_k
                * (1.0 - expected_winner)
            )

            loser_change = (
                -loser_k
                * (1.0 - expected_winner)
            )

            # Determine whether the requested player
            # is Player 1 or Player 2.
            player_1_matches = (
                normalized_player_id == id_1
                or player.lower()
                == row["Player1"].strip().lower()
            )

            player_2_matches = (
                normalized_player_id == id_2
                or player.lower()
                == row["Player2"].strip().lower()
            )

            if player_1_matches and player_2_matches:
                raise ValueError(
                    "Player matched both sides of a match."
                )

            if player_1_matches:

                found_player = True

                opponent = row["Player2"]

                score = (
                    f'{int(float(row["Player1Score"]))}-'
                    f'{int(float(row["Player2Score"]))}'
                )

                elo_change = (
                    winner_change
                    if winner == id_1
                    else loser_change
                )

                writer.writerow([
                    match_date.isoformat(),
                    opponent,
                    row["Tournament"],
                    score,
                    round(elo_change, 2),
                ])

            elif player_2_matches:

                found_player = True

                opponent = row["Player1"]

                # Reverse the score so it is always
                # from the selected player's perspective.
                score = (
                    f'{row["Player2Score"]}-'
                    f'{row["Player1Score"]}'
                )

                elo_change = (
                    winner_change
                    if winner == id_2
                    else loser_change
                )

                writer.writerow([
                    match_date.isoformat(),
                    opponent,
                    row["Tournament"],
                    score,
                    round(elo_change, 2),
                ])

            # IMPORTANT:
            # Apply Elo changes for EVERY match,
            # even when this isn't the selected player.
            ratings[winner] += winner_change
            ratings[loser] += loser_change

            records[winner]["matches"] += 1
            records[winner]["wins"] += 1

            records[loser]["matches"] += 1
            records[loser]["losses"] += 1

    if not found_player:
        raise ValueError(
            f"Could not find player: {player}"
        )


# =========================
# ACTIVITY / RANK ELIGIBILITY
# =========================

def eligible_player_ids(
    rows: list[dict[str, str]],
    as_of: date,
    activity_window_days: int = ACTIVITY_WINDOW_DAYS,
) -> set[str]:

    cutoff = (
        as_of
        - timedelta(days=activity_window_days)
    )

    eligible: set[str] = set()

    for row in rows:

        match_date = timestamp_to_date(
            row["Timestamp"]
        )

        if match_date >= cutoff:

            eligible.add(row["Player1ID"])
            eligible.add(row["Player2ID"])

    return eligible


def ranked_player_ids(
    rows: list[dict[str, str]],
    records: dict[str, dict[str, int]],
    as_of: date,
    min_matches: int,
) -> set[str]:

    active_players = eligible_player_ids(
        rows,
        as_of,
    )

    return {
        player_id
        for player_id in active_players
        if records.get(
            player_id,
            new_record(),
        )["matches"] >= min_matches
    }


def filter_eligible_predictions(
    predictions: list[
        tuple[float, float, date, str, str]
    ],
    eligible_players: set[str],
) -> list[tuple[float, float]]:

    return [
        (prediction, actual)
        for (
            prediction,
            actual,
            _,
            player_1,
            player_2,
        ) in predictions
        if (
            player_1 in eligible_players
            and player_2 in eligible_players
        )
    ]


# =========================
# METRICS
# =========================

def log_loss(
    predictions: list[tuple[float, float]],
    eps: float = 1e-15,
) -> float:

    if not predictions:
        return float("nan")

    total = 0.0

    for probability, actual in predictions:

        probability = min(
            max(probability, eps),
            1.0 - eps,
        )

        total += -(
            actual * log(probability)
            + (1.0 - actual)
            * log(1.0 - probability)
        )

    return total / len(predictions)


def brier_score(
    predictions: list[tuple[float, float]],
) -> float:

    if not predictions:
        return float("nan")

    return sum(
        (prediction - actual) ** 2
        for prediction, actual in predictions
    ) / len(predictions)


def accuracy(
    predictions: list[tuple[float, float]],
) -> float:

    if not predictions:
        return float("nan")

    correct = sum(
        1
        for prediction, actual in predictions
        if (
            prediction >= 0.5
            and actual == 1.0
        )
        or (
            prediction < 0.5
            and actual == 0.0
        )
    )

    return correct / len(predictions)


# =========================
# EVALUATION
# =========================

def evaluate_params(
    rows: list[dict[str, str]],
    base: float,
    k: float,
    k_provisional: float,
    provisional_matches: int,
    half_life_days: float,
    as_of: date,
    warmup_rows: list[
        dict[str, str]
    ] | None = None,
) -> tuple[float, int, int]:

    ratings: dict[str, float] = {}
    records: dict[str, dict[str, int]] = {}

    if warmup_rows:

        apply_matches(
            warmup_rows,
            ratings,
            records,
            k,
            base,
            k_provisional,
            provisional_matches,
            half_life_days,
            as_of,
        )

    predictions: list[
        tuple[float, float, date, str, str]
    ] = []

    apply_matches(
        rows,
        ratings,
        records,
        k,
        base,
        k_provisional,
        provisional_matches,
        half_life_days,
        as_of,
        predictions,
    )

    eligible_players = eligible_player_ids(
        rows,
        as_of,
    )

    filtered_predictions = (
        filter_eligible_predictions(
            predictions,
            eligible_players,
        )
    )

    return (
        log_loss(filtered_predictions),
        len(filtered_predictions),
        len(predictions),
    )


# =========================
# DATA SPLITTING
# =========================

def split_rows(
    rows: list[dict[str, str]],
    fraction: float,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
]:

    if not 0.0 < fraction < 1.0:
        raise ValueError(
            "Split must be between 0 and 1."
        )

    cut = int(
        round(
            len(rows)
            * (1.0 - fraction)
        )
    )

    cut = max(
        1,
        min(cut, len(rows) - 1),
    )

    return rows[:cut], rows[cut:]


def three_way_split(
    rows: list[dict[str, str]],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:

    train_end = int(
        len(rows) * 0.70
    )

    validation_end = int(
        len(rows) * 0.85
    )

    return (
        rows[:train_end],
        rows[train_end:validation_end],
        rows[validation_end:],
    )


# =========================
# PARAMETER GRID
# =========================

def parse_grid(
    spec: str | None,
    default: list[float],
) -> list[float]:

    if not spec:
        return default

    values: list[float] = []

    for token in spec.split(","):

        token = token.strip()

        if token:
            values.append(
                float(token)
            )

    return values or default


# =========================
# OPTIMIZATION
# =========================

def optimize(
    rows: list[dict[str, str]],
    base: float,
    k_grid: list[float],
    k_provisional_grid: list[float],
    provisional_matches_grid: list[float],
    half_life_grid: list[float],
    as_of: date,
    split: float,
) -> None:

    train_rows, validation_rows = (
        split_rows(rows, split)
    )

    total = (
        len(k_grid)
        * len(k_provisional_grid)
        * len(provisional_matches_grid)
        * len(half_life_grid)
    )

    print()
    print(
        f"Testing {total:,} parameter combinations..."
    )
    print(
        f"Training matches:   {len(train_rows):,}"
    )
    print(
        f"Validation matches: {len(validation_rows):,}"
    )
    print(
        f"Activity window:    "
        f"{ACTIVITY_WINDOW_DAYS} days"
    )

    baseline_loss, baseline_eligible, baseline_total = (
        evaluate_params(
            validation_rows,
            base,
            BASELINE_K,
            BASELINE_K_PROVISIONAL,
            BASELINE_PROVISIONAL_MATCHES,
            BASELINE_HALF_LIFE,
            as_of,
            train_rows,
        )
    )

    print()
    print("Baseline:")
    print(
        f"K                 = "
        f"{BASELINE_K:g}"
    )
    print(
        f"K-provisional     = "
        f"{BASELINE_K_PROVISIONAL:g}"
    )
    print(
        f"Provisional match = "
        f"{BASELINE_PROVISIONAL_MATCHES}"
    )
    print(
        f"Half-life         = "
        f"{BASELINE_HALF_LIFE:g}"
    )
    print(
        f"Eligible matches  = "
        f"{baseline_eligible:,} / "
        f"{baseline_total:,}"
    )
    print(
        f"Log-loss          = "
        f"{baseline_loss:.4f}"
    )

    print()

    results: list[
        tuple[
            float,
            float,
            float,
            int,
            float,
            int,
        ]
    ] = []

    for k in k_grid:

        for k_provisional in k_provisional_grid:

            for provisional_matches in (
                provisional_matches_grid
            ):

                for half_life in half_life_grid:

                    if k_provisional < k:
                        continue

                    loss, eligible, _ = (
                        evaluate_params(
                            validation_rows,
                            base,
                            k,
                            k_provisional,
                            int(provisional_matches),
                            half_life,
                            as_of,
                            train_rows,
                        )
                    )

                    results.append(
                        (
                            loss,
                            k,
                            k_provisional,
                            int(provisional_matches),
                            half_life,
                            eligible,
                        )
                    )

    if not results:
        print(
            "No valid parameter combinations found."
        )
        return

    results.sort(
        key=lambda result: result[0]
    )

    print(
        "Log-loss      K  K-prov  Prov-N  "
        "Half-Life   Eligible "
        "(scored on: validation)"
    )

    print("-" * 76)

    for (
        loss,
        k,
        k_provisional,
        provisional_matches,
        half_life,
        eligible,
    ) in results[:10]:

        half_life_display = (
            "off"
            if half_life <= 0
            else f"{half_life:g}"
        )

        print(
            f"{loss:>8.4f} "
            f"{k:>5g} "
            f"{k_provisional:>7g} "
            f"{provisional_matches:>7d} "
            f"{half_life_display:>10} "
            f"{eligible:>10,}"
        )

    best = results[0]

    absolute_change = (
        baseline_loss - best[0]
    )

    relative_change = (
        absolute_change
        / baseline_loss
        * 100
        if baseline_loss
        else float("nan")
    )

    print()
    print("Best configuration:")
    print(
        f"--k {best[1]:g} "
        f"--k-provisional {best[2]:g} "
        f"--provisional-matches {best[3]} "
        f"--half-life {best[4]:g}"
    )

    print(
        f"Eligible validation matches = "
        f"{best[5]:,}"
    )

    print(
        f"Log-loss = {best[0]:.4f}"
    )

    print()
    print("Comparison:")
    print(
        f"Baseline log-loss:  "
        f"{baseline_loss:.4f}"
    )
    print(
        f"Best log-loss:      "
        f"{best[0]:.4f}"
    )
    print(
        f"Absolute change:    "
        f"+{absolute_change:.4f}"
    )
    print(
        f"Relative change:    "
        f"+{relative_change:.2f}%"
    )
    print(
        f"Result: "
        f"{'IMPROVEMENT' if best[0] < baseline_loss else 'NO IMPROVEMENT'}"
    )


# =========================
# THREE-WAY TEST
# =========================

def print_model_results(
    label: str,
    k: float,
    k_provisional: float,
    provisional_matches: int,
    loss: float,
    eligible: int,
    total: int,
) -> None:

    print(label)
    print(f"K:                 {k:g}")
    print(
        f"K-provisional:     "
        f"{k_provisional:g}"
    )
    print(
        f"Provisional:       "
        f"{provisional_matches}"
    )
    print(
        f"Eligible matches:  "
        f"{eligible:,} / {total:,}"
    )
    print(
        f"Log-loss:          "
        f"{loss:.4f}"
    )


def three_way_test(
    rows: list[dict[str, str]],
    base: float,
    as_of: date,
) -> None:

    train_rows, validation_rows, test_rows = (
        three_way_split(rows)
    )

    print()
    print(
        f"Training:   "
        f"{len(train_rows):,} matches"
    )
    print(
        f"Validation: "
        f"{len(validation_rows):,} matches"
    )
    print(
        f"Test:       "
        f"{len(test_rows):,} matches"
    )

    print()
    print(
        "Player IDs normalized with MERGE_MAP."
    )
    print(
        f"Blacklisted IDs removed: "
        f"{BLACKLIST}"
    )
    print(
        f"Activity requirement: "
        f"1 match within "
        f"{ACTIVITY_WINDOW_DAYS} days"
    )

    print()
    print(
        "The test set is NOT used "
        "to choose parameters."
    )

    print()
    print("---")
    print()
    print("VALIDATION")
    print()

    (
        baseline_validation_loss,
        baseline_validation_eligible,
        baseline_validation_total,
    ) = evaluate_params(
        validation_rows,
        base,
        BASELINE_K,
        BASELINE_K_PROVISIONAL,
        BASELINE_PROVISIONAL_MATCHES,
        BASELINE_HALF_LIFE,
        as_of,
        train_rows,
    )

    (
        optimized_validation_loss,
        optimized_validation_eligible,
        optimized_validation_total,
    ) = evaluate_params(
        validation_rows,
        base,
        OPTIMIZED_K,
        OPTIMIZED_K_PROVISIONAL,
        OPTIMIZED_PROVISIONAL_MATCHES,
        OPTIMIZED_HALF_LIFE,
        as_of,
        train_rows,
    )

    print_model_results(
        "Baseline",
        BASELINE_K,
        BASELINE_K_PROVISIONAL,
        BASELINE_PROVISIONAL_MATCHES,
        baseline_validation_loss,
        baseline_validation_eligible,
        baseline_validation_total,
    )

    print()

    print_model_results(
        "Optimized",
        OPTIMIZED_K,
        OPTIMIZED_K_PROVISIONAL,
        OPTIMIZED_PROVISIONAL_MATCHES,
        optimized_validation_loss,
        optimized_validation_eligible,
        optimized_validation_total,
    )

    print()
    print("---")
    print()
    print("FINAL TEST")
    print()

    (
        baseline_test_loss,
        baseline_test_eligible,
        baseline_test_total,
    ) = evaluate_params(
        test_rows,
        base,
        BASELINE_K,
        BASELINE_K_PROVISIONAL,
        BASELINE_PROVISIONAL_MATCHES,
        BASELINE_HALF_LIFE,
        as_of,
        train_rows + validation_rows,
    )

    (
        optimized_test_loss,
        optimized_test_eligible,
        optimized_test_total,
    ) = evaluate_params(
        test_rows,
        base,
        OPTIMIZED_K,
        OPTIMIZED_K_PROVISIONAL,
        OPTIMIZED_PROVISIONAL_MATCHES,
        OPTIMIZED_HALF_LIFE,
        as_of,
        train_rows + validation_rows,
    )

    print_model_results(
        "Baseline:",
        BASELINE_K,
        BASELINE_K_PROVISIONAL,
        BASELINE_PROVISIONAL_MATCHES,
        baseline_test_loss,
        baseline_test_eligible,
        baseline_test_total,
    )

    print()

    print_model_results(
        "Optimized:",
        OPTIMIZED_K,
        OPTIMIZED_K_PROVISIONAL,
        OPTIMIZED_PROVISIONAL_MATCHES,
        optimized_test_loss,
        optimized_test_eligible,
        optimized_test_total,
    )

    absolute_improvement = (
        baseline_test_loss
        - optimized_test_loss
    )

    relative_improvement = (
        absolute_improvement
        / baseline_test_loss
        * 100
        if baseline_test_loss
        else float("nan")
    )

    print()
    print(
        f"Baseline log-loss:   "
        f"{baseline_test_loss:.4f}"
    )
    print(
        f"Optimized log-loss:  "
        f"{optimized_test_loss:.4f}"
    )
    print(
        f"Absolute improvement:"
        f"+{absolute_improvement:.4f}"
    )
    print(
        f"Relative improvement:"
        f"+{relative_improvement:.2f}%"
    )

    print()

    if optimized_test_loss < baseline_test_loss:
        print(
            "RESULT: OPTIMIZED MODEL WINS"
        )
    else:
        print(
            "RESULT: BASELINE MODEL WINS"
        )


# =========================
# RANKING OUTPUT
# =========================

def write_ratings(
    path: str,
    ratings: dict[str, float],
    records: dict[str, dict[str, int]],
    names: dict[str, str],
    rows: list[dict[str, str]],
    as_of: date,
    min_matches: int,
) -> None:

    eligible = ranked_player_ids(
        rows,
        records,
        as_of,
        min_matches,
    )

    ordered = sorted(
        [
            (player_id, rating)
            for player_id, rating in ratings.items()
            if player_id in eligible
        ],
        key=lambda item: item[1],
        reverse=True,
    )

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:

        writer = csv.writer(handle)

        writer.writerow([
            "rank",
            "id",
            "player",
            "rating",
            "matches",
            "wins",
            "losses",
        ])

        for rank, (player_id, rating) in enumerate(
            ordered,
            start=1,
        ):

            record = records.get(
                player_id,
                new_record(),
            )

            writer.writerow([
                rank,
                player_id,
                names.get(
                    player_id,
                    player_id,
                ),
                round(rating, 2),
                record["matches"],
                record["wins"],
                record["losses"],
            ])


# =========================
# MAIN
# =========================

def main(
    argv: list[str] | None = None,
) -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Build Fulkrank Elo ratings "
            "from match history."
        )
    )

    parser.add_argument(
        "--matches",
        "-m",
        required=True,
    )

    parser.add_argument(
        "--k",
        type=float,
        default=OPTIMIZED_K,
    )

    parser.add_argument(
        "--k-provisional",
        type=float,
        default=OPTIMIZED_K_PROVISIONAL,
    )

    parser.add_argument(
        "--provisional-matches",
        type=int,
        default=OPTIMIZED_PROVISIONAL_MATCHES,
    )

    parser.add_argument(
        "--base",
        type=float,
        default=1200.0,
    )

    parser.add_argument(
        "--half-life",
        type=float,
        default=OPTIMIZED_HALF_LIFE,
    )

    parser.add_argument(
        "--as-of",
    )

    parser.add_argument(
        "--output",
        "-o",
    )

    parser.add_argument(
        "--match-history",
        help=(
            "Write per-match Elo history "
            "to CSV."
        ),
    )

    parser.add_argument(
        "--player",
        help="Player name or ID for match history output.",
    )

    parser.add_argument(
        "--optimize",
        action="store_true",
    )

    parser.add_argument(
        "--three-way-test",
        action="store_true",
    )

    parser.add_argument(
        "--split",
        type=float,
        default=0.20,
    )

    parser.add_argument(
        "--k-grid",
    )

    parser.add_argument(
        "--k-provisional-grid",
    )

    parser.add_argument(
        "--provisional-matches-grid",
    )

    parser.add_argument(
        "--half-life-grid",
    )

    args = parser.parse_args(argv)

    try:

        rows, removed_blacklisted = (
            load_matches(args.matches)
        )

        print(
            f"Loaded {len(rows):,} "
            f"cleaned matches."
        )

        print(
            f"Merge map entries: "
            f"{len(MERGE_MAP)}"
        )

        print(
            f"Blacklisted IDs removed: "
            f"{BLACKLIST}"
        )

        if not rows:
            raise ValueError(
                "No valid matches were loaded."
            )

        if args.as_of:
            as_of = parse_date(
                args.as_of
            )
        else:
            as_of = max(
                timestamp_to_date(
                    row["Timestamp"]
                )
                for row in rows
            )

        if args.three_way_test:

            three_way_test(
                rows,
                args.base,
                as_of,
            )

            return 0

        if args.optimize:

            optimize(
                rows,
                args.base,
                parse_grid(
                    args.k_grid,
                    [12, 16, 20, 24, 32, 40],
                ),
                parse_grid(
                    args.k_provisional_grid,
                    [40, 60, 80],
                ),
                parse_grid(
                    args.provisional_matches_grid,
                    [0, 10, 20, 30],
                ),
                parse_grid(
                    args.half_life_grid,
                    [0, 100, 365, 730],
                ),
                as_of,
                args.split,
            )

            return 0

        ratings: dict[str, float] = {}
        records: dict[str, dict[str, int]] = {}
        names: dict[str, str] = {}

        apply_matches(
            rows,
            ratings,
            records,
            args.k,
            args.base,
            args.k_provisional,
            args.provisional_matches,
            args.half_life,
            as_of,
            names=names,
        )

        if args.output:

            write_ratings(
                args.output,
                ratings,
                records,
                names,
                rows,
                as_of,
                args.provisional_matches,
            )

            print(
                f"Ratings written to "
                f"{args.output}"
            )

            print(
                f"Minimum matches to rank: "
                f"{args.provisional_matches}"
            )

            print(
                f"Activity requirement: "
                f"1 match within "
                f"{ACTIVITY_WINDOW_DAYS} days"
            )

        if args.match_history:

            if not args.player:
                raise ValueError(
                    "--player is required for match history"
                )

            write_match_history(
                args.match_history,
                rows,
                args.player,
                args.k,
                args.base,
                args.k_provisional,
                args.provisional_matches,
                args.half_life,
                as_of,
    )

            print(
                f"Match history written to "
                f"{args.match_history}"
            )

        return 0

    except (OSError, ValueError) as error:

        print(
            f"Error: {error}"
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
