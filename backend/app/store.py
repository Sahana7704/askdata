"""Tiny SQLite store for query history and evaluation runs (AskData's own state, not the target DB)."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any

from .config import get_settings

_lock = threading.Lock()


@contextmanager
def _conn():
    con = sqlite3.connect(get_settings().state_db_path, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init() -> None:
    with _lock, _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS history (
            id TEXT PRIMARY KEY, created_at REAL, question TEXT, status TEXT, response_json TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS eval_runs (
            id TEXT PRIMARY KEY, created_at REAL, status TEXT, progress_json TEXT, result_json TEXT)""")


def add_history(response: dict[str, Any]) -> str:
    hid = uuid.uuid4().hex[:12]
    with _lock, _conn() as c:
        c.execute("INSERT INTO history VALUES (?,?,?,?,?)",
                  (hid, time.time(), response["question"], response["status"], json.dumps(response)))
    return hid


def list_history(limit: int = 20) -> list[dict[str, Any]]:
    with _lock, _conn() as c:
        rows = c.execute("SELECT id, created_at, question, status FROM history ORDER BY created_at DESC LIMIT ?",
                         (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_history(hid: str) -> dict[str, Any] | None:
    with _lock, _conn() as c:
        r = c.execute("SELECT response_json FROM history WHERE id=?", (hid,)).fetchone()
    return json.loads(r["response_json"]) if r else None


def create_eval(progress: dict[str, Any]) -> str:
    rid = uuid.uuid4().hex[:12]
    with _lock, _conn() as c:
        c.execute("INSERT INTO eval_runs VALUES (?,?,?,?,?)", (rid, time.time(), "running", json.dumps(progress), None))
    return rid


def update_eval(rid: str, *, status: str | None = None, progress: dict | None = None, result: dict | None = None) -> None:
    with _lock, _conn() as c:
        if status:
            c.execute("UPDATE eval_runs SET status=? WHERE id=?", (status, rid))
        if progress is not None:
            c.execute("UPDATE eval_runs SET progress_json=? WHERE id=?", (json.dumps(progress), rid))
        if result is not None:
            c.execute("UPDATE eval_runs SET result_json=? WHERE id=?", (json.dumps(result), rid))


def _eval_row(r: sqlite3.Row) -> dict[str, Any]:
    return {"id": r["id"], "created_at": r["created_at"], "status": r["status"],
            "progress": json.loads(r["progress_json"] or "{}"),
            "result": json.loads(r["result_json"]) if r["result_json"] else None}


def get_eval(rid: str) -> dict[str, Any] | None:
    with _lock, _conn() as c:
        r = c.execute("SELECT * FROM eval_runs WHERE id=?", (rid,)).fetchone()
    return _eval_row(r) if r else None


def latest_eval(only_complete: bool = False) -> dict[str, Any] | None:
    q = "SELECT * FROM eval_runs " + ("WHERE status='complete' " if only_complete else "") + "ORDER BY created_at DESC LIMIT 1"
    with _lock, _conn() as c:
        r = c.execute(q).fetchone()
    return _eval_row(r) if r else None


def mark_stale_runs_failed() -> None:
    """A run left 'running' by a previous process can never finish."""
    with _lock, _conn() as c:
        c.execute("UPDATE eval_runs SET status='interrupted' WHERE status='running'")
