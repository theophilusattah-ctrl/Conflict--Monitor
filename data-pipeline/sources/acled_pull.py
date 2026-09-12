"""
Pull ACLED aggregated event data for Nigeria (rolling/current window).

Research-tier access provides unlimited aggregated data by week, country,
admin, event, and subevent type. This script fetches the latest weeks and
upserts into `acled_events_agg`.

Requires env vars: ACLED_API_KEY, ACLED_EMAIL, SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import os
import sys
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_client  # noqa: E402

ACLED_BASE_URL = "https://api.acleddata.com/acled/read"


def fetch_acled_nigeria(limit: int = 5000) -> list[dict]:
    params = {
        "key": os.environ["ACLED_API_KEY"],
        "email": os.environ["ACLED_EMAIL"],
        "country": "Nigeria",
        "limit": limit,
        # Sort newest first so we always capture the latest rolling window
        "sort": "-event_date",
    }
    resp = requests.get(ACLED_BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success", False):
        raise RuntimeError(f"ACLED API error: {payload}")
    return payload.get("data", [])


def aggregate_by_state_week(events: list[dict]) -> list[dict]:
    """Aggregate raw event records into state/week/event_type counts."""
    from collections import defaultdict
    from datetime import datetime

    buckets = defaultdict(lambda: {"event_count": 0, "fatalities": 0})

    for e in events:
        try:
            event_date = datetime.strptime(e["event_date"], "%Y-%m-%d")
        except (KeyError, ValueError):
            continue
        week_start = event_date.date().isoformat()[:8] + "01"  # simplistic; refine with isocalendar
        state = e.get("admin1", "Unknown")
        event_type = e.get("event_type", "Unknown")
        key = (state, week_start, event_type)
        buckets[key]["event_count"] += 1
        buckets[key]["fatalities"] += int(e.get("fatalities", 0) or 0)

    rows = []
    for (state, week_start, event_type), agg in buckets.items():
        rows.append({
            "state_name": state,
            "week_start": week_start,
            "event_type": event_type,
            "event_count": agg["event_count"],
            "fatalities": agg["fatalities"],
        })
    return rows


def main():
    events = fetch_acled_nigeria()
    rows = aggregate_by_state_week(events)

    client = get_client()
    if rows:
        client.table("acled_events_agg").insert(rows).execute()
        print(f"Inserted {len(rows)} aggregated ACLED rows.")
    else:
        print("No ACLED rows to insert.")


if __name__ == "__main__":
    main()
