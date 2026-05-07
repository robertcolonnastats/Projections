"""
cache_manager.py
Manages disk-based JSON cache with midnight EST expiry.
Designed for Streamlit Cloud where background schedulers don't persist.
"""

import json
import os
import pandas as pd
from datetime import datetime, date
from zoneinfo import ZoneInfo

from utils.constants import CACHE_FILE, SIM_CACHE_FILE, CACHE_DIR

EST = ZoneInfo("America/New_York")


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_expiry_ts() -> float:
    """Return Unix timestamp of the next (or current) midnight EST."""
    now_est = datetime.now(EST)
    midnight_est = now_est.replace(hour=0, minute=0, second=0, microsecond=0)
    # If we're past midnight today, next expiry is tomorrow midnight
    # The cache written after midnight today expires at tomorrow midnight
    return midnight_est.timestamp()


def is_cache_valid(cache_key: str = "data") -> bool:
    """
    Returns True if the cache file exists and was written after today's midnight EST.
    """
    _ensure_cache_dir()
    path = CACHE_FILE if cache_key == "data" else SIM_CACHE_FILE

    if not os.path.exists(path):
        return False

    mtime = os.path.getmtime(path)
    today_midnight = get_cache_expiry_ts()

    return mtime >= today_midnight


def load_cache(cache_key: str = "data") -> dict | None:
    """Load cache from disk. Returns None if missing or invalid."""
    if not is_cache_valid(cache_key):
        return None

    path = CACHE_FILE if cache_key == "data" else SIM_CACHE_FILE
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def save_cache(payload: dict, cache_key: str = "data"):
    """Save payload dict to disk cache."""
    _ensure_cache_dir()
    path = CACHE_FILE if cache_key == "data" else SIM_CACHE_FILE
    try:
        with open(path, "w") as f:
            json.dump(payload, f, default=str)
    except Exception as e:
        print(f"Warning: cache write failed: {e}")


def dataframe_to_cache(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to JSON-serializable list of dicts."""
    return df.to_dict(orient="records")


def cache_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """Restore DataFrame from cached list of dicts."""
    return pd.DataFrame(records)


def get_last_updated() -> str:
    """Return human-readable string of when data was last refreshed."""
    if not os.path.exists(CACHE_FILE):
        return "Never"
    mtime = os.path.getmtime(CACHE_FILE)
    dt = datetime.fromtimestamp(mtime, tz=EST)
    return dt.strftime("%B %d, %Y at %I:%M %p EST")


def get_season_state() -> str:
    """
    Returns one of: 'offseason', 'pre_deadline', 'deadline_ramp', 'post_deadline'
    Used to control app behavior throughout the year.
    """
    from utils.constants import OPENING_DAY, WORLD_SERIES_END_APPROX, TRADE_DEADLINE, DEADLINE_RAMP_START

    today = date.today()
    opening   = date.fromisoformat(OPENING_DAY)
    ws_end    = date.fromisoformat(WORLD_SERIES_END_APPROX)
    deadline  = date.fromisoformat(TRADE_DEADLINE)
    ramp_start = date.fromisoformat(DEADLINE_RAMP_START)

    if today < opening or today > ws_end:
        return "offseason"
    elif today > deadline:
        return "post_deadline"
    elif today >= ramp_start:
        return "deadline_ramp"
    else:
        return "pre_deadline"


def get_deadline_ramp_factor() -> float:
    """
    Returns a float 0.0 → 1.0 representing how far through the July ramp we are.
    0.0 = July 1 (no adjustment yet)
    1.0 = July 31+ (full adjustment)
    """
    from utils.constants import TRADE_DEADLINE, DEADLINE_RAMP_START

    today      = date.today()
    ramp_start = date.fromisoformat(DEADLINE_RAMP_START)
    deadline   = date.fromisoformat(TRADE_DEADLINE)

    state = get_season_state()
    if state in ("offseason", "pre_deadline"):
        return 0.0
    if state == "post_deadline":
        return 1.0

    # Linear interpolation across July
    total_days   = (deadline - ramp_start).days
    elapsed_days = (today - ramp_start).days
    factor = elapsed_days / max(total_days, 1)
    return round(min(max(factor, 0.0), 1.0), 4)
