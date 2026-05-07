# MLB Season Projections

Deadline-aware Monte Carlo MLB projections for all 30 teams.

## What makes this different

Most projection systems assume your roster today is your roster in August.
This model accounts for trade deadline selling and buying — teams that sell
take a win-rate penalty post-deadline; buyers get a boost. The impact is
gradual across July, not a cliff on July 31.

## Features

- **30-team projections**: Division odds, playoff odds, World Series odds
- **Trade deadline engine**: Algorithmic buyer/seller classification using WC games back,
  run differential, and Pythagorean luck adjustment
- **July ramp**: Gradual 0%→100% deadline adjustment across July
- **Before/after tab**: See exactly how the deadline shifts each team's odds
- **Team detail**: Deep dive on any team's classification drivers and win distribution
- **Daily auto-refresh**: Updates at midnight EST, no manual input needed
- **Offseason mode**: Freezes final standings when season ends

## Deployment (Streamlit Cloud)

1. Push this folder to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set **Main file path** to `app.py`
5. Deploy — no secrets or environment variables needed

## Local development

```bash
pip install -r requirements.txt
streamlit run app.py
```

## File structure

```
mlb_projections/
├── app.py                      # Entry point
├── requirements.txt
├── .streamlit/config.toml      # Dark theme + server config
├── utils/
│   └── constants.py            # All tunable parameters
├── data/
│   ├── fetch_standings.py      # MLB Stats API
│   ├── fetch_schedule.py       # Remaining schedule
│   ├── fetch_statcast.py       # Statcast/pybaseball projections
│   ├── cache_manager.py        # Midnight EST cache logic
│   └── cache/                  # Auto-created on first run
├── engine/
│   ├── buyer_seller.py         # Classification + penalty engine
│   ├── projections.py          # Stat blending
│   ├── simulation.py           # Monte Carlo (10,000 sims)
│   └── schedule_strength.py    # SoS calculator
└── ui/
    ├── tab_projections.py      # Main standings tab
    ├── tab_deadline.py         # Before/after deadline tab
    ├── tab_team.py             # Team detail tab
    └── tab_methodology.py      # Methodology documentation
```

## Tuning the model

All parameters live in `utils/constants.py`:

- `ADJ_HARD_SELLER / ADJ_SOFT_SELLER` — win rate penalties for sellers
- `ADJ_SOFT_BUYER / ADJ_HARD_BUYER` — win rate boosts for buyers
- `HARD_SELLER_GB / SOFT_SELLER_GB` — games back thresholds for classification
- `WEIGHT_CURRENT_SEASON` etc. — stat weighting across years
- `N_SIMULATIONS` — simulation count (higher = slower but more accurate)

## Data sources

- **MLB Stats API**: Standings, schedule (free, official, real-time)
- **Baseball Savant via pybaseball**: Statcast batting and pitching stats

## Season config

Update these in `constants.py` each year:
- `SEASON_YEAR`
- `OPENING_DAY`
- `WORLD_SERIES_END_APPROX`
- `TRADE_DEADLINE`
- `DEADLINE_RAMP_START`
