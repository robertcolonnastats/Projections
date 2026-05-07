"""
constants.py
All tunable parameters in one place. Edit here to adjust model behavior.
"""

# ── Season boundaries ──────────────────────────────────────────────────────────
SEASON_YEAR = 2025
OPENING_DAY = "2025-03-27"
WORLD_SERIES_END_APPROX = "2025-11-01"   # updated after WS ends
TRADE_DEADLINE = "2025-07-31"
DEADLINE_RAMP_START = "2025-07-01"       # when July ramp begins

# ── Stat weighting for projections ────────────────────────────────────────────
WEIGHT_CURRENT_SEASON = 0.50
WEIGHT_LAST_YEAR      = 0.30
WEIGHT_TWO_YEARS_AGO  = 0.20

# ── Buyer / Seller thresholds (Wild Card games back) ──────────────────────────
HARD_SELLER_GB   =  8.0    # 8+ GB wild card
SOFT_SELLER_GB   =  4.0    # 4–7.9 GB
NEUTRAL_BAND     =  3.0    # within 3 GB either direction
SOFT_BUYER_AHEAD =  0.0    # in WC picture but not division leader
HARD_BUYER_AHEAD =  0.0    # division leader or top WC seed (set via rank logic)

# ── Win-rate adjustments (post-deadline, fully ramped) ────────────────────────
ADJ_HARD_SELLER  = -0.12   # −12 %
ADJ_SOFT_SELLER  = -0.06   # − 6 %
ADJ_NEUTRAL      =  0.00
ADJ_SOFT_BUYER   = +0.04   # + 4 %
ADJ_HARD_BUYER   = +0.07   # + 7 %

# ── Run-differential modifier ─────────────────────────────────────────────────
# Applied to both tier classification and penalty magnitude.
# A team with a strongly positive run diff gets pulled toward "buyer" by this factor.
RD_SCALE_GAMES   = 162     # normalise run diff to per-162-game pace
RD_MODIFIER_CAP  =  2.0    # max GB shift from run-diff alone
RD_SENSITIVITY   =  0.02   # GB shift per 10 runs of normalised run diff

# ── Pythagorean exponent ───────────────────────────────────────────────────────
PYTHAG_EXPONENT  = 1.83    # Bill James standard

# ── Pythagorean vs actual gap modifier ────────────────────────────────────────
# If a team is outperforming their Pythagorean win%, they are "lucky";
# push their seller score up (closer to selling).
PYTHAG_GAP_SENSITIVITY = 0.5   # fraction of gap (in wins) added to GB score

# ── Monte Carlo ───────────────────────────────────────────────────────────────
N_SIMULATIONS    = 10_000
RANDOM_SEED      = 42

# ── Playoff structure ─────────────────────────────────────────────────────────
N_DIVISION_WINNERS   = 3    # per league
N_WILD_CARDS         = 3    # per league (expanded format)
TOTAL_PLAYOFF_TEAMS  = 12

# ── Cache ──────────────────────────────────────────────────────────────────────
CACHE_DIR        = "data/cache"
CACHE_FILE       = "data/cache/latest.json"
SIM_CACHE_FILE   = "data/cache/sim_results.json"
CACHE_TTL_HOURS  = 24

# ── MLB Stats API ──────────────────────────────────────────────────────────────
MLB_API_BASE     = "https://statsapi.mlb.com/api/v1"

# ── Team metadata ─────────────────────────────────────────────────────────────
# Maps MLB team ID → (name, abbreviation, division, league)
TEAM_INFO = {
    108: ("Los Angeles Angels",      "LAA", "AL West",    "AL"),
    109: ("Arizona Diamondbacks",    "ARI", "NL West",    "NL"),
    110: ("Baltimore Orioles",       "BAL", "AL East",    "AL"),
    111: ("Boston Red Sox",          "BOS", "AL East",    "AL"),
    112: ("Chicago Cubs",            "CHC", "NL Central", "NL"),
    113: ("Cincinnati Reds",         "CIN", "NL Central", "NL"),
    114: ("Cleveland Guardians",     "CLE", "AL Central", "AL"),
    115: ("Colorado Rockies",        "COL", "NL West",    "NL"),
    116: ("Detroit Tigers",          "DET", "AL Central", "AL"),
    117: ("Houston Astros",          "HOU", "AL West",    "AL"),
    118: ("Kansas City Royals",      "KC",  "AL Central", "AL"),
    119: ("Los Angeles Dodgers",     "LAD", "NL West",    "NL"),
    120: ("Washington Nationals",    "WSH", "NL East",    "NL"),
    121: ("New York Mets",           "NYM", "NL East",    "NL"),
    133: ("Oakland Athletics",       "OAK", "AL West",    "AL"),
    134: ("Pittsburgh Pirates",      "PIT", "NL Central", "NL"),
    135: ("San Diego Padres",        "SD",  "NL West",    "NL"),
    136: ("Seattle Mariners",        "SEA", "AL West",    "AL"),
    137: ("San Francisco Giants",    "SF",  "NL West",    "NL"),
    138: ("St. Louis Cardinals",     "STL", "NL Central", "NL"),
    139: ("Tampa Bay Rays",          "TB",  "AL East",    "AL"),
    140: ("Texas Rangers",           "TEX", "AL West",    "AL"),
    141: ("Toronto Blue Jays",       "TOR", "AL East",    "AL"),
    142: ("Minnesota Twins",         "MIN", "AL Central", "AL"),
    143: ("Philadelphia Phillies",   "PHI", "NL East",    "NL"),
    144: ("Atlanta Braves",          "ATL", "NL East",    "NL"),
    145: ("Chicago White Sox",       "CWS", "AL Central", "AL"),
    146: ("Miami Marlins",           "MIA", "NL East",    "NL"),
    147: ("New York Yankees",        "NYY", "AL East",    "AL"),
    158: ("Milwaukee Brewers",       "MIL", "NL Central", "NL"),
}

DIVISIONS = [
    "AL East", "AL Central", "AL West",
    "NL East", "NL Central", "NL West",
]
