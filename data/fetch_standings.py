"""
fetch_standings.py
Pulls current standings from the MLB Stats API.
Returns a DataFrame with one row per team.
"""

import requests
import pandas as pd
from datetime import date
from utils.constants import MLB_API_BASE, TEAM_INFO, SEASON_YEAR


def fetch_standings() -> pd.DataFrame:
    """
    Fetch current standings for all 30 teams from the MLB Stats API.
    Returns a DataFrame with columns:
        team_id, name, abbr, division, league,
        wins, losses, win_pct, games_back, runs_scored, runs_allowed,
        run_differential, games_played
    """
    url = f"{MLB_API_BASE}/standings"
    params = {
        "leagueId": "103,104",   # AL=103, NL=104
        "season": SEASON_YEAR,
        "standingsTypes": "regularSeason",
        "hydrate": "team,record",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch standings: {e}")

    rows = []
    for record in data.get("records", []):
        division_name = record.get("division", {}).get("name", "Unknown")
        for tr in record.get("teamRecords", []):
            team_id = tr["team"]["id"]
            if team_id not in TEAM_INFO:
                continue

            name, abbr, div, league = TEAM_INFO[team_id]

            wins   = tr.get("wins", 0)
            losses = tr.get("losses", 0)
            gp     = wins + losses
            wp     = wins / gp if gp > 0 else 0.0

            # Games back — API returns string like "1.0" or "-" for leader
            gb_raw = tr.get("gamesBack", "0")
            try:
                gb = float(gb_raw)
            except (ValueError, TypeError):
                gb = 0.0

            # Wild card games back
            wc_gb_raw = tr.get("wildCardGamesBack", "0")
            try:
                wc_gb = float(wc_gb_raw)
            except (ValueError, TypeError):
                wc_gb = 0.0

            # Run totals — buried in split records
            rs = 0
            ra = 0
            league_record = tr.get("leagueRecord", {})
            runs_info = tr.get("runsScored", None)
            runs_allowed_info = tr.get("runsAllowed", None)

            # Try the records splits for RS/RA
            for split in tr.get("records", {}).get("splitRecords", []):
                pass  # not always populated here

            # Primary source for runs
            rs = tr.get("runsScored", 0) or 0
            ra = tr.get("runsAllowed", 0) or 0
            rd = rs - ra

            rows.append({
                "team_id":          team_id,
                "name":             name,
                "abbr":             abbr,
                "division":         div,
                "league":           league,
                "wins":             wins,
                "losses":           losses,
                "games_played":     gp,
                "win_pct":          round(wp, 4),
                "div_games_back":   gb,
                "wc_games_back":    wc_gb,
                "runs_scored":      rs,
                "runs_allowed":     ra,
                "run_differential": rd,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("Standings DataFrame is empty — API may have changed.")

    # ── Compute wild-card games back properly across both leagues ──────────────
    df = _compute_wc_games_back(df)

    return df.sort_values(["league", "division", "wins"], ascending=[True, True, False])


def _compute_wc_games_back(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each league, identify the 3 division winners and 3 wild card teams.
    Compute wc_games_back relative to the 3rd wild card team's win%.
    Teams already in as division winners get wc_gb = -999 (clinched).
    """
    result_frames = []
    for league in ["AL", "NL"]:
        lg = df[df["league"] == league].copy()

        # Best record per division = division leader
        div_leaders = lg.groupby("division")["win_pct"].idxmax()
        lg["div_leader"] = False
        lg.loc[div_leaders, "div_leader"] = True

        # Wild card pool = non-division leaders, sorted by win%
        wc_pool = lg[~lg["div_leader"]].sort_values("win_pct", ascending=False)

        if len(wc_pool) >= 3:
            wc_cutoff_pct = wc_pool.iloc[2]["win_pct"]
        elif len(wc_pool) > 0:
            wc_cutoff_pct = wc_pool.iloc[-1]["win_pct"]
        else:
            wc_cutoff_pct = 0.5

        # Games back from wild card = games needed to make up the gap
        # Approximation: (cutoff_wp - team_wp) * games_played
        def calc_wc_gb(row):
            if row["div_leader"]:
                return -5.0   # well inside playoff picture
            gp = max(row["games_played"], 1)
            gap = (wc_cutoff_pct - row["win_pct"]) * gp
            return round(gap, 1)

        lg["wc_games_back"] = lg.apply(calc_wc_gb, axis=1)
        result_frames.append(lg)

    return pd.concat(result_frames, ignore_index=True)


def fetch_team_runs(team_id: int) -> tuple[int, int]:
    """
    Fallback: fetch a single team's runs scored/allowed from the team endpoint.
    Returns (runs_scored, runs_allowed).
    """
    url = f"{MLB_API_BASE}/teams/{team_id}/stats"
    params = {"stats": "season", "group": "hitting,pitching", "season": SEASON_YEAR}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rs, ra = 0, 0
        for group in data.get("stats", []):
            for split in group.get("splits", []):
                stat = split.get("stat", {})
                if group.get("group", {}).get("displayName") == "hitting":
                    rs = stat.get("runs", 0)
                elif group.get("group", {}).get("displayName") == "pitching":
                    ra = stat.get("runs", 0)
        return rs, ra
    except Exception:
        return 0, 0
