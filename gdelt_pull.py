"""
Pull GDELT events for Nigeria (15-minute update cycle) and compute a rolling
anomaly score (z-score of event volume + tone) per state.

Uses GDELT's DOC 2.0 API for near-real-time articles/events. For production
scale, consider switching to the GDELT BigQuery public dataset.

Requires env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_client, NIGERIA_STATES  # noqa: E402

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Rough keyword anchor per state can be refined; starting with a Nigeria-wide
# pull filtered by state name mention is a reasonable v1 approach.
KEYWORDS = ["violence", "attack", "clash", "conflict", "kidnap", "killed", "bandits"]


def fetch_gdelt_articles(state: str, hours_back: int = 1) -> list[dict]:
    query = f'({" OR ".join(KEYWORDS)}) "{state}" Nigeria'
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": 250,
        "timespan": f"{hours_back}h",
    }
    resp = requests.get(GDELT_DOC_API, params=params, timeout=30)
    resp.raise_for_status()
    try:
        return resp.json().get("articles", [])
    except ValueError:
        return []  # GDELT returns empty body on no-match sometimes


def compute_zscore(current: float, history: list[float]) -> float:
    if len(history) < 3:
        return 0.0
    mean = np.mean(history)
    std = np.std(history) or 1.0
    return (current - mean) / std


def main():
    client = get_client()
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=1)

    for state in NIGERIA_STATES:
        articles = fetch_gdelt_articles(state)
        event_count = len(articles)

        # Pull last 14 days of counts for this state to build a baseline
        history_resp = (
            client.table("gdelt_events")
            .select("event_count")
            .eq("state_name", state)
            .gte("event_date", (now - timedelta(days=14)).isoformat())
            .execute()
        )
        history_counts = [r["event_count"] for r in history_resp.data] if history_resp.data else []

        volume_z = compute_zscore(event_count, history_counts)
        is_anomaly = volume_z >= 2.0  # 2 std devs above rolling baseline

        client.table("gdelt_events").insert({
            "state_name": state,
            "event_date": now.isoformat(),
            "event_count": event_count,
            "avg_tone": None,  # populate if using GDELT GKG for tone data
        }).execute()

        client.table("gdelt_anomaly_scores").insert({
            "state_name": state,
            "window_start": window_start.isoformat(),
            "window_end": now.isoformat(),
            "volume_zscore": float(volume_z),
            "is_anomaly": bool(is_anomaly),
        }).execute()

        if is_anomaly:
            print(f"[ANOMALY] {state}: volume_zscore={volume_z:.2f} (count={event_count})")


if __name__ == "__main__":
    main()
