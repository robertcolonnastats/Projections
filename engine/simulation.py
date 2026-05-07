"""
simulation.py
Vectorized Monte Carlo simulation of the remaining MLB season.
10,000 iterations using numpy for speed and Streamlit Cloud stability.
Zero-sum wins guaranteed via game-level simulation.
"""

import numpy as np
import pandas as pd
from utils.constants import N_SIMULATIONS, RANDOM_SEED, DIVISIONS


def log5(wp_a: float, wp_b: float) -> float:
    """
    Bill James Log5 formula.
    Returns win probability for team A when facing team B,
    assuming a league-average opponent wins 50% of games.
    """
    if wp_a + wp_b == 0:
        return 0.5
    return (wp_a - wp_a * wp_b) / (wp_a + wp_b - 2 * wp_a * wp_b + 1e-9)


def run_simulation(master_df: pd.DataFrame, schedule_df: pd.DataFrame) -> dict:
    """
    Run N_SIMULATIONS Monte Carlo simulations of the remaining season.

    Parameters
    ----------
    master_df   : DataFrame with team records + adj_win_pct per team
    schedule_df : DataFrame of remaining games (home_team_id, away_team_id)

    Returns
    -------
    dict with keys:
        division_odds   : {team_id: float}  probability of winning division
        playoff_odds    : {team_id: float}  probability of making playoffs
        ws_odds         : {team_id: float}  probability of winning World Series
        proj_wins       : {team_id: float}  mean projected final wins
        proj_wins_std   : {team_id: float}  std dev of final wins
        pre_deadline_division_odds  : same as above but without deadline adjustments
        pre_deadline_playoff_odds   : same
        pre_deadline_ws_odds        : same
    """
    rng = np.random.default_rng(RANDOM_SEED)

    team_ids = master_df["team_id"].tolist()
    n_teams  = len(team_ids)
    tid_to_idx = {tid: i for i, tid in enumerate(team_ids)}

    # Current wins/losses
    current_wins   = master_df.set_index("team_id")["wins"].to_dict()
    current_losses = master_df.set_index("team_id")["losses"].to_dict()
    games_played   = master_df.set_index("team_id")["games_played"].to_dict()

    # Adjusted win% (with deadline adjustments)
    adj_wp = master_df.set_index("team_id")["adj_win_pct"].to_dict()

    # Unadjusted win% (blended, no deadline penalty) for before/after comparison
    base_wp = master_df.set_index("team_id")["blended_win_pct"].to_dict()

    # Filter to remaining (unplayed) games
    from data.fetch_schedule import get_remaining_games
    remaining = get_remaining_games(schedule_df)

    if remaining.empty:
        # Season is over — return actuals
        return _season_complete_results(master_df)

    home_ids = remaining["home_team_id"].values.astype(int)
    away_ids = remaining["away_team_id"].values.astype(int)
    n_games  = len(home_ids)

    # Pre-compute Log5 probabilities for each game
    adj_probs  = np.array([
        log5(adj_wp.get(h, 0.5), adj_wp.get(a, 0.5))
        for h, a in zip(home_ids, away_ids)
    ])

    base_probs = np.array([
        log5(base_wp.get(h, 0.5), base_wp.get(a, 0.5))
        for h, a in zip(home_ids, away_ids)
    ])

    # Maps for fast indexing in simulation
    home_idx = np.array([tid_to_idx.get(int(h), -1) for h in home_ids])
    away_idx = np.array([tid_to_idx.get(int(a), -1) for a in away_ids])

    # Filter out games where teams aren't in our master list
    valid_mask = (home_idx >= 0) & (away_idx >= 0)
    home_idx   = home_idx[valid_mask]
    away_idx   = away_idx[valid_mask]
    adj_probs  = adj_probs[valid_mask]
    base_probs = base_probs[valid_mask]
    n_games    = int(valid_mask.sum())

    # ── Simulation arrays ─────────────────────────────────────────────────────
    init_wins = np.array([current_wins.get(tid, 0) for tid in team_ids], dtype=float)

    # Run adjusted simulations
    adj_results  = _simulate_batch(rng, init_wins, home_idx, away_idx, adj_probs,  n_teams, n_games)
    # Run pre-deadline simulations (no deadline adjustment)
    base_results = _simulate_batch(rng, init_wins, home_idx, away_idx, base_probs, n_teams, n_games)

    # ── Build playoff odds from results ───────────────────────────────────────
    team_info_df = master_df[["team_id", "division", "league"]].copy()

    adj_odds  = _compute_odds(adj_results,  team_ids, team_info_df)
    base_odds = _compute_odds(base_results, team_ids, team_info_df)

    # Simulate World Series from playoff-qualified teams
    adj_ws  = _simulate_world_series(adj_results,  adj_odds["playoff"],  adj_wp,  team_ids, team_info_df, rng)
    base_ws = _simulate_world_series(base_results, base_odds["playoff"], base_wp, team_ids, team_info_df, rng)

    proj_wins_arr = adj_results.mean(axis=0)
    proj_wins_std = adj_results.std(axis=0)

    return {
        "division_odds":               {tid: float(adj_odds["division"][i])  for i, tid in enumerate(team_ids)},
        "playoff_odds":                {tid: float(adj_odds["playoff"][i])   for i, tid in enumerate(team_ids)},
        "ws_odds":                     {tid: float(adj_ws[i])                for i, tid in enumerate(team_ids)},
        "proj_wins":                   {tid: float(proj_wins_arr[i])         for i, tid in enumerate(team_ids)},
        "proj_wins_std":               {tid: float(proj_wins_std[i])         for i, tid in enumerate(team_ids)},
        "pre_deadline_division_odds":  {tid: float(base_odds["division"][i]) for i, tid in enumerate(team_ids)},
        "pre_deadline_playoff_odds":   {tid: float(base_odds["playoff"][i])  for i, tid in enumerate(team_ids)},
        "pre_deadline_ws_odds":        {tid: float(base_ws[i])               for i, tid in enumerate(team_ids)},
    }


def _simulate_batch(
    rng: np.random.Generator,
    init_wins: np.ndarray,
    home_idx: np.ndarray,
    away_idx: np.ndarray,
    probs: np.ndarray,
    n_teams: int,
    n_games: int,
) -> np.ndarray:
    """
    Vectorized simulation of N_SIMULATIONS seasons.
    Returns array of shape (N_SIMULATIONS, n_teams) with final win totals.
    """
    N = N_SIMULATIONS

    # Shape: (N, n_teams) — start everyone at current wins
    final_wins = np.tile(init_wins, (N, 1)).astype(float)

    if n_games == 0:
        return final_wins

    # Simulate all N seasons × n_games at once
    # Shape: (N, n_games)
    rand_vals   = rng.random((N, n_games))
    home_wins   = rand_vals < probs[np.newaxis, :]   # True = home wins

    # Add wins to each team across all simulations
    # np.add.at is not vectorized; use bincount approach per simulation
    # For speed: accumulate using matrix ops
    for g in range(n_games):
        h = home_idx[g]
        a = away_idx[g]
        # home_wins[:, g] is (N,) bool
        final_wins[:, h] += home_wins[:, g].astype(float)
        final_wins[:, a] += (~home_wins[:, g]).astype(float)

    return final_wins


def _compute_odds(
    results: np.ndarray,
    team_ids: list,
    team_info_df: pd.DataFrame,
) -> dict:
    """
    From simulation results array (N_SIM × n_teams), compute division and playoff odds.
    Returns dict with 'division' and 'playoff' arrays (length n_teams).
    """
    N, n_teams = results.shape
    n_sims = N

    info = team_info_df.set_index("team_id")
    divisions_list = team_info_df["division"].unique()

    div_wins_count  = np.zeros(n_teams)
    playoff_count   = np.zeros(n_teams)

    tid_to_idx = {tid: i for i, tid in enumerate(team_ids)}

    # Per simulation, determine division winners and WC teams
    for sim_idx in range(n_sims):
        sim_wins = results[sim_idx]   # (n_teams,)

        div_winner_idxs = set()

        # Division winners
        for div in divisions_list:
            mask = [i for i, tid in enumerate(team_ids)
                    if info.loc[int(tid), "division"] == div]
            if not mask:
                continue
            best_idx = mask[np.argmax(sim_wins[mask])]
            div_winner_idxs.add(best_idx)
            div_wins_count[best_idx] += 1

        # Wild card per league (top 3 non-division-winners)
        for league in ["AL", "NL"]:
            league_idxs = [i for i, tid in enumerate(team_ids)
                           if info.loc[int(tid), "league"] == league]
            non_div_idxs = [i for i in league_idxs if i not in div_winner_idxs]
            if not non_div_idxs:
                continue
            wc_wins = sim_wins[non_div_idxs]
            top3 = np.argsort(wc_wins)[-3:]
            for rank_idx in top3:
                playoff_count[non_div_idxs[rank_idx]] += 1

        # Division winners also in playoffs
        for idx in div_winner_idxs:
            playoff_count[idx] += 1

    return {
        "division": div_wins_count / n_sims,
        "playoff":  playoff_count  / n_sims,
    }


def _simulate_world_series(
    results: np.ndarray,
    playoff_odds: np.ndarray,
    win_pct_map: dict,
    team_ids: list,
    team_info_df: pd.DataFrame,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Simplified WS simulation: for each simulation, pick 12 playoff teams,
    then run single-elimination bracket weighted by win%.
    Returns array of WS win probabilities per team.
    """
    N = N_SIMULATIONS
    n_teams = len(team_ids)
    ws_count = np.zeros(n_teams)

    tid_to_idx = {tid: i for i, tid in enumerate(team_ids)}
    info = team_info_df.set_index("team_id")
    wp_arr = np.array([win_pct_map.get(tid, 0.5) for tid in team_ids])

    for sim_idx in range(N):
        sim_wins = results[sim_idx]
        playoff_teams = _get_playoff_teams(sim_wins, team_ids, info)
        if len(playoff_teams) < 2:
            continue

        # Simple bracket: pair teams, winner advances, repeat
        remaining = list(playoff_teams)
        while len(remaining) > 1:
            next_round = []
            # Shuffle for bracket randomness
            rng.shuffle(remaining)
            for i in range(0, len(remaining) - 1, 2):
                t1, t2 = remaining[i], remaining[i + 1]
                wp1 = wp_arr[tid_to_idx.get(t1, 0)]
                wp2 = wp_arr[tid_to_idx.get(t2, 0)]
                p = log5(wp1, wp2)
                winner = t1 if rng.random() < p else t2
                next_round.append(winner)
            if len(remaining) % 2 == 1:
                next_round.append(remaining[-1])   # bye
            remaining = next_round

        if remaining:
            champion = remaining[0]
            idx = tid_to_idx.get(champion)
            if idx is not None:
                ws_count[idx] += 1

    return ws_count / N


def _get_playoff_teams(sim_wins, team_ids, info) -> list:
    """Get the 12 playoff teams for a single simulation."""
    playoff = set()
    leagues = ["AL", "NL"]

    for league in leagues:
        lg_idxs = [i for i, tid in enumerate(team_ids)
                   if info.loc[int(tid), "league"] == league]
        divisions = info[info["league"] == league]["division"].unique()

        div_winner_idxs = set()
        for div in divisions:
            div_idxs = [i for i in lg_idxs
                        if info.loc[int(team_ids[i]), "division"] == div]
            if div_idxs:
                best = div_idxs[int(np.argmax(sim_wins[div_idxs]))]
                div_winner_idxs.add(best)
                playoff.add(int(team_ids[best]))

        non_div = [i for i in lg_idxs if i not in div_winner_idxs]
        if non_div:
            top3_rel = np.argsort(sim_wins[non_div])[-3:]
            for r in top3_rel:
                playoff.add(int(team_ids[non_div[r]]))

    return list(playoff)


def _season_complete_results(master_df: pd.DataFrame) -> dict:
    """Return results based on actual standings when season is over."""
    team_ids = master_df["team_id"].tolist()
    return {
        "division_odds":              {tid: 0.0 for tid in team_ids},
        "playoff_odds":               {tid: 0.0 for tid in team_ids},
        "ws_odds":                    {tid: 0.0 for tid in team_ids},
        "proj_wins":                  master_df.set_index("team_id")["wins"].to_dict(),
        "proj_wins_std":              {tid: 0.0 for tid in team_ids},
        "pre_deadline_division_odds": {tid: 0.0 for tid in team_ids},
        "pre_deadline_playoff_odds":  {tid: 0.0 for tid in team_ids},
        "pre_deadline_ws_odds":       {tid: 0.0 for tid in team_ids},
    }
