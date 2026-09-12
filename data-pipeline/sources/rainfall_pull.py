"""
Pull live rainfall data from Open-Meteo per Nigerian state (using a
representative lat/lon per state capital) and compute anomaly vs. a
30-day rolling baseline.

No API key required for Open-Meteo.
Requires env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY
"""
import os
import sys
from datetime import date, timedelta

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_client  # noqa: E402

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# State capital coordinates (approximate) — replace/expand with full 37-state
# list; a handful of high-risk states included here to start.
STATE_COORDS = {
    "Benue": (7.7322, 8.5391),      # Makurdi
    "Plateau": (9.8965, 8.8583),    # Jos
    "Borno": (11.8333, 13.1500),    # Maiduguri
    "Zamfara": (12.1704, 6.2650),   # Gusau
    "Kaduna": (10.5222, 7.4383),
    "Taraba": (8.8833, 11.3667),    # Jalingo
    "Adamawa": (9.3265, 12.3984),   # Yola
    "Niger": (9.6139, 6.5569),      # Minna
}


def fetch_rainfall(lat: float, lon: float) -> float:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum",
        "timezone": "Africa/Lagos",
        "past_days": 1,
        "forecast_days": 0,
    }
    resp = requests.get(OPEN_METEO_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    values = data.get("daily", {}).get("precipitation_sum", [])
    return values[0] if values else 0.0


def get_baseline(client, state: str, days: int = 30) -> float:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    resp = (
        client.table("rainfall_readings")
        .select("rainfall_mm")
        .eq("state_name", state)
        .gte("reading_date", cutoff)
        .execute()
    )
    vals = [r["rainfall_mm"] for r in resp.data] if resp.data else []
    return sum(vals) / len(vals) if vals else 0.0


def main():
    client = get_client()
    today = date.today().isoformat()

    for state, (lat, lon) in STATE_COORDS.items():
        rainfall_mm = fetch_rainfall(lat, lon)
        baseline_mm = get_baseline(client, state)
        anomaly_ratio = (rainfall_mm / baseline_mm) if baseline_mm > 0 else 1.0

        client.table("rainfall_readings").insert({
            "state_name": state,
            "reading_date": today,
            "rainfall_mm": rainfall_mm,
            "baseline_mm": baseline_mm,
            "anomaly_ratio": anomaly_ratio,
        }).execute()

        print(f"{state}: {rainfall_mm}mm (baseline {baseline_mm:.1f}mm, ratio {anomaly_ratio:.2f})")


if __name__ == "__main__":
    main()
