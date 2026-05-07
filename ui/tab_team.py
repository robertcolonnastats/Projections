"""
tab_team.py
Team Detail tab — deep dive into a single team's projections,
buyer/seller drivers, schedule, and odds trajectory.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from engine.buyer_seller import TIER_COLORS


def render_team_tab(master_df: pd.DataFrame, sim_results: dict):
    st.markdown("## Team Detail")

    # Team selector
    team_options = sorted(
        [(row["name"], row["team_id"]) for _, row in master_df.iterrows()],
        key=lambda x: x[0]
    )
    selected_name = st.selectbox(
        "Select a team",
        [t[0] for t in team_options],
        key="team_detail_select"
    )
    tid = next(t[1] for t in team_options if t[0] == selected_name)
    row = master_df[master_df["team_id"] == tid].iloc[0]

    st.markdown("---")

    # Header
    tier_emoji = {
        "hard_seller": "🔴", "soft_seller": "🟠",
        "neutral": "⚪", "soft_buyer": "🟢", "hard_buyer": "🔵",
    }
    tier = row.get("tier", "neutral")
    label = row.get("tier_label", "Neutral")
    emoji = tier_emoji.get(tier, "⚪")

    col_h1, col_h2, col_h3 = st.columns([2, 1, 1])
    col_h1.markdown(f"## {row['name']} ({row['abbr']})")
    col_h1.markdown(f"{row['division']} · {emoji} **{label}**")
    col_h2.metric("Record", f"{int(row['wins'])}–{int(row['losses'])}")
    col_h3.metric("Win%", f"{row['win_pct']:.3f}")

    st.markdown("---")

    # Odds metrics
    st.markdown("### Season Projections")
    m1, m2, m3, m4, m5 = st.columns(5)

    proj_w = sim_results["proj_wins"].get(tid, row["wins"])
    proj_std = sim_results["proj_wins_std"].get(tid, 0)
    div_odds = sim_results["division_odds"].get(tid, 0)
    playoff_odds = sim_results["playoff_odds"].get(tid, 0)
    ws_odds = sim_results["ws_odds"].get(tid, 0)

    m1.metric("Proj Wins", f"{proj_w:.1f}", f"±{proj_std:.1f}")
    m2.metric("Div%", f"{div_odds:.1%}")
    m3.metric("Playoff%", f"{playoff_odds:.1%}")
    m4.metric("WS%", f"{ws_odds:.2%}")
    m5.metric("SoS", row.get("sos_label", "—"))

    st.markdown("---")

    # Buyer/seller deep dive
    st.markdown("### Deadline Classification Drivers")
    _render_score_breakdown(row)

    st.markdown("---")

    # Before/after comparison for this team
    st.markdown("### Deadline Impact (This Team)")
    _render_team_deadline_impact(tid, row, sim_results)

    st.markdown("---")

    # Win distribution chart
    st.markdown("### Projected Win Distribution")
    _render_win_distribution(tid, proj_w, proj_std)


def _render_score_breakdown(row: pd.Series):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Key Inputs**")
        inputs = {
            "WC Games Back":         f"{row.get('wc_games_back', 0):.1f}",
            "Run Diff / 162":        f"{row.get('rd_per_162', 0):+.0f}",
            "Actual Win%":           f"{row.get('win_pct', 0):.3f}",
            "Pythagorean Win%":      f"{row.get('pythag_win_pct', 0):.3f}",
            "Luck (wins +/-)":       f"{row.get('luck_wins', 0):+.1f}",
            "Blended True Talent%":  f"{row.get('blended_win_pct', 0):.3f}",
        }
        for k, v in inputs.items():
            st.markdown(f"- **{k}:** {v}")

    with col2:
        st.markdown("**Score Calculation**")
        score_data = {
            "Raw Score (WC GB)":     f"{row.get('raw_score', 0):.2f}",
            "Adjusted Score":        f"{row.get('adjusted_score', 0):.2f}",
            "Base Win Adj":          f"{row.get('base_adj', 0):+.1%}",
            "Magnitude Modifier":    f"{row.get('magnitude_modifier', 0):+.1%}",
            "Full Adj (post-DL)":    f"{row.get('final_adj', 0):+.1%}",
            "Ramped Adj (today)":    f"{row.get('ramped_adj', 0):+.1%}",
        }
        for k, v in score_data.items():
            st.markdown(f"- **{k}:** {v}")

    # Visual gauge
    score = row.get("adjusted_score", 0)
    _render_score_gauge(score)


def _render_score_gauge(score: float):
    """Simple horizontal gauge showing buyer/seller score."""
    # Clamp for display
    display_score = max(-10, min(score, 12))

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=display_score,
        title={"text": "Buyer ← Score → Seller"},
        gauge={
            "axis": {"range": [-10, 12], "tickwidth": 1},
            "bar": {"color": "#636efa"},
            "steps": [
                {"range": [-10, -3],  "color": "#1f77b4"},   # hard buyer
                {"range": [-3,   0],  "color": "#2ca02c"},   # soft buyer
                {"range": [0,    4],  "color": "#7f7f7f"},   # neutral
                {"range": [4,    8],  "color": "#ff7f0e"},   # soft seller
                {"range": [8,   12],  "color": "#d62728"},   # hard seller
            ],
            "threshold": {
                "line": {"color": "white", "width": 4},
                "thickness": 0.75,
                "value": display_score,
            },
        },
    ))
    fig.update_layout(height=250, margin=dict(t=40, b=10, l=30, r=30),
                      paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)


def _render_team_deadline_impact(tid: int, row: pd.Series, sim_results: dict):
    pre_po  = sim_results.get("pre_deadline_playoff_odds", {}).get(tid, 0)
    post_po = sim_results.get("playoff_odds", {}).get(tid, 0)
    pre_ws  = sim_results.get("pre_deadline_ws_odds", {}).get(tid, 0)
    post_ws = sim_results.get("ws_odds", {}).get(tid, 0)
    pre_div = sim_results.get("pre_deadline_division_odds", {}).get(tid, 0)
    post_div= sim_results.get("division_odds", {}).get(tid, 0)

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Division Odds",
        f"{post_div:.1%}",
        delta=f"{(post_div - pre_div):+.1%} vs pre-DL",
        delta_color="normal",
    )
    c2.metric(
        "Playoff Odds",
        f"{post_po:.1%}",
        delta=f"{(post_po - pre_po):+.1%} vs pre-DL",
        delta_color="normal",
    )
    c3.metric(
        "World Series Odds",
        f"{post_ws:.2%}",
        delta=f"{(post_ws - pre_ws):+.2%} vs pre-DL",
        delta_color="normal",
    )


def _render_win_distribution(tid: int, proj_mean: float, proj_std: float):
    """Simple normal distribution curve of projected wins."""
    std = max(proj_std, 3.0)   # ensure visible spread
    x = np.linspace(proj_mean - 4 * std, proj_mean + 4 * std, 200)
    y = np.exp(-0.5 * ((x - proj_mean) / std) ** 2) / (std * np.sqrt(2 * np.pi))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y,
        fill="tozeroy",
        mode="lines",
        line=dict(color="#636efa", width=2),
        fillcolor="rgba(99,110,250,0.2)",
        name="Win Distribution",
    ))
    fig.add_vline(
        x=proj_mean, line_dash="dash", line_color="#ef553b",
        annotation_text=f"Proj: {proj_mean:.1f}W",
        annotation_position="top right",
    )

    fig.update_layout(
        xaxis_title="Final Wins",
        yaxis_title="Probability Density",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=300,
        showlegend=False,
        yaxis=dict(showticklabels=False),
        xaxis=dict(gridcolor="rgba(128,128,128,0.2)"),
    )
    st.plotly_chart(fig, use_container_width=True)
