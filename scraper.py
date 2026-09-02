
# =========================
# FULKRANK START.GG SCRAPER
# =========================
#
# COMMAND EXAMPLES
#
# Scrape Knoxville tournaments:
#
#   python scraper.py -t tournamentsKnox.txt -o Rankings/sets_dataset_knox.csv
#
# Scrape TRICOT tournaments:
#
#   python scraper.py -t tournamentsTricot.txt -o Rankings/sets_dataset_tricot.csv
#
# =========================

from __future__ import annotations

import argparse
import asyncio
import os
import time
import re
from datetime import datetime

import aiohttp
import pandas
import requests

from queries import (
    QUERY_TOURNAMENT_NAME,
    QUERY_EVENT_ID,
    QUERY_EVENT,
    QUERY_PHASES,
)

# ===========================
# GLOBALS
# ===========================

API_KEY = "a6345f8ee6d3390b8fc62b5d98091087"

API_VERSION = "alpha"

URL = f"https://api.start.gg/gql/{API_VERSION}"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

PER_PAGE = 25

# ============================
# DATA FETCHING
# ============================

async def fetch_phase_data(session: aiohttp.ClientSession, phase_ids: list[dict]) -> list[dict]:

    all_sets = []

    for phase_id in phase_ids:
        page = 1
        retry_delay = 2

        while True:
            try:
                async with session.post(URL, headers=HEADERS, json={"query": QUERY_PHASES, "variables": {"phaseId": phase_id, "page": page, "perPage": PER_PAGE}}) as response:
                    
                    if response.status == 429:
                        print(f"Rate limit hit for sets. Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue

                    if response.status != 200:
                        print(f"Error fetching sets data (Phase {phase_id}, Page {page}): {response.status}")
                        print(await response.text())
                        break

                    data = await response.json()
                    sets = (
                        data
                        .get("data", {})
                        .get("phase", {})
                        .get("sets", {})
                        .get("nodes", [])
                    )

                    if not sets:
                        break

                    all_sets.extend(sets)
                    page += 1
                    retry_delay = 2

            except Exception as e:
                print(f"Unexpected error: {e}")
                break

    return all_sets


def fetch_tournament_name(slug: str) -> str | None:

    try:
        response = requests.post(URL, headers=HEADERS, json={"query": QUERY_TOURNAMENT_NAME, "variables": {"slug": slug}})

        if response.status_code == 200:
            return (
                response
                .json()
                .get("data", {})
                .get("tournament", {})
                .get("name")
            )
        
        if response.status_code == 429:
            print("Rate limit hit on Tournament Name fetch. Waiting 30 seconds...")
            time.sleep(30)
            return None
        
        print(f"API Error {response.status_code} for {slug}")
        return None

    except requests.exceptions.JSONDecodeError:
        print(f"Warning: Received empty/invalid response for {slug}. Skipping...")
        return None


def fetch_event_id(slug: str) -> str | None:
    try:

        response = requests.post(URL, headers=HEADERS, json={"query": QUERY_EVENT_ID, "variables": {"slug": slug}})

        data = response.json()

        if "errors" in data:
            print(f"Errors in data: {data["errors"]}")
            return None

        return (
            data
            .get("data", {})
            .get("event", {})
            .get("id")
        )

    except(requests.exceptions.RequestException, requests.exceptions.JSONDecodeError) as error:
        print(f"Error fetching event id: {error}")
        return None


def fetch_event_data(event_id: str) -> list[int]:

    try:
        response = requests.post(URL, headers=HEADERS, json={"query": QUERY_EVENT, "variables": {"eventId": event_id}})

        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            return []

        data = response.json()

        if "errors" in data:
            print("Error:", data["errors"])
            return []

        phases = (
            data
            .get("data", {})
            .get("event", {})
            .get("phases", [])
        )

        return [phase["id"] for phase in sorted(phases, key=lambda x: x["phaseOrder"])]

    except (requests.exceptions.RequestException, requests.exceptions.JSONDecodeError) as error:
        print(f"Error fetching event data: {error}")
        return []

# ============================
# SLUG PARSING
# ============================

def parse_slug(slug_text: str) -> tuple[str | None, str | None]:

    match = re.search(r"(tournament/[^/]+)(/event/[^/]+)?", slug_text)

    if not match:
        return None, None
    
    tournament_slug = match.group(1)

    event_slug = match.group(1) + (match.group(2) or "")

    return event_slug, tournament_slug

# ============================
# SET PROCESSING
# ============================

def convert_sets(sets: list[dict], tournament_name: str) -> list[dict]:

    all_sets = []

    for current_set in sets:

        try:
            slots = current_set.get("slots", [])

            if not slots or len(slots) < 2:
                continue

            p1_entrant = slots[0].get("entrant")
            p2_entrant = slots[1].get("entrant")

            if not p1_entrant or not p2_entrant:
                continue

            p1_parts = p1_entrant.get("participants", [])
            p2_parts = p2_entrant.get("participants", [])

            p1_name = p1_entrant.get("name", "Unknown")
            p2_name = p2_entrant.get("name", "Unknown")

            p1_id = p1_parts[0]["player"]["id"]
            p2_id = p2_parts[0]["player"]["id"]

            if not p1_id or not p2_id:
                continue

            p1_standing = slots[0].get("standing", {})
            p2_standing = slots[1].get("standing", {})

            p1_score = p1_standing.get("stats", {}).get("score", {}).get("value", 0) if p1_standing else 0
            p2_score = p2_standing.get("stats", {}).get("score", {}).get("value", 0) if p2_standing else 0

            if p1_score == p2_score:
                continue

            winner = p1_name if (p1_score > p2_score) else p2_name

            raw_time = current_set.get("completedAt")

            if raw_time:
                date_str = datetime.fromtimestamp(raw_time).strftime('%Y-%m-%d') 
            else:
                date_str = "N/A"

            all_sets.append({
                "SetID": current_set["id"],
                "Timestamp": raw_time,
                "Tournament": tournament_name,
                "Date": date_str,
                "Player1ID": p1_id,
                "Player2ID": p2_id,
                "Player1": p1_name,
                "Player2": p2_name,
                "Player1Score": p1_score,
                "Player2Score": p2_score,
                "Winner": winner
            })

        except (KeyError, TypeError, IndexError):
            continue

    return all_sets

# =========================
# TOURNAMENT FILE
# =========================

def load_tournament_urls(path: str) -> list[str]:

    if not os.path.exists(path):
        raise FileNotFoundError(f"Tournament path not found: {path}")

    urls = []

    with open(path, "r", encoding="utf-8") as handle:

        for line in handle:

            url = (
                line
                .strip()
                .lower()
                .rstrip("/")
            )

            if url:
                urls.append(url)

    return urls

# =========================
# CSV OUTPUT
# =========================

def write_dataset(path: str, rows: list[dict]) -> None:

    if not rows:
        print("No sets to write")
        return

    output_directory = os.path.dirname(path)

    if output_directory:
        os.makedirs(output_directory, exist_ok=True)

    dataframe = pandas.DataFrame(rows)

    dataframe.to_csv(path, index=False)

    print(f"Wrote {len(dataframe):,} sets to {path}")

# =========================
# SCRAPER
# =========================

async def scrape_tournaments(tournament_files: list[str]) -> list[dict]:

    tournament_urls = []

    for tournament_file in tournament_files:
        urls = load_tournament_urls(tournament_file)
        tournament_urls.extend(urls)

    print(
        f"Loaded {len(urls)} tournaments from {tournament_file}"
    )

    tournament_urls = list(dict.fromkeys(tournament_urls))

    print()
    print(f"Loaded {len(tournament_urls)} unique tournaments/events total")

    all_rows = []

    async with aiohttp.ClientSession() as session:

        for tournament_url in tournament_urls:

            print()
            print("=" * 60)
            print(f"Processing: {tournament_url}")
            print("=" * 60)

            event_slug, tournament_slug = parse_slug(tournament_url)

            if event_slug is None or tournament_slug is None:
                print("Skipping: Invalid slug")
                continue

            tournament_name = fetch_tournament_name(tournament_slug)

            if not tournament_name:
                print("Skipping: could not find tournament name")
                continue

            print(f"Tournament: {tournament_name}")

            event_id = fetch_event_id(event_slug)

            if not event_id:
                print("Skipping: could not find event id")
                continue

            print(f"Event ID: {event_id}")

            phase_ids = fetch_event_data(event_id)

            if not phase_ids:
                print("Skipping: No phases found")
                continue

            print(f"Found {len(phase_ids)} phases")

            sets = await fetch_phase_data(session, phase_ids)

            converted_sets = convert_sets(sets, tournament_name)

            all_rows.extend(converted_sets)

            print(f"Successfully added {len(converted_sets)} sets")

            await asyncio.sleep(2)

    return all_rows

# =========================
# MAIN
# =========================

def main(argv: list[str] | None = None) -> int:

    parser = argparse.ArgumentParser(description="Scrape start.gg data into csv")

    parser.add_argument(
        "--tournaments",
        "-t",
        nargs="+",
        required=True,
    )

    parser.add_argument(
        "--output",
        "-o",
        required=True
    )

    args = parser.parse_args(argv)

    try:

        rows = asyncio.run(scrape_tournaments(args.tournaments))

        write_dataset(args.output, rows)

        return 0

    except(OSError, ValueError, requests.RequestException) as error:

        print(f"Error: {error}")

        return 1
    
if __name__ == "__main__":
    raise SystemExit(main())
