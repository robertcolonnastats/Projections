"""
buyer_seller.py
Classifies all 30 teams on a buyer/seller spectrum and computes
the win-rate adjustment to apply post-deadline.
"""

import pandas as pd
import numpy as np
from utils.constants import (
    HARD_SELLER_GB, SOFT_SELLER_GB, NEUTRAL_BAND,
    ADJ_HARD_SELLER, ADJ_SOFT_SELLER, ADJ_NEUTRAL,
    ADJ_SOFT_BUYER, ADJ_HARD_BUYER,
    PYTHAG_EXPONENT, PYTHAG_GAP_SENSITIVITY,
    RD_MODIFIER_CAP, RD_SENSITIVITY, RD_SCALE_GAMES,
)


TIER_LABELS = {
    "hard_seller":  "Hard Seller",
    "soft_seller":  "Soft Seller",
    "neutral":      "Neutral",
    "soft_buyer":   "Soft Buyer",
    "hard_buyer":   "Hard Buyer",
}

TIER_COLORS = {
    "hard_seller":  "#d62728",   # red
    "soft_seller":  "#ff7f0e",   # orange
    "neutral":      "#7f7f7f",   # grey
    "soft_buyer":   "#2ca02c",   # green
    "hard_buyer":   "#1f77b4",   # blue
}


def compute_pythagorean_win_pct(runs_scored: float, runs_allowed: float) -> float:
    """Bill James Pythagorean win% with exponent 1.83."""
    if runs_scored <= 0 or runs_allowed <= 0:
        return 0.500
    exp = PYTHAG_EXPONENT
    return runs_scored ** exp / (runs_scored ** exp + runs_allowed ** exp)


def compute_buyer_seller_scores(standings_df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes the standings DataFrame and returns it with added columns:
        pythag_win_pct      – Pythagorean expected win%
        luck_wins           – actual wins minus Pythagorean expected wins
        rd_per_162          – run differential normalised to 162 games
        raw_score           – continuous buyer/seller score (positive = seller)
        adjusted_score      – score after run-diff and Pythagorean modifiers
        tier                – 'hard_seller' | 'soft_seller' | 'neutral' | 'soft_buyer' | 'hard_buyer'
        tier_label          – human-readable label
        base_adj            – base win-rate adjustment for this tier
        magnitude_adj       – modifier to base_adj from run-diff / luck
        final_adj           – total win-rate adjustment (0.0 pre-deadline, ramped in July)
    """
    df = standings_df.copy()

    # ── Pythagorean win% ────────────────────────────────────────────────────────
    df["pythag_win_pct"] = df.apply(
        lambda r: compute_pythagorean_win_pct(
            r["runs_scored"], r["runs_allowed"]
        ), axis=1
    )

    # ── Luck: actual wins vs Pythagorean expected wins ─────────────────────────
    df["pythag_expected_wins"] = df["pythag_win_pct"] * df["games_played"]
    df["luck_wins"] = df["wins"] - df["pythag_expected_wins"]

    # ── Run differential per 162 ───────────────────────────────────────────────
    df["rd_per_162"] = df.apply(
        lambda r: (r["run_differential"] / max(r["games_played"], 1)) * RD_SCALE_GAMES,
        axis=1
    )

    # ── Raw score: WC games back (positive = behind, i.e. seller candidate) ───
    # Division leaders already assigned wc_games_back = -5.0
    df["raw_score"] = df["wc_games_back"]

    # ── Run-differential modifier ──────────────────────────────────────────────
    # Strong positive run diff → team may be unlucky → pull score toward buyer
    # Strong negative run diff → team may be lucky   → push score toward seller
    rd_modifier = -df["rd_per_162"] * RD_SENSITIVITY   # negative RD = push seller
    rd_modifier = rd_modifier.clip(-RD_MODIFIER_CAP, RD_MODIFIER_CAP)

    # ── Pythagorean / luck modifier ────────────────────────────────────────────
    # If luck_wins > 0 (lucky), push toward seller (inflate score)
    # If luck_wins < 0 (unlucky), pull toward buyer (deflate score)
    luck_modifier = df["luck_wins"] * PYTHAG_GAP_SENSITIVITY

    # ── Adjusted score ─────────────────────────────────────────────────────────
    df["adjusted_score"] = df["raw_score"] + rd_modifier + luck_modifier

    # ── Tier classification from adjusted_score ────────────────────────────────
    def classify_tier(score: float) -> str:
        if score >= HARD_SELLER_GB:
            return "hard_seller"
        elif score >= SOFT_SELLER_GB:
            return "soft_seller"
        elif score >= -NEUTRAL_BAND:
            return "neutral"
        elif score >= -8.0:
            return "soft_buyer"
        else:
            return "hard_buyer"

    df["tier"] = df["adjusted_score"].apply(classify_tier)
    df["tier_label"] = df["tier"].map(TIER_LABELS)

    # ── Base win-rate adjustment ───────────────────────────────────────────────
    base_adj_map = {
        "hard_seller":  ADJ_HARD_SELLER,
        "soft_seller":  ADJ_SOFT_SELLER,
        "neutral":      ADJ_NEUTRAL,
        "soft_buyer":   ADJ_SOFT_BUYER,
        "hard_buyer":   ADJ_HARD_BUYER,
    }
    df["base_adj"] = df["tier"].map(base_adj_map)

    # ── Magnitude modifier within tier ────────────────────────────────────────
    # Adjusts the penalty/boost within its tier band based on run diff + luck.
    # Sellers get a deeper cut if they're truly bad; buyers get more if unlucky.
    # Scale: ±20% of the base adjustment max.
    df["magnitude_modifier"] = _compute_magnitude_modifier(df)

    # ── Final adjustment (pre-ramp; ramp factor applied at sim time) ───────────
    df["final_adj"] = df["base_adj"] + df["magnitude_modifier"]

    # Cap adjustments to reasonable bounds
    df["final_adj"] = df["final_adj"].clip(-0.18, +0.10)

    return df


def _compute_magnitude_modifier(df: pd.DataFrame) -> pd.Series:
    """
    Returns a Series of small adjustments (±20% of base_adj) driven by
    run differential and luck within each team's tier.
    """
    modifiers = []
    for _, row in df.iterrows():
        base = row["base_adj"]
        if base == 0.0:
            modifiers.append(0.0)
            continue

        # Normalise rd_per_162 to [-1, 1] range (±50 runs = max effect)
        rd_factor   = np.clip(row["rd_per_162"] / 50.0, -1.0, 1.0)
        luck_factor = np.clip(row["luck_wins"] / 5.0, -1.0, 1.0)

        # Combined factor (equal weight)
        combined = (rd_factor + luck_factor) / 2.0

        # For sellers (negative base), more negative rd/luck = deeper cut
        # For buyers (positive base), more positive rd/luck = bigger boost
        magnitude = base * combined * 0.20   # max ±20% of base
        modifiers.append(round(magnitude, 4))

    return pd.Series(modifiers, index=df.index)


def apply_ramp(df: pd.DataFrame, ramp_factor: float) -> pd.DataFrame:
    """
    Apply the July ramp factor to final_adj.
    ramp_factor: 0.0 (July 1) → 1.0 (July 31+)
    Returns df with 'ramped_adj' column added.
    """
    df = df.copy()
    df["ramped_adj"] = df["final_adj"] * ramp_factor
    return df


def get_adjusted_win_pct(df: pd.DataFrame, use_ramped: bool = True) -> pd.Series:
    """
    Returns a Series of adjusted win percentages.
    Blends projected win% with the deadline adjustment.
    """
    adj_col = "ramped_adj" if (use_ramped and "ramped_adj" in df.columns) else "final_adj"
    adjusted = (df["proj_win_pct"] + df[adj_col]).clip(0.20, 0.80)
    return adjusted
