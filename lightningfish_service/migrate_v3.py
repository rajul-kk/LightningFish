from __future__ import annotations
"""Add base_url column to simulations for local LLM support."""
import os
import psycopg2


_SQL = """
ALTER TABLE simulations ADD COLUMN IF NOT EXISTS base_url TEXT;
"""


def migrate() -> None:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(_SQL)
        conn.commit()
    finally:
        conn.close()
    print("migrate_v3: base_url column added")


if __name__ == "__main__":
    migrate()
