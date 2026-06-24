from __future__ import annotations
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager


def _connect():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


@contextmanager
def _cursor():
    conn = _connect()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_simulation(
    sim_id: str,
    user_id: str,
    domain_id: str,
    seed_json: dict,
    n_agents: int,
    n_rounds: int,
) -> None:
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO simulations (id, user_id, domain_id, status, seed_json, n_agents, n_rounds)
            VALUES (%s, %s, %s, 'pending', %s, %s, %s)
            """,
            (sim_id, user_id, domain_id, json.dumps(seed_json), n_agents, n_rounds),
        )


def get_simulation(sim_id: str) -> dict | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM simulations WHERE id = %s", (sim_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def update_simulation_status(sim_id: str, status: str) -> None:
    with _cursor() as cur:
        cur.execute(
            "UPDATE simulations SET status = %s WHERE id = %s", (status, sim_id)
        )


def update_simulation_result(sim_id: str, result_json: dict, cost_usd: float) -> None:
    with _cursor() as cur:
        cur.execute(
            """
            UPDATE simulations
            SET status = 'complete', result_json = %s, cost_usd = %s
            WHERE id = %s
            """,
            (json.dumps(result_json), cost_usd, sim_id),
        )


def insert_round_event(sim_id: str, round_number: int, event_json: dict) -> None:
    with _cursor() as cur:
        cur.execute(
            """
            INSERT INTO round_events (simulation_id, round_number, event_json)
            VALUES (%s, %s, %s)
            """,
            (sim_id, round_number, json.dumps(event_json)),
        )


def get_round_events(sim_id: str) -> list[dict]:
    with _cursor() as cur:
        cur.execute(
            "SELECT * FROM round_events WHERE simulation_id = %s ORDER BY round_number",
            (sim_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_simulations_by_user(user_id: str, limit: int = 50) -> list[dict]:
    with _cursor() as cur:
        cur.execute(
            "SELECT * FROM simulations WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
            (user_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def create_api_key(key_id: str, user_id: str, key_hash: str, name: str) -> None:
    with _cursor() as cur:
        cur.execute(
            "INSERT INTO api_keys (id, user_id, key_hash, name) VALUES (%s, %s, %s, %s)",
            (key_id, user_id, key_hash, name),
        )


def get_api_key(key_hash: str) -> dict | None:
    with _cursor() as cur:
        cur.execute("SELECT * FROM api_keys WHERE key_hash = %s", (key_hash,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_api_keys(user_id: str) -> list[dict]:
    with _cursor() as cur:
        cur.execute(
            "SELECT id, name, created_at, last_used_at FROM api_keys WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def delete_api_key(key_id: str, user_id: str) -> None:
    with _cursor() as cur:
        cur.execute(
            "DELETE FROM api_keys WHERE id = %s AND user_id = %s", (key_id, user_id)
        )
