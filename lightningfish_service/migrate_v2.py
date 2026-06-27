#!/usr/bin/env python3
"""
Schema migration v2 — adds model and agent_config_json columns.
Safe to run multiple times (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).

Usage: python -m lightningfish_service.migrate_v2
"""
from __future__ import annotations

import os

import psycopg2

_SQL = """
ALTER TABLE simulations ADD COLUMN IF NOT EXISTS model TEXT DEFAULT 'claude-sonnet-4-6';
ALTER TABLE simulations ADD COLUMN IF NOT EXISTS agent_config_json JSONB;
"""


def main() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(_SQL)
    conn.commit()
    conn.close()
    print("Migration v2 complete.")


if __name__ == "__main__":
    main()
