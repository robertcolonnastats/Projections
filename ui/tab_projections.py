"""
tab_projections.py
Main projections tab — full 30-team standings with playoff/WS odds.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from engine.buyer_seller import TIER_COLORS, TIER_LABELS


def render_projections_tab(master_df: pd.DataFrame, sim_results: dict):
    st.markdown("## 2025 MLB Season Projections")
    st.caption("Updated daily at midnight EST · 10,000-simulation Monte Carlo model")

    # Build display DataFrame
    display_df = _build_display_df(master_df, sim_results)

    # League filter
    league_filter = st.radio(
        "League", ["All", "AL", "NL"], horizontal=True, key="proj_league"
    )
    if league_filter != "All":
        display_df = display_df[display_df["League"] == league_filter]

    # Division filter
    all_divs = sorted(display_df["Division"].unique())
    div_filter = st.selectbox("Division", ["All Divisions"] + all_divs, key="proj_div")
    if div_filter != "All Divisions":
        display_df = display_df[display_df["Division"] == div_filter]

    st.markdown("---")

    # Render by division
    divisions_in_view = display_df["Division"].unique()
    for div in sorted(divisions_in_view):
        div_df = display_df[display_df["Division"] == div].sort_values(
            "Proj W", ascending=False
        )
        st.markdown(f"### {div}")
        _render_division_table(div_df)
        st.markdown("")

    # Legend
    st.markdown("---")
    st.markdown("**Buyer / Seller Legend**")
    cols = st.columns(5)
    labels = [("🔴 Hard Seller", "−12% post-deadline win rate"),
              ("🟠 Soft Seller", "−6% post-deadline win rate"),
              ("⚪ Neutral", "No adjustment"),
              ("🟢 Soft Buyer", "+4% post-deadline win rate"),
              ("🔵 Hard Buyer", "+7% post-deadline win rate")]
    for col, (label, desc) in zip(cols, labels):
        col.markdown(f"**{label}**  \n{desc}")


def _build_display_df(master_df: pd.DataFrame, sim_results: dict) -> pd.DataFrame:
    rows = []
    for _, row in master_df.iterrows():
        tid = row["team_id"]
        rows.append({
            "Team":        row["abbr"],
            "Full Name":   row["name"],
            "League":      row["league"],
            "Division":    row["division"],
            "W":           int(row["wins"]),
            "L":           int(row["losses"]),
            "Win%":        f"{row['win_pct']:.3f}",
            "Pythag%":     f"{row.get('pythag_win_pct', row['win_pct']):.3f}",
            "GB (WC)":     f"{row['wc_games_back']:.1f}" if row['wc_games_back'] > 0 else "—",
            "Proj W":      round(sim_results["proj_wins"].get(tid, row["wins"]), 1),
            "Div%":        f"{sim_results['division_odds'].get(tid, 0):.1%}",
            "Playoff%":    f"{sim_results['playoff_odds'].get(tid, 0):.1%}",
            "WS%":         f"{sim_results['ws_odds'].get(tid, 0):.1%}",
            "Status":      row.get("tier_label", "Neutral"),
            "tier":        row.get("tier", "neutral"),
            "SoS":         row.get("sos_label", "—"),
        })

    return pd.DataFrame(rows)


def _render_division_table(df: pd.DataFrame):
    """Render a styled division standings table."""

    tier_emoji = {
        "Hard Seller": "🔴",
        "Soft Seller": "🟠",
        "Neutral":     "⚪",
        "Soft Buyer":  "🟢",
        "Hard Buyer":  "🔵",
    }

    display_cols = ["Team", "W", "L", "Win%", "Pythag%", "GB (WC)",
                    "Proj W", "Div%", "Playoff%", "WS%", "Status", "SoS"]

    render_df = df[display_cols].copy()
    render_df["Status"] = render_df["Status"].apply(
        lambda s: f"{tier_emoji.get(s, '⚪')} {s}"
    )

    st.dataframe(
        render_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Team":     st.column_config.TextColumn("Team",    width="small"),
            "W":        st.column_config.NumberColumn("W",     width="small"),
            "L":        st.column_config.NumberColumn("L",     width="small"),
            "Win%":     st.column_config.TextColumn("Win%",    width="small"),
            "Pythag%":  st.column_config.TextColumn("Pythag%", width="small"),
            "GB (WC)":  st.column_config.TextColumn("GB",      width="small"),
            "Proj W":   st.column_config.NumberColumn("Proj W",width="small"),
            "Div%":     st.column_config.TextColumn("Div%",    width="small"),
            "Playoff%": st.column_config.TextColumn("Playoff%",width="medium"),
            "WS%":      st.column_config.TextColumn("WS%",     width="small"),
            "Status":   st.column_config.TextColumn("Deadline Status", width="medium"),
            "SoS":      st.column_config.TextColumn("Schedule", width="small"),
        }
    )
