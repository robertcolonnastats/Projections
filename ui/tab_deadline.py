"""
tab_deadline.py
Deadline Impact tab — before/after odds comparison showing
how the trade deadline model shifts each team's projections.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from engine.buyer_seller import TIER_COLORS
from data.cache_manager import get_deadline_ramp_factor, get_season_state


def render_deadline_tab(master_df: pd.DataFrame, sim_results: dict):
    state = get_season_state()
    ramp  = get_deadline_ramp_factor()

    st.markdown("## Trade Deadline Impact")

    # Context banner
    if state == "pre_deadline":
        st.info("⏳ Trade deadline adjustments begin ramping July 1. "
                "Check back then to see the deadline's projected impact on each team.")
    elif state == "deadline_ramp":
        pct = int(ramp * 100)
        st.warning(f"📅 July deadline ramp is **{pct}% active**. "
                   "Adjustments will reach full strength on July 31.")
    elif state == "post_deadline":
        st.success("✅ Trade deadline has passed. Full adjustments are locked in.")
    elif state == "offseason":
        st.info("🏁 Season complete. Showing final deadline impact from last season.")

    st.markdown("---")

    # Build comparison DataFrame
    comp_df = _build_comparison_df(master_df, sim_results)

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    sellers = comp_df[comp_df["tier"].isin(["hard_seller", "soft_seller"])]
    buyers  = comp_df[comp_df["tier"].isin(["hard_buyer",  "soft_buyer"])]

    col1.metric("Hard Sellers", len(comp_df[comp_df["tier"] == "hard_seller"]))
    col2.metric("Soft Sellers + Buyers", f"{len(sellers)} / {len(buyers)}")
    col3.metric("Ramp Factor", f"{ramp:.0%}")

    st.markdown("---")

    # Chart: Playoff odds change
    st.markdown("### Playoff Odds: Before vs. After Deadline Adjustments")
    _render_odds_delta_chart(comp_df, "playoff_delta", "Playoff% Change", "Playoff Odds Impact")

    st.markdown("### World Series Odds: Before vs. After Deadline Adjustments")
    _render_odds_delta_chart(comp_df, "ws_delta", "WS% Change", "World Series Odds Impact")

    st.markdown("---")

    # Detailed table
    st.markdown("### Full Team Breakdown")
    _render_comparison_table(comp_df)

    # Buyer/seller score drivers
    st.markdown("---")
    st.markdown("### What's Driving Each Team's Classification")
    _render_score_drivers(master_df)


def _build_comparison_df(master_df: pd.DataFrame, sim_results: dict) -> pd.DataFrame:
    rows = []
    for _, row in master_df.iterrows():
        tid = row["team_id"]

        pre_playoff = sim_results.get("pre_deadline_playoff_odds", {}).get(tid, 0)
        post_playoff = sim_results.get("playoff_odds", {}).get(tid, 0)
        pre_ws  = sim_results.get("pre_deadline_ws_odds", {}).get(tid, 0)
        post_ws = sim_results.get("ws_odds", {}).get(tid, 0)
        pre_div = sim_results.get("pre_deadline_division_odds", {}).get(tid, 0)
        post_div= sim_results.get("division_odds", {}).get(tid, 0)

        rows.append({
            "team_id":       tid,
            "Team":          row["abbr"],
            "Full Name":     row["name"],
            "tier":          row.get("tier", "neutral"),
            "Status":        row.get("tier_label", "Neutral"),
            "Win Adj":       f"{row.get('ramped_adj', 0):+.1%}",
            "Pre Playoff%":  pre_playoff,
            "Post Playoff%": post_playoff,
            "playoff_delta": post_playoff - pre_playoff,
            "Pre WS%":       pre_ws,
            "Post WS%":      post_ws,
            "ws_delta":      post_ws - pre_ws,
            "Pre Div%":      pre_div,
            "Post Div%":     post_div,
            "div_delta":     post_div - pre_div,
            "score":         round(row.get("adjusted_score", 0), 2),
        })

    return pd.DataFrame(rows).sort_values("playoff_delta")


def _render_odds_delta_chart(df: pd.DataFrame, delta_col: str, label: str, title: str):
    tier_color_map = {
        "hard_seller": "#d62728",
        "soft_seller": "#ff7f0e",
        "neutral":     "#7f7f7f",
        "soft_buyer":  "#2ca02c",
        "hard_buyer":  "#1f77b4",
    }

    sorted_df = df.sort_values(delta_col)
    colors = [tier_color_map.get(t, "#7f7f7f") for t in sorted_df["tier"]]

    fig = go.Figure(go.Bar(
        x=sorted_df["Team"],
        y=(sorted_df[delta_col] * 100).round(1),
        marker_color=colors,
        text=(sorted_df[delta_col] * 100).round(1).apply(lambda v: f"{v:+.1f}%"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>" + label + ": %{y:+.1f}%<extra></extra>",
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Team",
        yaxis_title="Percentage Point Change",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=400,
        yaxis=dict(gridcolor="rgba(128,128,128,0.2)"),
        showlegend=False,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(128,128,128,0.5)")

    st.plotly_chart(fig, use_container_width=True)


def _render_comparison_table(df: pd.DataFrame):
    tier_emoji = {
        "hard_seller": "🔴", "soft_seller": "🟠",
        "neutral": "⚪", "soft_buyer": "🟢", "hard_buyer": "🔵",
    }

    display = df[["Team", "Status", "Win Adj",
                  "Pre Playoff%", "Post Playoff%", "playoff_delta",
                  "Pre WS%", "Post WS%", "ws_delta"]].copy()

    display["Status"] = df.apply(
        lambda r: f"{tier_emoji.get(r['tier'], '⚪')} {r['Status']}", axis=1
    )
    display["Playoff Δ"] = (df["playoff_delta"] * 100).round(1).apply(lambda v: f"{v:+.1f}pp")
    display["WS Δ"]      = (df["ws_delta"]      * 100).round(2).apply(lambda v: f"{v:+.2f}pp")
    display["Pre Playoff%"]  = (df["Pre Playoff%"]  * 100).round(1).apply(lambda v: f"{v:.1f}%")
    display["Post Playoff%"] = (df["Post Playoff%"] * 100).round(1).apply(lambda v: f"{v:.1f}%")
    display["Pre WS%"]       = (df["Pre WS%"]       * 100).round(2).apply(lambda v: f"{v:.2f}%")
    display["Post WS%"]      = (df["Post WS%"]      * 100).round(2).apply(lambda v: f"{v:.2f}%")

    final_cols = ["Team", "Status", "Win Adj",
                  "Pre Playoff%", "Post Playoff%", "Playoff Δ",
                  "Pre WS%", "Post WS%", "WS Δ"]

    st.dataframe(
        display[final_cols],
        use_container_width=True,
        hide_index=True,
    )


def _render_score_drivers(master_df: pd.DataFrame):
    """Scatter plot: WC Games Back vs Run Diff, colored by tier."""
    tier_color_map = {
        "hard_seller": "#d62728", "soft_seller": "#ff7f0e",
        "neutral": "#7f7f7f", "soft_buyer": "#2ca02c", "hard_buyer": "#1f77b4",
    }

    plot_df = master_df[["abbr", "wc_games_back", "rd_per_162",
                          "tier", "tier_label", "luck_wins"]].copy()
    plot_df["color"] = plot_df["tier"].map(tier_color_map)
    plot_df["luck_label"] = plot_df["luck_wins"].round(1).apply(
        lambda v: f"Luck: {v:+.1f}W"
    )

    fig = go.Figure()
    for tier, group in plot_df.groupby("tier"):
        fig.add_trace(go.Scatter(
            x=group["wc_games_back"],
            y=group["rd_per_162"],
            mode="markers+text",
            name=group["tier_label"].iloc[0],
            text=group["abbr"],
            textposition="top center",
            marker=dict(
                color=tier_color_map.get(tier, "#7f7f7f"),
                size=12,
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "WC GB: %{x:.1f}<br>"
                "Run Diff/162: %{y:.0f}<br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        title="Buyer/Seller Classification: WC Games Back vs Run Differential",
        xaxis_title="Wild Card Games Back (higher = further out)",
        yaxis_title="Run Differential per 162 Games",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=500,
        xaxis=dict(gridcolor="rgba(128,128,128,0.2)"),
        yaxis=dict(gridcolor="rgba(128,128,128,0.2)"),
    )
    fig.add_vline(x=4.0,  line_dash="dash", line_color="rgba(255,127,14,0.4)",  annotation_text="Soft Seller line")
    fig.add_vline(x=8.0,  line_dash="dash", line_color="rgba(214,39,40,0.4)",   annotation_text="Hard Seller line")
    fig.add_vline(x=-3.0, line_dash="dash", line_color="rgba(44,160,44,0.4)",   annotation_text="Soft Buyer line")
    fig.add_hline(y=0,    line_dash="dot",  line_color="rgba(128,128,128,0.3)")

    st.plotly_chart(fig, use_container_width=True)
