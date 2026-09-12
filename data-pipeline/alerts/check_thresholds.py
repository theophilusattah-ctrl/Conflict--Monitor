"""
Check rainfall and GDELT anomaly thresholds; send email alerts via Resend
when a threshold is crossed. Deduplicates using `alert_log` so the same
condition doesn't spam repeated emails within a cooldown window.

Requires env vars:
  SUPABASE_URL, SUPABASE_SERVICE_KEY, RESEND_API_KEY, ALERT_EMAIL_TO
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_client  # noqa: E402

RESEND_API_URL = "https://api.resend.com/emails"
RAINFALL_ANOMALY_THRESHOLD = 2.0   # ratio vs. 30-day baseline
COOLDOWN_HOURS = 12                # don't re-alert same state/type within this window


def already_alerted(client, alert_type: str, state: str) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=COOLDOWN_HOURS)).isoformat()
    resp = (
        client.table("alert_log")
        .select("id")
        .eq("alert_type", alert_type)
        .eq("state_name", state)
        .gte("sent_at", cutoff)
        .execute()
    )
    return bool(resp.data)


def send_email(subject: str, body: str):
    headers = {
        "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": "Conflict Monitor <alerts@yourdomain.com>",  # replace with verified Resend domain
        "to": [os.environ["ALERT_EMAIL_TO"]],
        "subject": subject,
        "text": body,
    }
    resp = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()


def check_rainfall(client):
    today = datetime.now(timezone.utc).date().isoformat()
    resp = client.table("rainfall_readings").select("*").eq("reading_date", today).execute()
    for row in resp.data or []:
        if row["anomaly_ratio"] and row["anomaly_ratio"] >= RAINFALL_ANOMALY_THRESHOLD:
            state = row["state_name"]
            if already_alerted(client, "rainfall_threshold", state):
                continue
            send_email(
                subject=f"[Conflict Monitor] Rainfall anomaly — {state}",
                body=(
                    f"Rainfall in {state} is {row['rainfall_mm']}mm today, "
                    f"{row['anomaly_ratio']:.1f}x the 30-day baseline "
                    f"({row['baseline_mm']:.1f}mm). This may elevate displacement/"
                    f"resource-conflict risk — review the dashboard."
                ),
            )
            client.table("alert_log").insert({
                "alert_type": "rainfall_threshold",
                "state_name": state,
                "detail": f"ratio={row['anomaly_ratio']:.2f}",
            }).execute()
            print(f"Sent rainfall alert: {state}")


def check_gdelt_spikes(client):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = (
        client.table("gdelt_anomaly_scores")
        .select("*")
        .eq("is_anomaly", True)
        .gte("window_end", cutoff)
        .execute()
    )
    for row in resp.data or []:
        state = row["state_name"]
        if already_alerted(client, "event_spike", state):
            continue
        send_email(
            subject=f"[Conflict Monitor] Event spike detected — {state}",
            body=(
                f"GDELT event volume in {state} is {row['volume_zscore']:.1f} standard "
                f"deviations above its 14-day baseline (window ending {row['window_end']}). "
                f"This is a fast-signal trigger — cross-check against ACLED once verified "
                f"data is available."
            ),
        )
        client.table("alert_log").insert({
            "alert_type": "event_spike",
            "state_name": state,
            "detail": f"volume_zscore={row['volume_zscore']:.2f}",
        }).execute()
        print(f"Sent event-spike alert: {state}")


def main():
    client = get_client()
    check_rainfall(client)
    check_gdelt_spikes(client)


if __name__ == "__main__":
    main()
