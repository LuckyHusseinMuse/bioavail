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
        _pool = ConnectionPool(url, min_size=1, max_size=5, open=True, kwargs={"row_factory": dict_row})


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
