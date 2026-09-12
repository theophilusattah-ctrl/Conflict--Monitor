# Conflict Monitor — Nigeria Early Warning System

Early warning system combining verified conflict data (ACLED), real-time
news signal (GDELT), rainfall anomalies (Open-Meteo), and a static
flood/vulnerability index (Sentinel-1 SAR + AHP) to flag violent conflict
risk across Nigerian states.

## Architecture

```
Data Sources (ACLED, GDELT, Open-Meteo, Sentinel-1)
        │
        ▼  (GitHub Actions, scheduled)
data-pipeline/  →  Supabase (Postgres + PostGIS)
        │
        ▼
frontend/  (choropleth map, risk tables)
        │
        ▼
alerts/  →  Resend (email on threshold crossed)
```

## Structure

- `data-pipeline/sources/` — pull scripts for each data source
- `data-pipeline/alerts/` — threshold logic + Resend email dispatch
- `supabase/schema.sql` — database schema (run once in Supabase SQL editor)
- `frontend/` — static map dashboard (Leaflet, deploys to GitHub Pages/Vercel)
- `.github/workflows/` — scheduled jobs

## Setup

1. Create a free Supabase project. Run `supabase/schema.sql` in the SQL editor.
2. Add these repo secrets (Settings → Secrets and variables → Actions):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `ACLED_API_KEY` / `ACLED_EMAIL`
   - `RESEND_API_KEY`
   - `ALERT_EMAIL_TO`
3. Push to GitHub. Workflows start running on schedule automatically.
4. Deploy `frontend/` to GitHub Pages (Settings → Pages → source: `/frontend`)
   or connect the repo to Vercel.

## Data windows

- ACLED aggregated (current, rolling) — live feature input
- ACLED event-level (>12 months old) — model training/labels
- GDELT — 15-minute pull, rolling z-score anomaly detection
- Open-Meteo — hourly rainfall, anomaly vs. seasonal baseline
- Sentinel-1 / AHP FVI — static, recomputed periodically (manual trigger)

## Status

Prototype scaffold — data pipeline and alert logic are functional stubs.
Fill in AHP weights and model training once historical ACLED data is pulled.
