"""
schedule_strength.py
Computes remaining strength of schedule for each team
based on opponents' adjusted win percentages.
"""

import pandas as pd
import numpy as np


def compute_sos(
    master_df: pd.DataFrame,
    remaining_opponents: dict[int, list[int]],
) -> pd.DataFrame:
    """
    Computes strength of schedule (SoS) for each team's remaining games.

    SoS = average adjusted win% of remaining opponents.
    A SoS of 0.520 means the team faces opponents who win 52% of games on average.

    Returns master_df with added columns:
        sos_raw         – average opponent adj_win_pct
        sos_rank        – rank among 30 teams (1 = hardest schedule)
        sos_label       – 'Easy' | 'Average' | 'Hard'
        games_vs_playoff – estimated games vs current playoff teams
    """
    df = master_df.copy()

    # Build lookup: team_id → adj_win_pct
    win_pct_map = df.set_index("team_id")["adj_win_pct"].to_dict()

    sos_values = {}
    for tid in df["team_id"]:
        opponents = remaining_opponents.get(int(tid), [])
        if not opponents:
            sos_values[tid] = 0.500
            continue
        opp_wp = [win_pct_map.get(int(o), 0.500) for o in opponents]
        sos_values[tid] = np.mean(opp_wp)

    df["sos_raw"] = df["team_id"].map(sos_values).fillna(0.500)

    # Rank (1 = hardest)
    df["sos_rank"] = df["sos_raw"].rank(ascending=False, method="min").astype(int)

    # Label
    p33 = df["sos_raw"].quantile(0.33)
    p67 = df["sos_raw"].quantile(0.67)
    def _sos_label(v):
        if v <= p33: return "Easy"
        elif v <= p67: return "Average"
        else: return "Hard"
    df["sos_label"] = df["sos_raw"].apply(_sos_label)

    # Games vs current playoff teams
    playoff_ids = _get_current_playoff_teams(df)
    games_vs_playoff = {}
    for tid in df["team_id"]:
        opponents = remaining_opponents.get(int(tid), [])
        gvp = sum(1 for o in opponents if int(o) in playoff_ids)
        games_vs_playoff[tid] = gvp

    df["games_vs_playoff"] = df["team_id"].map(games_vs_playoff).fillna(0).astype(int)

    return df


def _get_current_playoff_teams(df: pd.DataFrame) -> set[int]:
    """
    Returns set of team_ids currently in playoff position
    (3 division leaders + 3 WC per league = 12 teams).
    """
    playoff_ids = set()

    for league in ["AL", "NL"]:
        lg = df[df["league"] == league].copy()

        # Top team per division
        for div in lg["division"].unique():
            div_teams = lg[lg["division"] == div].sort_values("win_pct", ascending=False)
            if not div_teams.empty:
                playoff_ids.add(int(div_teams.iloc[0]["team_id"]))

        # Top 3 wild card (non-division leaders)
        div_leaders = set()
        for div in lg["division"].unique():
            div_teams = lg[lg["division"] == div].sort_values("win_pct", ascending=False)
            if not div_teams.empty:
                div_leaders.add(int(div_teams.iloc[0]["team_id"]))

        wc_teams = lg[~lg["team_id"].isin(div_leaders)].sort_values("win_pct", ascending=False)
        for _, row in wc_teams.head(3).iterrows():
            playoff_ids.add(int(row["team_id"]))

    return playoff_ids
