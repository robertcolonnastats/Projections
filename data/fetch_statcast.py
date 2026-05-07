"""
fetch_statcast.py
Pulls batting and pitching stats via pybaseball (Baseball Savant + FanGraphs).
Builds weighted team-level offensive and pitching projections.
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

from utils.constants import (
    SEASON_YEAR,
    WEIGHT_CURRENT_SEASON,
    WEIGHT_LAST_YEAR,
    WEIGHT_TWO_YEARS_AGO,
    TEAM_INFO,
)

# Lazy import pybaseball to avoid import errors if not installed
try:
    import pybaseball as pb
    pb.cache.enable()
    PYBASEBALL_AVAILABLE = True
except ImportError:
    PYBASEBALL_AVAILABLE = False


# ── Team abbreviation mapping (pybaseball uses FanGraphs team names) ───────────
FG_TEAM_MAP = {
    "Angels":      108, "Diamondbacks": 109, "Orioles":   110,
    "Red Sox":     111, "Cubs":         112, "Reds":      113,
    "Guardians":   114, "Rockies":      115, "Tigers":    116,
    "Astros":      117, "Royals":       118, "Dodgers":   119,
    "Nationals":   120, "Mets":         121, "Athletics": 133,
    "Pirates":     134, "Padres":       135, "Mariners":  136,
    "Giants":      137, "Cardinals":    138, "Rays":      139,
    "Rangers":     140, "Blue Jays":    141, "Twins":     142,
    "Phillies":    143, "Braves":       144, "White Sox": 145,
    "Marlins":     146, "Yankees":      147, "Brewers":   158,
}

MIN_PA_BATTER  = 100   # minimum plate appearances to include in team batting avg
MIN_IP_PITCHER = 20    # minimum innings pitched


def fetch_team_projections() -> pd.DataFrame:
    """
    Returns a DataFrame with one row per team_id containing:
        team_id, proj_win_pct, proj_runs_per_game, proj_ra_per_game
    These are weighted blends of current + last 2 seasons.
    Falls back to league-average estimates if pybaseball fails.
    """
    if not PYBASEBALL_AVAILABLE:
        return _fallback_projections()

    try:
        batting_proj   = _build_batting_projections()
        pitching_proj  = _build_pitching_projections()
        return _combine_projections(batting_proj, pitching_proj)
    except Exception as e:
        print(f"Warning: Statcast projection failed ({e}), using fallback.")
        return _fallback_projections()


def _fetch_batting_season(year: int) -> pd.DataFrame:
    """Fetch FanGraphs batting stats for a given year."""
    try:
        df = pb.batting_stats(year, qual=MIN_PA_BATTER)
        df["season"] = year
        return df
    except Exception:
        return pd.DataFrame()


def _fetch_pitching_season(year: int) -> pd.DataFrame:
    """Fetch FanGraphs pitching stats for a given year."""
    try:
        df = pb.pitching_stats(year, qual=MIN_IP_PITCHER)
        df["season"] = year
        return df
    except Exception:
        return pd.DataFrame()


def _build_batting_projections() -> pd.DataFrame:
    """
    Weighted team wRC+ and OBP across 3 seasons.
    Returns DataFrame: team_id, weighted_wrc_plus, weighted_obp
    """
    seasons = {
        SEASON_YEAR:     WEIGHT_CURRENT_SEASON,
        SEASON_YEAR - 1: WEIGHT_LAST_YEAR,
        SEASON_YEAR - 2: WEIGHT_TWO_YEARS_AGO,
    }

    frames = []
    for yr, weight in seasons.items():
        df = _fetch_batting_season(yr)
        if df.empty:
            continue

        # Normalize team names to team_id
        df["team_id"] = df["Team"].map(FG_TEAM_MAP)
        df = df.dropna(subset=["team_id"])
        df["team_id"] = df["team_id"].astype(int)

        # Weight by PA within season, then apply season weight
        if "PA" not in df.columns:
            df["PA"] = 400  # fallback

        team_stats = df.groupby("team_id").apply(
            lambda g: pd.Series({
                "wrc_plus": np.average(
                    g["wRC+"].fillna(100),
                    weights=g["PA"].fillna(1)
                ) if "wRC+" in g.columns else 100.0,
                "obp": np.average(
                    g["OBP"].fillna(0.320),
                    weights=g["PA"].fillna(1)
                ) if "OBP" in g.columns else 0.320,
            })
        ).reset_index()

        team_stats["weight"] = weight
        team_stats["season"] = yr
        frames.append(team_stats)

    if not frames:
        return _fallback_batting()

    combined = pd.concat(frames, ignore_index=True)

    # Weighted average across seasons
    result = combined.groupby("team_id").apply(
        lambda g: pd.Series({
            "weighted_wrc_plus": np.average(g["wrc_plus"], weights=g["weight"]),
            "weighted_obp":      np.average(g["obp"],      weights=g["weight"]),
        })
    ).reset_index()

    return result


def _build_pitching_projections() -> pd.DataFrame:
    """
    Weighted team FIP and ERA across 3 seasons.
    We use FIP as primary (holds pitchers accountable for actual HR)
    and blend in ERA for pitchers with large sample sizes.
    Returns DataFrame: team_id, weighted_fip, weighted_era
    """
    seasons = {
        SEASON_YEAR:     WEIGHT_CURRENT_SEASON,
        SEASON_YEAR - 1: WEIGHT_LAST_YEAR,
        SEASON_YEAR - 2: WEIGHT_TWO_YEARS_AGO,
    }

    frames = []
    for yr, weight in seasons.items():
        df = _fetch_pitching_season(yr)
        if df.empty:
            continue

        df["team_id"] = df["Team"].map(FG_TEAM_MAP)
        df = df.dropna(subset=["team_id"])
        df["team_id"] = df["team_id"].astype(int)

        if "IP" not in df.columns:
            df["IP"] = 50.0

        team_stats = df.groupby("team_id").apply(
            lambda g: pd.Series({
                "fip": np.average(
                    g["FIP"].fillna(4.00).clip(2.0, 7.0),
                    weights=g["IP"].fillna(1)
                ) if "FIP" in g.columns else 4.00,
                "era": np.average(
                    g["ERA"].fillna(4.20).clip(1.5, 8.0),
                    weights=g["IP"].fillna(1)
                ) if "ERA" in g.columns else 4.20,
            })
        ).reset_index()

        # Blend FIP (70%) with ERA (30%) per your preference — not xFIP
        team_stats["blended_pitching"] = (
            team_stats["fip"] * 0.70 +
            team_stats["era"] * 0.30
        )

        team_stats["weight"] = weight
        team_stats["season"] = yr
        frames.append(team_stats)

    if not frames:
        return _fallback_pitching()

    combined = pd.concat(frames, ignore_index=True)

    result = combined.groupby("team_id").apply(
        lambda g: pd.Series({
            "weighted_fip":       np.average(g["fip"],             weights=g["weight"]),
            "weighted_era":       np.average(g["era"],             weights=g["weight"]),
            "weighted_pitching":  np.average(g["blended_pitching"],weights=g["weight"]),
        })
    ).reset_index()

    return result


def _combine_projections(batting: pd.DataFrame, pitching: pd.DataFrame) -> pd.DataFrame:
    """
    Combine batting and pitching projections into run-scoring/prevention estimates,
    then convert to projected win%.
    """
    all_team_ids = list(TEAM_INFO.keys())

    # Ensure all teams present
    bat = batting.set_index("team_id").reindex(all_team_ids)
    pit = pitching.set_index("team_id").reindex(all_team_ids)

    # League averages for fill
    avg_wrc   = bat["weighted_wrc_plus"].mean() if not bat.empty else 100.0
    avg_fip   = pit["weighted_pitching"].mean()  if not pit.empty else 4.10

    bat = bat.fillna({"weighted_wrc_plus": avg_wrc, "weighted_obp": 0.320})
    pit = pit.fillna({"weighted_fip": avg_fip, "weighted_era": 4.20, "weighted_pitching": avg_fip})

    # Convert wRC+ → runs per game (league avg ~4.5 R/G, scaled by wRC+/100)
    LEAGUE_AVG_RPG = 4.50
    proj_rpg = (bat["weighted_wrc_plus"] / 100.0) * LEAGUE_AVG_RPG

    # Convert FIP → runs allowed per game
    # FIP ≈ ERA in the aggregate; scale to runs (not earned runs) with ~1.08 factor
    proj_rapg = pit["weighted_pitching"] * (LEAGUE_AVG_RPG / 4.10)

    # Clip to reasonable range
    proj_rpg  = proj_rpg.clip(2.5, 7.5)
    proj_rapg = proj_rapg.clip(2.5, 7.5)

    # Pythagorean win% from projected R/G
    from utils.constants import PYTHAG_EXPONENT
    exp = PYTHAG_EXPONENT
    proj_wp = proj_rpg ** exp / (proj_rpg ** exp + proj_rapg ** exp)

    result = pd.DataFrame({
        "team_id":           all_team_ids,
        "proj_runs_per_game": proj_rpg.values,
        "proj_ra_per_game":   proj_rapg.values,
        "proj_win_pct":       proj_wp.values,
    })

    return result


def _fallback_projections() -> pd.DataFrame:
    """
    Return league-average projections for all teams when API data unavailable.
    This ensures the app never crashes due to data fetch failures.
    """
    rows = []
    for tid in TEAM_INFO.keys():
        rows.append({
            "team_id":            tid,
            "proj_runs_per_game": 4.50,
            "proj_ra_per_game":   4.50,
            "proj_win_pct":       0.500,
        })
    return pd.DataFrame(rows)


def _fallback_batting() -> pd.DataFrame:
    rows = [{"team_id": tid, "weighted_wrc_plus": 100.0, "weighted_obp": 0.320}
            for tid in TEAM_INFO.keys()]
    return pd.DataFrame(rows)


def _fallback_pitching() -> pd.DataFrame:
    rows = [{"team_id": tid, "weighted_fip": 4.00, "weighted_era": 4.20, "weighted_pitching": 4.06}
            for tid in TEAM_INFO.keys()]
    return pd.DataFrame(rows)
