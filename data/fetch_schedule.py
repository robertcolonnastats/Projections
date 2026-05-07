"""
fetch_schedule.py
Pulls the remaining schedule for all 30 teams from the MLB Stats API.
Returns a DataFrame of future games with home/away team IDs.
"""

import requests
import pandas as pd
from datetime import date, timedelta
from utils.constants import MLB_API_BASE, SEASON_YEAR, WORLD_SERIES_END_APPROX


def fetch_remaining_schedule(from_date: date | None = None) -> pd.DataFrame:
    """
    Fetch all remaining regular-season games from from_date through end of season.
    Returns DataFrame with columns:
        game_id, game_date, home_team_id, away_team_id, status
    """
    if from_date is None:
        from_date = date.today()

    end_date = date.fromisoformat(WORLD_SERIES_END_APPROX)
    if from_date > end_date:
        return pd.DataFrame(columns=["game_id", "game_date", "home_team_id", "away_team_id"])

    # MLB API limits schedule requests; chunk by month to be safe
    all_games = []
    chunk_start = from_date

    while chunk_start <= end_date:
        chunk_end = min(
            date(chunk_start.year, chunk_start.month, 1) + timedelta(days=31),
            end_date
        )
        # Snap to month end
        if chunk_end.month != chunk_start.month:
            chunk_end = date(chunk_start.year, chunk_start.month + 1, 1) - timedelta(days=1)

        games = _fetch_schedule_chunk(chunk_start, chunk_end)
        all_games.extend(games)
        chunk_start = chunk_end + timedelta(days=1)

    if not all_games:
        return pd.DataFrame(columns=["game_id", "game_date", "home_team_id", "away_team_id"])

    df = pd.DataFrame(all_games)
    df["game_date"] = pd.to_datetime(df["game_date"])
    df = df.drop_duplicates(subset="game_id")
    return df.sort_values("game_date").reset_index(drop=True)


def _fetch_schedule_chunk(start: date, end: date) -> list[dict]:
    """Fetch a single date-range chunk from the schedule API."""
    url = f"{MLB_API_BASE}/schedule"
    params = {
        "sportId": 1,
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "gameType": "R",          # regular season only
        "hydrate": "team",
        "season": SEASON_YEAR,
    }

    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Warning: schedule fetch failed for {start}–{end}: {e}")
        return []

    games = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            status = game.get("status", {}).get("abstractGameState", "")
            # Only include scheduled / in-progress / final
            home_id = game.get("teams", {}).get("home", {}).get("team", {}).get("id")
            away_id = game.get("teams", {}).get("away", {}).get("team", {}).get("id")
            if home_id and away_id:
                games.append({
                    "game_id":      game.get("gamePk"),
                    "game_date":    date_entry.get("date"),
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "status":       status,
                })

    return games


def get_remaining_games(schedule_df: pd.DataFrame) -> pd.DataFrame:
    """Filter schedule to only future (unplayed) games."""
    today = pd.Timestamp(date.today())
    return schedule_df[
        (schedule_df["game_date"] >= today) &
        (schedule_df["status"].isin(["Preview", "Scheduled", ""]))
    ].copy()


def compute_remaining_opponents(schedule_df: pd.DataFrame) -> dict[int, list[int]]:
    """
    Returns dict mapping team_id → list of opponent team_ids for remaining games.
    Used for strength-of-schedule calculations.
    """
    remaining = get_remaining_games(schedule_df)
    opponents: dict[int, list[int]] = {}

    for _, row in remaining.iterrows():
        h, a = row["home_team_id"], row["away_team_id"]
        opponents.setdefault(h, []).append(a)
        opponents.setdefault(a, []).append(h)

    return opponents
