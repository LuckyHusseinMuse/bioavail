"""Database connection pool (Tiger Data / TimescaleDB)."""
from __future__ import annotations

from collections.abc import Iterator

import psycopg
from fastapi import HTTPException, status
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def open_pool(url: str | None) -> None:
    global _pool
    if url and _pool is None:
        # Cloud databases close idle connections. Check each one before use, recycle idle ones, and keep TCP alive,
        # so the first request after a quiet spell never gets a dead connection.
        _pool = ConnectionPool(
            url, min_size=1, max_size=5, open=True, max_idle=120, max_lifetime=1800,
            check=ConnectionPool.check_connection,
            kwargs={"row_factory": dict_row, "keepalives": 1, "keepalives_idle": 30,
                    "keepalives_interval": 10, "keepalives_count": 3, "connect_timeout": 15},
        )


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_conn() -> Iterator[psycopg.Connection]:
    if _pool is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    with _pool.connection() as conn:
        yield conn


def pool() -> ConnectionPool:
    if _pool is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    return _pool
