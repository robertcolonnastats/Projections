"""
projections.py
Combines real standings data with Statcast projections to build
each team's "true talent" win%, then blends with Pythagorean win%.
"""

import pandas as pd
import numpy as np
from utils.constants import PYTHAG_EXPONENT


def build_master_projections(
    standings_df: pd.DataFrame,
    statcast_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merges standings with Statcast projections.
    Produces a single master DataFrame with all columns needed for simulation.

    Key output columns:
        team_id, name, abbr, division, league,
        wins, losses, games_played, win_pct,
        pythag_win_pct, proj_win_pct (statcast),
        blended_win_pct (main input to sim),
        wc_games_back, run_differential, rd_per_162,
        tier, tier_label, base_adj, final_adj
    """
    df = standings_df.copy()

    # Merge statcast projections
    df = df.merge(
        statcast_df[["team_id", "proj_win_pct", "proj_runs_per_game", "proj_ra_per_game"]],
        on="team_id",
        how="left",
    )

    # Fallback: if statcast missing, use current win_pct
    df["proj_win_pct"] = df["proj_win_pct"].fillna(df["win_pct"]).fillna(0.500)

    # Blend: 50% Statcast projection + 50% Pythagorean win%
    # (Pythagorean already computed by buyer_seller engine — handle both cases)
    if "pythag_win_pct" not in df.columns:
        df["pythag_win_pct"] = df.apply(
            lambda r: _pythag(r["runs_scored"], r["runs_allowed"]), axis=1
        )

    # The "blended_win_pct" is the pre-deadline true talent estimate
    # Weight shifts toward Statcast as season progresses (more data)
    gp_weight = (df["games_played"] / 162.0).clip(0.0, 1.0)
    statcast_weight = 0.50 + gp_weight * 0.20   # 50% early → 70% late season
    pythag_weight   = 1.0 - statcast_weight

    df["blended_win_pct"] = (
        df["proj_win_pct"] * statcast_weight +
        df["pythag_win_pct"] * pythag_weight
    ).clip(0.20, 0.80)

    # Games remaining
    df["games_remaining"] = 162 - df["games_played"]
    df["games_remaining"] = df["games_remaining"].clip(0, 162)

    return df


def project_final_record(df: pd.DataFrame, adjusted_win_pct_series: pd.Series) -> pd.DataFrame:
    """
    Project final wins for each team using their adjusted win% over remaining games.
    Returns df with added columns: proj_final_wins, proj_final_losses.
    """
    df = df.copy()
    df["adj_win_pct"] = adjusted_win_pct_series.values

    df["proj_final_wins"] = (
        df["wins"] + df["adj_win_pct"] * df["games_remaining"]
    ).round(1)

    df["proj_final_losses"] = (
        df["losses"] + (1 - df["adj_win_pct"]) * df["games_remaining"]
    ).round(1)

    return df


def _pythag(rs: float, ra: float) -> float:
    if rs <= 0 or ra <= 0:
        return 0.500
    exp = PYTHAG_EXPONENT
    return rs ** exp / (rs ** exp + ra ** exp)
