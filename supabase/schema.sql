-- Conflict Monitor schema
-- Run this once in the Supabase SQL editor (enables PostGIS first)

create extension if not exists postgis;

-- Nigerian states/admin boundaries (populate once from a shapefile/GeoJSON source)
create table if not exists admin_regions (
    id serial primary key,
    state_name text not null unique,
    lga_name text,
    geom geometry(MultiPolygon, 4326)
);

-- Rolling ACLED events (aggregated, current window)
create table if not exists acled_events_agg (
    id serial primary key,
    state_name text not null,
    week_start date not null,
    event_type text,
    event_count int default 0,
    fatalities int default 0,
    population_exposure numeric,
    pulled_at timestamptz default now()
);

-- Historical ACLED events (event-level, >12mo, used for model training)
create table if not exists acled_events_historical (
    id serial primary key,
    acled_event_id text unique,
    event_date date,
    state_name text,
    lga_name text,
    event_type text,
    sub_event_type text,
    actor1 text,
    actor2 text,
    fatalities int,
    latitude double precision,
    longitude double precision,
    notes text
);

-- GDELT rolling events / tone (fast trigger layer)
create table if not exists gdelt_events (
    id serial primary key,
    state_name text,
    event_date timestamptz,
    avg_tone numeric,
    event_count int,
    goldstein_scale numeric,
    source_url text,
    pulled_at timestamptz default now()
);

create table if not exists gdelt_anomaly_scores (
    id serial primary key,
    state_name text not null,
    window_start timestamptz not null,
    window_end timestamptz not null,
    volume_zscore numeric,
    tone_zscore numeric,
    is_anomaly boolean default false,
    computed_at timestamptz default now()
);

-- Rainfall (live trigger layer)
create table if not exists rainfall_readings (
    id serial primary key,
    state_name text not null,
    reading_date date not null,
    rainfall_mm numeric,
    baseline_mm numeric,
    anomaly_ratio numeric,
    pulled_at timestamptz default now()
);

-- Static vulnerability layer (AHP + SAR-derived FVI)
create table if not exists vulnerability_fvi (
    id serial primary key,
    state_name text not null,
    settlement_name text,
    flood_exposure_score numeric,
    ahp_composite_score numeric,
    risk_tier text check (risk_tier in ('High','Moderate','Watch','Normal')),
    computed_at timestamptz default now()
);

-- Region/state risk summary (rendered on dashboard)
create table if not exists region_risk_summary (
    id serial primary key,
    state_name text not null unique,
    event_frequency_score numeric,
    severity_score numeric,
    composite_risk numeric,
    risk_tier text,
    updated_at timestamptz default now()
);

-- Alert log (avoid duplicate emails)
create table if not exists alert_log (
    id serial primary key,
    alert_type text not null, -- 'rainfall_threshold' | 'event_spike' | 'new_event_type'
    state_name text,
    detail text,
    sent_at timestamptz default now()
);

create index if not exists idx_acled_agg_state_week on acled_events_agg(state_name, week_start);
create index if not exists idx_gdelt_state_date on gdelt_events(state_name, event_date);
create index if not exists idx_rainfall_state_date on rainfall_readings(state_name, reading_date);
