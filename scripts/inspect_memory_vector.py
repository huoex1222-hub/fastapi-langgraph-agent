"""Inspect long-term memories stored by mem0 in pgvector.

Usage:
    uv run python scripts/inspect_memory_vector.py
    uv run python scripts/inspect_memory_vector.py <memory-id>
    uv run python scripts/inspect_memory_vector.py <memory-id-prefix>

Without an id it lists the most recent memories. With an id it prints the
payload, vector statistics, and the raw vector text.
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# The zh-CN console defaults to GBK; force UTF-8 so JSONB text renders correctly.
for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

from app.core.config import settings  # noqa: E402

TABLE = settings.LONG_TERM_MEMORY_COLLECTION_NAME


def connect() -> psycopg.Connection[Any]:
    """Open a connection to the application database."""
    return psycopg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
    )


def list_memories(limit: int) -> None:
    """Print the most recent memories so an id can be chosen."""
    query = sql.SQL(
        """
        SELECT id,
               payload->>'user_id',
               payload->>'created_at',
               payload->>'data'
        FROM {}
        ORDER BY payload->>'created_at' DESC NULLS LAST
        LIMIT %s
        """
    ).format(sql.Identifier(TABLE))

    with connect() as conn, conn.cursor() as cur:
        cur.execute(query, (limit,))
        rows = cur.fetchall()

    if not rows:
        print(f"No rows in {TABLE}.")
        return

    print(f"Recent memories in {TABLE} ({len(rows)}):")
    print(f"{'ID':38} {'USER':6} {'CREATED_AT':26} DATA")
    for memory_id, user_id, created_at, data in rows:
        preview = (data or "").replace("\n", " ")
        if len(preview) > 70:
            preview = preview[:67] + "..."
        print(f"{memory_id!s:38} {user_id or '-':6} {(created_at or '-'):26} {preview}")

    print("\nInspect one with:")
    print("  uv run python scripts/inspect_memory_vector.py <id>")


def parse_vector(text: str) -> list[float]:
    """Parse pgvector's text representation (a JSON array) into floats."""
    return [float(value) for value in json.loads(text)]


def show_memory(memory_id: str) -> int:
    """Print payload and raw vector for a memory id or id prefix."""
    base_query = sql.SQL("SELECT id, vector::text, payload FROM {}").format(sql.Identifier(TABLE))

    with connect() as conn, conn.cursor() as cur:
        cur.execute(base_query + sql.SQL(" WHERE id::text = %s"), (memory_id,))
        row = cur.fetchone()

        if row is None:
            cur.execute(base_query + sql.SQL(" WHERE id::text LIKE %s LIMIT 1"), (f"{memory_id}%",))
            row = cur.fetchone()

    if row is None:
        print(f"Memory id not found: {memory_id}")
        return 1

    stored_id, vector_text, payload_value = row
    payload: dict[str, Any] = payload_value or {}
    raw_vector: str = vector_text or "[]"
    values = parse_vector(raw_vector)

    print(f"id:          {stored_id}")
    print(f"user_id:     {payload.get('user_id', '-')}")
    print(f"created_at:  {payload.get('created_at', '-')}")
    print(f"updated_at:  {payload.get('updated_at', '-')}")
    print(f"data:        {payload.get('data', '-')}")
    print(f"hash:        {payload.get('hash', '-')}")
    print(f"dimensions:  {len(values)}")

    if values:
        norm = math.sqrt(sum(value * value for value in values))
        print(f"min:         {min(values):.8f}")
        print(f"max:         {max(values):.8f}")
        print(f"mean:        {sum(values) / len(values):.8f}")
        print(f"l2_norm:     {norm:.8f}")

    print("\npayload:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("\nvector (raw):")
    print(raw_vector)
    return 0


def main() -> int:
    """Parse arguments and run listing or inspection mode."""
    parser = argparse.ArgumentParser(description="Inspect pgvector long-term memories stored by mem0.")
    parser.add_argument("id", nargs="?", help="Memory UUID (a prefix is also accepted)")
    parser.add_argument("--limit", type=int, default=10, help="Number of recent memories to list (default: 10)")
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    try:
        if args.id:
            return show_memory(args.id)
        list_memories(args.limit)
        return 0
    except psycopg.Error as exc:
        print(f"Database error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
