"""Database access: engine, safe execution, and JSON-safe row serialisation."""
from __future__ import annotations

import datetime as dt
import decimal
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from .config import get_settings


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    return create_engine(s.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return v if v == v and v not in (float("inf"), float("-inf")) else None
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return v.total_seconds()
    if isinstance(v, (uuid.UUID, bytes, memoryview)):
        return str(v) if not isinstance(v, (bytes, memoryview)) else "<binary>"
    return str(v)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool = False
    elapsed_ms: float = 0.0
    column_types: list[str] = field(default_factory=list)


class QueryError(Exception):
    """Raised when the database rejects or fails a query. Message is safe to show the model."""


def run_readonly(sql: str, row_limit: int | None = None, timeout_ms: int | None = None,
                 engine: Engine | None = None) -> QueryResult:
    """Execute one statement in a READ ONLY transaction with a statement timeout.

    This is the last line of defence: the validator already restricts the SQL to
    SELECT, and the connecting role should itself be read-only.
    """
    s = get_settings()
    row_limit = row_limit or s.row_limit
    timeout_ms = timeout_ms or s.statement_timeout_ms
    engine = engine or get_engine()
    t0 = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
            res = conn.exec_driver_sql(sql)
            cols = list(res.keys())
            fetched = res.fetchmany(row_limit + 1)
            conn.rollback()
    except Exception as e:  # noqa: BLE001 - surface any driver error to the repair loop
        orig = getattr(e, "orig", e)
        msg = str(orig).strip().splitlines()[0] if str(orig).strip() else type(orig).__name__
        raise QueryError(msg) from e
    truncated = len(fetched) > row_limit
    rows = [[jsonable(v) for v in r] for r in fetched[:row_limit]]
    return QueryResult(columns=cols, rows=rows, truncated=truncated,
                       elapsed_ms=(time.perf_counter() - t0) * 1000)
