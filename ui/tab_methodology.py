"""
tab_methodology.py
Methodology tab — plain English explanation of the model,
data sources, formulas, and update cadence.
"""

import streamlit as st
from data.cache_manager import get_last_updated, get_season_state, get_deadline_ramp_factor
from utils.constants import (
    ADJ_HARD_SELLER, ADJ_SOFT_SELLER, ADJ_NEUTRAL, ADJ_SOFT_BUYER, ADJ_HARD_BUYER,
    HARD_SELLER_GB, SOFT_SELLER_GB, NEUTRAL_BAND,
    WEIGHT_CURRENT_SEASON, WEIGHT_LAST_YEAR, WEIGHT_TWO_YEARS_AGO,
    N_SIMULATIONS, PYTHAG_EXPONENT,
)


def render_methodology_tab():
    st.markdown("## Methodology")
    st.caption(f"Data last updated: {get_last_updated()}")

    st.markdown("""
This model was designed around a core insight missing from most public projection systems:
**teams that sell at the trade deadline get meaningfully worse after July 31, but existing
models don't account for it.** This system does.

The following explains every component of the model, how inputs flow together, and why
each design choice was made.
""")

    # ── Overview ──────────────────────────────────────────────────────────────
    with st.expander("📊 Overview & Philosophy", expanded=True):
        st.markdown("""
### What this model does differently

Most projection systems generate a "rest of season" win% for each team and run
simulations from there. The problem: they assume the roster you have today is the
roster you'll have in August and September. For sellers, that's just not true.

This model:
1. Builds a true-talent estimate from **weighted Statcast and historical stats**
2. Identifies which teams will likely **buy or sell** at the deadline using real metrics
3. **Adjusts each team's win rate** post-deadline based on their seller/buyer status
4. **Gradually ramps** those adjustments across July rather than applying a cliff
5. Runs **10,000 Monte Carlo simulations** at the individual game level so wins and losses
   always sum correctly across the league
6. Recalculates **strength of schedule** after deadline adjustments propagate
7. Updates automatically every day at midnight EST

The before/after comparison on the Deadline Impact tab shows exactly how much this
adjustment moves the needle for each team.
""")

    # ── Data Sources ──────────────────────────────────────────────────────────
    with st.expander("📡 Data Sources"):
        st.markdown("""
### MLB Stats API
- **What:** Current standings, win/loss records, runs scored, runs allowed, and remaining schedule
- **Why:** Free, real-time, no scraping required, official source
- **Update cadence:** Pulled fresh each day at midnight EST

### Baseball Savant via pybaseball
- **What:** Current season and prior 2 seasons of batting stats (wRC+, OBP, SLG, HR)
  and pitching stats (FIP, ERA, K%, BB%, HR/9)
- **Why:** Statcast data is the gold standard for measuring true performance
  independent of park factors and small sample luck
- **Update cadence:** Same as above

### No manual inputs
Once running, the model requires zero human intervention. Everything is algorithm-driven.
The only thing that requires updating is `constants.py` at the start of each season
to reflect the new schedule.
""")

    # ── Team Projections ──────────────────────────────────────────────────────
    with st.expander("🔮 Team Projections"):
        st.markdown(f"""
### Stat weighting

We build a "true talent" projection for each team by blending three years of data:

| Season | Weight |
|---|---|
| Current year | {WEIGHT_CURRENT_SEASON:.0%} |
| Last year | {WEIGHT_LAST_YEAR:.0%} |
| Two years ago | {WEIGHT_TWO_YEARS_AGO:.0%} |

The current year weight increases as the season progresses (more data = more reliable).
By September, the current season carries roughly 70% of the weight.

### Pitching metrics

We use **FIP** (Fielding Independent Pitching) as the primary pitching metric, blended
with ERA. FIP holds pitchers accountable for actual home runs allowed — unlike xFIP,
which removes home run rate entirely. We disagree with xFIP's premise that home run
rate is entirely out of a pitcher's control.

Our blend: **70% FIP + 30% ERA**

### Pythagorean win%

Bill James's formula estimates how many games a team "should" have won based on
runs scored and runs allowed:

> **Win% = RS^{exp} / (RS^{exp} + RA^{exp})**  where exp = {PYTHAG_EXPONENT}

### Blended true talent

Final team strength = 50% weighted Statcast projection + 50% Pythagorean win%.
This blend captures both underlying skill (Statcast) and recent performance (Pythagorean).
""")

    # ── Buyer/Seller Engine ───────────────────────────────────────────────────
    with st.expander("📈 Buyer / Seller Classification"):
        st.markdown(f"""
### How teams get classified

Each team receives a **score** on a continuous scale. Higher scores = more likely to sell.
The score is calculated from three inputs:

**1. Wild Card Games Back (primary input)**
This is the most direct signal. A team 8 games out of a wild card spot in late June
has very little incentive to buy.

**2. Run Differential modifier**
A team with a strongly positive run differential may just be unlucky — their results
don't reflect their true quality. Their score is pulled toward the buyer side.
A team with poor run differential may be "lucky" — score pushed toward seller.

**3. Pythagorean vs. actual luck modifier**
If a team is significantly outperforming their Pythagorean win% (winning more than
their run differential says they should), they're running hot. We push their score
toward seller territory since regression is likely. The reverse applies for unlucky teams.

### Tier thresholds

| Tier | WC Games Back | Win Rate Adjustment |
|---|---|---|
| 🔴 Hard Seller | {HARD_SELLER_GB}+ GB | {ADJ_HARD_SELLER:.0%} post-deadline |
| 🟠 Soft Seller | {SOFT_SELLER_GB}–{HARD_SELLER_GB} GB | {ADJ_SOFT_SELLER:.0%} post-deadline |
| ⚪ Neutral | Within {NEUTRAL_BAND} GB | No adjustment |
| 🟢 Soft Buyer | In WC picture | {ADJ_SOFT_BUYER:+.0%} post-deadline |
| 🔵 Hard Buyer | Division leader / top WC | {ADJ_HARD_BUYER:+.0%} post-deadline |

### Why buyers get a smaller boost than sellers get a penalty

Selling means replacing a productive player with a replacement-level callup.
That's a large, measurable talent drop. Buying means adding one or two good players
to an already-constructed roster. The marginal gain is real but smaller. The asymmetry
reflects that reality.

### Magnitude modifier

Within each tier, the penalty or boost is further adjusted by ±20% based on
run differential and luck. A hard seller with terrible run differential gets the
full −12%; a hard seller who's been genuinely unlucky gets something closer to −10%.
""")

    # ── July Ramp ─────────────────────────────────────────────────────────────
    with st.expander("📅 July Deadline Ramp"):
        ramp = get_deadline_ramp_factor()
        st.markdown(f"""
### Why a gradual ramp?

Teams don't wait until July 31 to start making moves. Players go on the injured list
strategically, teams stop acquiring veterans, and sellers start playing their prospects
in July. The impact is gradual.

We model this as a linear ramp from **July 1 (0%)** to **July 31 (100%)**.

**Current ramp factor: {ramp:.0%}**

Before July 1: no adjustment applied  
July 1: adjustments begin at 0%  
July 15: adjustments at ~50%  
July 31+: full adjustment locked in

The ramp applies to both the seller penalty and the buyer boost.
""")

    # ── Monte Carlo Simulation ─────────────────────────────────────────────────
    with st.expander("🎲 Monte Carlo Simulation"):
        st.markdown(f"""
### How the simulation works

We simulate the remaining schedule **{N_SIMULATIONS:,} times**. In each simulation:

1. Every remaining game is played one at a time
2. Win probability for each game is calculated using the **Log5 formula**
3. A random number is drawn to determine the winner
4. Wins and losses are assigned — one win and one loss per game, guaranteed
5. After all games are played, we record division winners, playoff qualifiers, and
   run a simplified playoff bracket to find a World Series champion
6. After {N_SIMULATIONS:,} simulations, we count how often each team achieves each outcome

### Log5 formula

Bill James's formula converts two teams' win percentages into a head-to-head probability:

> P(A beats B) = (A − A×B) / (A + B − 2×A×B)

This correctly handles extreme cases: a .700 team vs a .300 team, or two equal teams.

### Zero-sum guarantee

Because every game produces exactly one winner and one loser, total wins across
all 30 teams always equals total losses. No win probability inflation or deflation.

### Speed vs. accuracy

{N_SIMULATIONS:,} simulations provides odds accurate to within roughly ±0.5 percentage points
for common outcomes (playoff berths). World Series odds for longshot teams may vary
by ±0.1 percentage points. This balance keeps the app responsive on Streamlit Cloud.
Results are cached after each midnight refresh and reused throughout the day.
""")

    # ── Strength of Schedule ──────────────────────────────────────────────────
    with st.expander("📋 Strength of Schedule"):
        st.markdown("""
### How SoS is calculated

Strength of schedule is the average adjusted win% of a team's remaining opponents.
A SoS of .520 means the team's remaining schedule is against opponents who win
52% of their games on average.

**Crucially**, SoS is recalculated **after** deadline adjustments are applied.
If a team's opponents are all hard sellers who take a win rate hit, that team's
remaining schedule gets easier — which flows through the simulation automatically.

This is a feature most systems miss: deadline activity ripples through the strength
of schedule for everyone in that team's remaining games.

### Labels
- **Easy**: Bottom third of schedules remaining
- **Average**: Middle third
- **Hard**: Top third
""")

    # ── Update Cadence & Offseason ─────────────────────────────────────────────
    with st.expander("🔄 Update Cadence & Offseason Mode"):
        state = get_season_state()
        st.markdown(f"""
### Daily updates

Data refreshes automatically every day at midnight EST. The first user to load
the app after midnight triggers a fresh data pull; all subsequent users that day
see the cached results.

**Current system state: `{state}`**

### Offseason mode

When the World Series ends (approximately late October), the app freezes final
standings and shows end-of-season projections. No data is fetched during the offseason.
The methodology tab remains active year-round.

The app automatically returns to live mode on Opening Day the following season.
""")

    # ── Limitations ────────────────────────────────────────────────────────────
    with st.expander("⚠️ Limitations & Known Simplifications"):
        st.markdown("""
### What this model does not do

**No player-level transactions.** The model does not track actual trades as they
happen. Instead, it applies team-level penalties based on the likelihood of selling.
Once a team clearly sells (e.g., their star pitcher is traded), their score shifts
algorithmically — but there is no real-time trade parser.

**Injuries not modeled.** Player injuries can dramatically affect team quality
mid-season. The model does not have an injury feed.

**Playoff seeding simplified.** The playoff bracket simulation uses a simplified
random bracket rather than the actual MLB seeding structure. This affects WS odds
slightly but not playoff qualification odds.

**Home field advantage not modeled.** The Log5 formula treats all games equally.
In reality, home teams win approximately 54% of games. This is a known simplification.

**Prospect quality on returning teams.** When a hard seller trades a star, they
receive prospects. Those prospects are modeled as replacement level, which is
accurate for 2025 impact but understates the future value the seller receives.

These limitations are documented transparently so users understand where the model
is strong (deadline impact, playoff odds, schedule-adjusted projections) and where
it is simplified.
""")
