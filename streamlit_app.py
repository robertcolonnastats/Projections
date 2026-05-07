"""
app.py
MLB Season Projections — Streamlit entry point.
Handles data loading, caching, simulation orchestration, and tab rendering.
"""

import streamlit as st
import pandas as pd
import json
import traceback
from datetime import date

# ── Page config (must be first Streamlit call) ─────────────────────────────────
st.set_page_config(
    page_title="MLB Season Projections",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Imports ────────────────────────────────────────────────────────────────────
from utils.constants import SEASON_YEAR, WORLD_SERIES_END_APPROX, OPENING_DAY
from data.cache_manager import (
    load_cache, save_cache, is_cache_valid,
    dataframe_to_cache, cache_to_dataframe,
    get_last_updated, get_season_state, get_deadline_ramp_factor,
)
from data.fetch_standings import fetch_standings
from data.fetch_schedule  import fetch_remaining_schedule, compute_remaining_opponents
from data.fetch_statcast  import fetch_team_projections
from engine.buyer_seller  import compute_buyer_seller_scores, apply_ramp, get_adjusted_win_pct
from engine.projections   import build_master_projections
from engine.schedule_strength import compute_sos
from engine.simulation    import run_simulation
from ui.tab_projections   import render_projections_tab
from ui.tab_deadline      import render_deadline_tab
from ui.tab_team          import render_team_tab
from ui.tab_methodology   import render_methodology_tab


# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main .block-container { max-width: 1400px; padding-top: 1rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 20px;
        border-radius: 6px 6px 0 0;
        font-weight: 500;
    }
    .metric-label { font-size: 0.85rem !important; }
    div[data-testid="stMetricDelta"] { font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)


# ── Data loading with caching ─────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def load_all_data() -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """
    Load standings, run simulation, return master_df and sim_results.
    Cached for 1 hour; real expiry managed by disk cache at midnight EST.
    Returns (master_df, sim_results, schedule_df)
    """
    season_state = get_season_state()

    # ── Offseason: load frozen cache ───────────────────────────────────────────
    if season_state == "offseason":
        cached = load_cache("data")
        if cached:
            master_df = cache_to_dataframe(cached["master"])
            sim_results = cached.get("sim_results", _empty_sim_results(master_df))
            schedule_df = pd.DataFrame(columns=["game_id","game_date","home_team_id","away_team_id","status"])
            return master_df, sim_results, schedule_df

    # ── Try disk cache first ───────────────────────────────────────────────────
    if is_cache_valid("data"):
        cached = load_cache("data")
        if cached:
            master_df   = cache_to_dataframe(cached["master"])
            sim_results = cached.get("sim_results", {})
            schedule_df = cache_to_dataframe(cached.get("schedule", []))
            if not master_df.empty and sim_results:
                return master_df, sim_results, schedule_df

    # ── Fresh data pull ────────────────────────────────────────────────────────
    with st.spinner("📡 Fetching current standings..."):
        standings_df = fetch_standings()

    with st.spinner("📅 Loading schedule..."):
        schedule_df = fetch_remaining_schedule()

    with st.spinner("⚾ Pulling Statcast projections..."):
        statcast_df = fetch_team_projections()

    # Build projections
    master_df = build_master_projections(standings_df, statcast_df)

    # Compute buyer/seller scores
    master_df = compute_buyer_seller_scores(master_df)

    # Apply July ramp
    ramp_factor = get_deadline_ramp_factor()
    master_df   = apply_ramp(master_df, ramp_factor)

    # Adjusted win%
    master_df["adj_win_pct"] = get_adjusted_win_pct(master_df, use_ramped=True)

    # Strength of schedule
    remaining_opponents = compute_remaining_opponents(schedule_df)
    master_df = compute_sos(master_df, remaining_opponents)

    # Run Monte Carlo simulation
    with st.spinner(f"🎲 Running {10000:,} simulations..."):
        sim_results = run_simulation(master_df, schedule_df)

    # Persist to disk cache
    save_cache({
        "master":      dataframe_to_cache(master_df),
        "sim_results": sim_results,
        "schedule":    dataframe_to_cache(schedule_df),
    }, "data")

    return master_df, sim_results, schedule_df


def _empty_sim_results(master_df: pd.DataFrame) -> dict:
    """Return zeroed-out sim results for offseason / error states."""
    team_ids = master_df["team_id"].tolist() if not master_df.empty else []
    return {
        "division_odds":              {tid: 0.0 for tid in team_ids},
        "playoff_odds":               {tid: 0.0 for tid in team_ids},
        "ws_odds":                    {tid: 0.0 for tid in team_ids},
        "proj_wins":                  {tid: 0.0 for tid in team_ids},
        "proj_wins_std":              {tid: 0.0 for tid in team_ids},
        "pre_deadline_division_odds": {tid: 0.0 for tid in team_ids},
        "pre_deadline_playoff_odds":  {tid: 0.0 for tid in team_ids},
        "pre_deadline_ws_odds":       {tid: 0.0 for tid in team_ids},
    }


# ── App header ─────────────────────────────────────────────────────────────────
def render_header(season_state: str, last_updated: str):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"# ⚾ MLB {SEASON_YEAR} Season Projections")
        st.markdown(
            "Deadline-aware Monte Carlo projections for all 30 teams. "
            "Accounts for trade deadline selling and buying in win-rate calculations."
        )
    with col2:
        state_labels = {
            "pre_deadline":  "🟡 Pre-Deadline Season",
            "deadline_ramp": "🟠 July Deadline Ramp",
            "post_deadline": "🟢 Post-Deadline Season",
            "offseason":     "❄️ Offseason",
        }
        ramp = get_deadline_ramp_factor()
        st.markdown(f"**Status:** {state_labels.get(season_state, '⚾ In Season')}")
        st.markdown(f"**Ramp:** {ramp:.0%} active")
        st.caption(f"Last updated: {last_updated}")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    season_state = get_season_state()
    last_updated = get_last_updated()

    render_header(season_state, last_updated)

    # Offseason banner
    if season_state == "offseason":
        st.info(
            f"🏁 The {SEASON_YEAR} season is complete. "
            "Showing final standings and end-of-season projections. "
            "Live projections return on Opening Day."
        )

    st.markdown("---")

    # Load data
    try:
        master_df, sim_results, schedule_df = load_all_data()
    except Exception as e:
        st.error(f"⚠️ Data loading failed: {e}")
        st.code(traceback.format_exc())
        st.stop()

    if master_df.empty:
        st.warning("No standings data available. Please try again shortly.")
        st.stop()

    # ── Tabs ───────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Projections",
        "🔄 Deadline Impact",
        "🔍 Team Detail",
        "📖 Methodology",
    ])

    with tab1:
        render_projections_tab(master_df, sim_results)

    with tab2:
        render_deadline_tab(master_df, sim_results)

    with tab3:
        render_team_tab(master_df, sim_results)

    with tab4:
        render_methodology_tab()

    # Footer
    st.markdown("---")
    st.caption(
        "Data: MLB Stats API · Baseball Savant via pybaseball · "
        "Model: Log5 Monte Carlo with deadline-adjusted win rates · "
        f"Simulations: 10,000 · Updated: {last_updated}"
    )


if __name__ == "__main__":
    main()
