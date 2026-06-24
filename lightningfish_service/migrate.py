#!/usr/bin/env python3
"""
Run once to create the Postgres schema.
Requires DATABASE_URL environment variable (Neon connection string).

Usage: python -m lightningfish_service.migrate
"""
from __future__ import annotations
import os
import psycopg2

_SQL = """
CREATE TABLE IF NOT EXISTS simulations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT NOT NULL,
    domain_id   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    seed_json   JSONB,
    result_json JSONB,
    n_agents    INT NOT NULL DEFAULT 500,
    n_rounds    INT NOT NULL DEFAULT 12,
    cost_usd    DECIMAL(10,6) DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS round_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulation_id   UUID NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    round_number    INT NOT NULL,
    event_json      JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    budget_usd  DECIMAL(10,4) DEFAULT 2.00,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_simulations_user_id    ON simulations(user_id);
CREATE INDEX IF NOT EXISTS idx_simulations_created_at ON simulations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_round_events_sim_id    ON round_events(simulation_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash          ON api_keys(key_hash);
"""


def main() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(_SQL)
    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
