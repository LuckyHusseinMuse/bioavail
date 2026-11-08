-- Absorb database schema for Tiger Data (TimescaleDB on PostgreSQL).
-- Idempotent: safe to run repeatedly. Applied by `python -m pipeline.load_db`.
--
-- Reference tables mirror the curated CSVs: key columns are typed, and the full CSV row is kept in `data`
-- so new CSV columns never need a schema change.
-- Time-series tables are hypertables. TimescaleDB requires the time column in every primary key, so meals
-- and results are keyed by (meal_id, eaten_at). No foreign keys point at hypertables; the API keeps them consistent.

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ===================================================================== reference data (replaced on each load)

CREATE TABLE IF NOT EXISTS foods (
    food_code       text PRIMARY KEY,
    name            text NOT NULL,
    category        text NOT NULL,
    iron_mg         numeric,          -- per 100 g
    calcium_mg      numeric,          -- per 100 g
    vitamin_c_mg    numeric,          -- per 100 g
    is_mfp          boolean NOT NULL,
    mfp_fraction    numeric NOT NULL,
    is_drink        boolean NOT NULL,
    serving_g       numeric NOT NULL,
    serving_label   text,
    data            jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS foods_name_trgm ON foods (lower(name));

CREATE TABLE IF NOT EXISTS food_inhibitors (
    food_code                   text PRIMARY KEY,
    beverage_class              text,
    phytate_mg_per_100g         numeric,
    polyphenols_mg_per_serving  numeric,
    specific_modifier_id        text,
    data_status                 text,
    data                        jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS absorption_baselines (
    baseline_id     text PRIMARY KEY,
    nutrient_form   text,
    value_pct       numeric,
    lower_pct       numeric,
    upper_pct       numeric,
    active          boolean NOT NULL,
    human_verified  boolean NOT NULL,
    data            jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS absorption_modifiers (
    modifier_id     text PRIMARY KEY,
    name            text,
    nutrient_form   text,
    direction       text,
    effect_value    numeric,
    effect_lower    numeric,
    effect_upper    numeric,
    active          boolean NOT NULL,
    human_verified  boolean NOT NULL,
    data            jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS interaction_rules (
    rule_id         text PRIMARY KEY,
    trigger_entity  text,
    conflict_group  text,
    modifier_id     text,
    active          boolean NOT NULL,
    human_verified  boolean NOT NULL,
    data            jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS engine_rule_evidence (
    rule_evidence_id    text PRIMARY KEY,
    engine_entity_type  text,
    engine_entity_id    text,
    paper_id            text,
    evidence_role       text,
    active              boolean NOT NULL,
    human_verified      boolean NOT NULL,
    data                jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS evidence_entity_idx ON engine_rule_evidence (engine_entity_id);

CREATE TABLE IF NOT EXISTS evidence_papers (
    paper_id            text PRIMARY KEY,
    title               text,
    year                int,
    citation_verified   boolean,
    data                jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS engine_assumptions (
    assumption_id   text PRIMARY KEY,
    name            text,
    value           numeric,
    active          boolean NOT NULL,
    data            jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS reference_intakes (
    sex                         text NOT NULL,
    age_min                     int NOT NULL,
    age_max                     int NOT NULL,
    iron_rni_mg_day             numeric NOT NULL,
    absorbed_target_mg_day      numeric NOT NULL,
    reference_day_fraction_pct  numeric NOT NULL,
    PRIMARY KEY (sex, age_min)
);

CREATE TABLE IF NOT EXISTS validation_meals (
    validation_id   text PRIMARY KEY,
    paper_id        text,
    split           text NOT NULL,
    measure         text NOT NULL,
    measured_value  numeric,
    data            jsonb NOT NULL
);

-- ===================================================================== users and settings

CREATE TABLE IF NOT EXISTS users (
    user_id         text PRIMARY KEY,           -- Auth0 subject (sub claim)
    sex             text CHECK (sex IN ('male', 'female')),
    birth_year      int,
    diet_type       text,                       -- omnivore | vegetarian | vegan | pescatarian
    preferences     jsonb NOT NULL DEFAULT '{}',
    timezone        text NOT NULL DEFAULT 'Europe/London',
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alert_preferences (
    user_id             text PRIMARY KEY REFERENCES users (user_id) ON DELETE CASCADE,
    enabled             boolean NOT NULL DEFAULT true,
    enabled_types       text[] NOT NULL DEFAULT ARRAY['conflict', 'data_gap', 'timing', 'shortfall', 'weekly_pattern'],
    quiet_start         time,
    quiet_end           time,
    daily_limit         int NOT NULL DEFAULT 3,
    push_subscription   jsonb,
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- ===================================================================== time series (hypertables)

CREATE TABLE IF NOT EXISTS meals (
    meal_id     uuid NOT NULL,
    user_id     text NOT NULL,
    eaten_at    timestamptz NOT NULL,
    items       jsonb NOT NULL,                 -- [{food_code, grams, offset_min}]
    source      text NOT NULL CHECK (source IN ('photo', 'text', 'manual', 'seed')),
    note        text,
    intake      jsonb,                          -- Gemini drafts and review, for audit
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (meal_id, eaten_at)
);
SELECT create_hypertable('meals', by_range('eaten_at', INTERVAL '7 days'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS meals_user_time ON meals (user_id, eaten_at DESC);

CREATE TABLE IF NOT EXISTS meal_results (
    meal_id                 uuid NOT NULL,
    eaten_at                timestamptz NOT NULL,
    user_id                 text NOT NULL,
    iron_mg                 numeric NOT NULL,
    absorbed_mg             numeric NOT NULL,
    potential_absorbed_mg   numeric NOT NULL,
    fractional_pct          numeric,
    share_of_potential_pct  numeric,
    range_low_mg            numeric,
    range_high_mg           numeric,
    conflict_count          int NOT NULL DEFAULT 0,
    conflict_rule_ids       text[] NOT NULL DEFAULT '{}',
    contributions           jsonb NOT NULL,
    conflicts               jsonb NOT NULL,
    data_gaps               jsonb NOT NULL,
    engine_version          text NOT NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (meal_id, eaten_at)
);
SELECT create_hypertable('meal_results', by_range('eaten_at', INTERVAL '7 days'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS meal_results_user_time ON meal_results (user_id, eaten_at DESC);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id      uuid NOT NULL,
    user_id     text,
    agent       text NOT NULL,                  -- intake | analyst | fix | chat
    started_at  timestamptz NOT NULL,
    finished_at timestamptz,
    outcome     text,                           -- ok | error | needs_confirmation
    detail      jsonb,
    PRIMARY KEY (run_id, started_at)
);
SELECT create_hypertable('agent_runs', by_range('started_at', INTERVAL '7 days'), if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS tool_calls (
    run_id          uuid NOT NULL,
    called_at       timestamptz NOT NULL,
    user_id         text,
    tool            text NOT NULL,
    args            jsonb,
    result_summary  jsonb,
    ok              boolean NOT NULL,
    duration_ms     int
);
SELECT create_hypertable('tool_calls', by_range('called_at', INTERVAL '7 days'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS tool_calls_run ON tool_calls (run_id, called_at);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id  uuid NOT NULL,
    user_id     text NOT NULL,
    sent_at     timestamptz NOT NULL,
    role        text NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content     text NOT NULL,
    run_id      uuid,
    PRIMARY KEY (message_id, sent_at)
);
SELECT create_hypertable('chat_messages', by_range('sent_at', INTERVAL '30 days'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS chat_user_time ON chat_messages (user_id, sent_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        uuid NOT NULL,
    user_id         text NOT NULL,
    created_at      timestamptz NOT NULL,
    type            text NOT NULL CHECK (type IN ('conflict', 'data_gap', 'timing', 'shortfall', 'weekly_pattern')),
    scheduled_for   timestamptz,
    sent_at         timestamptz,
    read_at         timestamptz,
    dismissed_at    timestamptz,
    message         text NOT NULL,
    source_rule_id  text,
    meal_id         uuid,
    data            jsonb,
    PRIMARY KEY (alert_id, created_at)
);
SELECT create_hypertable('alerts', by_range('created_at', INTERVAL '30 days'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS alerts_user_time ON alerts (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS alerts_due ON alerts (scheduled_for) WHERE sent_at IS NULL;

-- ===================================================================== daily rollup (continuous aggregate)
-- Days are London calendar days. Real-time aggregation includes meals logged since the last refresh.

CREATE MATERIALIZED VIEW IF NOT EXISTS daily_iron
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    time_bucket(INTERVAL '1 day', eaten_at, 'Europe/London') AS day,
    user_id,
    count(*)                        AS meals,
    sum(iron_mg)                    AS iron_mg,
    sum(absorbed_mg)                AS absorbed_mg,
    sum(potential_absorbed_mg)      AS potential_absorbed_mg,
    sum(conflict_count)             AS conflict_count
FROM meal_results
GROUP BY day, user_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('daily_iron',
    start_offset      => INTERVAL '35 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists     => TRUE);

-- Weekly pattern alerts: how often each conflict rule fired per user per day (plain view over meal_results).
CREATE OR REPLACE VIEW conflict_days AS
SELECT
    user_id,
    time_bucket(INTERVAL '1 day', eaten_at, 'Europe/London') AS day,
    unnest(conflict_rule_ids) AS rule_id
FROM meal_results;
