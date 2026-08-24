import pandas
import requests
import re
import asyncio
import os
import aiohttp
import datetime
import time
from queries import (
    QUERY_TOURNAMENT_NAME,
    QUERY_EVENT_ID,
    QUERY_EVENT,
    QUERY_INIT_PHASE,
    QUERY_PHASES,
)

API_KEY = "a6345f8ee6d3390b8fc62b5d98091087"

new_data = {
    "Tournament": [],
    "Date": [],
    "Player1": [],
    "Player2": [],
    "Player1Score": [],
    "Player2Score": [],
    "Player1Characters": [],
    "Player2Characters": []
}

new_df = pandas.DataFrame(new_data)

csv_file_path = 'TricotSmashDataset.csv'

API_VERSION = "alpha"
URL = f"https://api.start.gg/gql/{API_VERSION}"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}
PER_PAGE = 25
SEED_CACHE = {}


async def fetch_phase_data(session, phase_ids):
    all_sets = []

    for phase_id in phase_ids:
        page = 1
        retry_delay = 2

        while True:
            try:
                async with session.post(
                    URL, headers=HEADERS, json={"query": QUERY_PHASES, "variables": {
                        "phaseId": phase_id, "page": page, "perPage": PER_PAGE}}
                ) as response:
                    if response.status == 429:
                        print(
                            f"Rate limit hit for sets. Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue

                    if response.status != 200:
                        print(
                            f"Error fetching sets data (Phase {phase_id}, Page {page}): {response.status}")
                        print(await response.text())
                        break

                    data = await response.json()
                    sets = data.get("data", {}).get(
                        "phase", {}).get("sets", {}).get("nodes", [])

                    if not sets:
                        break

                    all_sets.extend(sets)
                    page += 1
                    retry_delay = 2

            except Exception as e:
                print(f"Unexpected error: {e}")
                break

    return all_sets


def fetch_tournament_name(slug):
    try:
        response = requests.post(URL, headers=HEADERS, json={
                                 "query": QUERY_TOURNAMENT_NAME, "variables": {"slug": slug}})

        if response.status_code == 200:
            return response.json().get("data", {}).get("tournament", {}).get("name")
        elif response.status_code == 429:
            print("Rate limit hit on Tournament Name fetch. Waiting 30 seconds...")
            time.sleep(30)
            return None
        else:
            print(f"API Error {response.status_code} for {slug}")
            return None

    except requests.exceptions.JSONDecodeError:
        print(
            f"Warning: Received empty/invalid response for {slug}. Skipping...")
        return None


def fetch_event_id(slug):
    response = requests.post(URL, headers=HEADERS, json={
                             "query": QUERY_EVENT_ID, "variables": {"slug": slug}})
    data = response.json()
    return data.get("data", {}).get("event", {}).get("id")


def fetch_event_data(event_id):
    response = requests.post(URL, headers=HEADERS, json={
                             "query": QUERY_EVENT, "variables": {"eventId": event_id}})

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        return []

    data = response.json()
    if "errors" in data:
        print("Error:", data["errors"])
        return []

    phases = data.get("data", {}).get("event", {}).get("phases", [])

    return [phase["id"] for phase in sorted(phases, key=lambda x: x["phaseOrder"])]


def parse_slug(slug_text):
    match = re.search(r"(tournament/[^/]+)(/event/[^/]+)?", slug_text)
    if not match:
        return None, None
    tournament_slug = match.group(1)
    event_slug = match.group(1) + (match.group(2) or "")
    return event_slug, tournament_slug


def add_data_to_dataset(sets, tournament_name):
    all_sets_list = []

    for s in sets:
        try:
            slots = s.get("slots", [])
            if not slots or len(slots) < 2:
                continue

            # Extract entrants safely
            p1_ent = slots[0].get("entrant")
            p2_ent = slots[1].get("entrant")

            # Skip if either entrant is missing (common in unplayed brackets)
            if not p1_ent or not p2_ent:
                continue

            # FIX: Handle 'participants' as a list
            p1_parts = p1_ent.get("participants", [])
            p2_parts = p2_ent.get("participants", [])

            p1_name = p1_ent.get("name", "Unknown")
            p2_name = p2_ent.get("name", "Unknown")

            # Correct path for Player IDs
            p1_id = p1_parts[0]["player"]["id"] if p1_parts else "N/A"
            p2_id = p2_parts[0]["player"]["id"] if p2_parts else "N/A"

            # Capture Scores
            p1_standing = slots[0].get("standing", {})
            p2_standing = slots[1].get("standing", {})

            # Navigate the nested stats object safely
            p1_score = p1_standing.get("stats", {}).get(
                "score", {}).get("value", 0) if p1_standing else 0
            p2_score = p2_standing.get("stats", {}).get(
                "score", {}).get("value", 0) if p2_standing else 0

            # Winner logic (placement 1 = winner)
            winner = p1_name if (p1_standing and p1_standing.get(
                "placement") == 1) else p2_name

            raw_time = s.get("completedAt")
            date_str = datetime.datetime.fromtimestamp(
                raw_time).strftime('%Y-%m-%d') if raw_time else "N/A"

            all_sets_list.append({
                "SetID": s["id"],
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
        except (KeyError, TypeError, IndexError) as e:
            continue

    if all_sets_list:
        sets_df = pandas.DataFrame(all_sets_list)
        file_path = os.path.join(os.getcwd(), "sets_dataset.csv")
        file_exists = os.path.isfile(file_path)
        sets_df.to_csv(file_path, mode='a', index=False,
                       header=not file_exists)
        print(
            f"--- SUCCESS: Added {len(all_sets_list)} sets to {file_path} ---")


async def __main__():
    file_path = "tournamentsKnox.txt"

    if not os.path.exists(file_path):
        print(
            f"Error: {file_path} not found. Create it with one URL per line.")
        return

    with open(file_path, "r") as f:
        for line in f:
            tournament_url = line.strip().lower().rstrip('/')

            if not tournament_url:
                continue

            print(f"\nProcessing: {tournament_url}")
            event_slug, tournament_slug = parse_slug(tournament_url)

            if event_slug is None or tournament_slug is None:
                print(f"Skipping: Invalid slug format for {tournament_url}")
                continue

            tournament_name = fetch_tournament_name(tournament_slug)
            event_id = fetch_event_id(event_slug)

            if event_id:
                phase_ids = fetch_event_data(event_id)
                async with aiohttp.ClientSession() as session:
                    sets = await fetch_phase_data(session, phase_ids)
                    add_data_to_dataset(sets, tournament_name)
                    print(
                        f"Successfully added {len(sets)} sets for {tournament_name}")

            await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(__main__())
    except KeyboardInterrupt:
        print("\nScraper stopped by user.")
