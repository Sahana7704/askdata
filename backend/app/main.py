"""FastAPI application."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

from . import store
from .agent import ask as run_agent
from .config import get_settings
from .db import get_engine
from .evals import load_golden, run_eval
from .llm import LLMNotConfigured, get_llm, llm_status
from .schema_index import get_index

EXAMPLES = [
    "Top 5 product categories by revenue",
    "Monthly revenue in 2018",
    "Which state has the highest average review rating?",
    "How many orders were canceled in each state?",
    "Share of revenue by payment type",
    "Rank sellers by revenue and show the top 10",
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init()
    store.mark_stale_runs_failed()
    yield


app = FastAPI(title="AskData API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_methods=["*"], allow_headers=["*"])

# ---- tiny in-memory rate limiter (per client IP) to protect LLM spend -------------------------------------------
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = threading.Lock()


def rate_limit(request: Request, key: str, limit: int, window_s: int = 60) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _hits_lock:
        q = _hits[f"{key}:{ip}"]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, f"Rate limit: max {limit} requests per {window_s}s")
        q.append(now)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class EvalRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=200)
    configs: list[str] | None = None


@app.get("/api/health")
def health() -> dict[str, Any]:
    out: dict[str, Any] = {"status": "ok", "llm": llm_status(), "database": None}
    try:
        t0 = time.perf_counter()
        with get_engine().connect() as c:
            c.execute(text("select 1"))
        latency = round((time.perf_counter() - t0) * 1000, 1)
        ix = get_index()
        out["database"] = {"name": ix.database, "dialect": "postgresql", "tables": len(ix.tables),
                           "columns": sum(len(t.columns) for t in ix.tables.values()), "latency_ms": latency}
    except Exception as e:  # noqa: BLE001
        out["status"] = "degraded"
        out["database"] = {"error": str(e).splitlines()[0][:200]}
    return out


@app.get("/api/examples")
def examples() -> list[str]:
    return EXAMPLES


@app.get("/api/schema")
def schema() -> dict[str, Any]:
    try:
        ix = get_index()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Database unavailable: {str(e).splitlines()[0][:200]}") from e
    return {"database": ix.database, "built_at": ix.built_at,
            "tables": [t.to_dict() for t in ix.tables.values()], "relationships": ix.relationships()}


@app.post("/api/schema/refresh")
def schema_refresh() -> dict[str, Any]:
    ix = get_index(refresh=True)
    return {"tables": len(ix.tables), "built_at": ix.built_at}


@app.post("/api/ask")
def ask(req: AskRequest, request: Request) -> dict[str, Any]:
    rate_limit(request, "ask", limit=20)
    try:
        get_llm()
    except LLMNotConfigured as e:
        raise HTTPException(503, "LLM not configured: set ASKDATA_GEMINI_API_KEY (free) or ASKDATA_ANTHROPIC_API_KEY on the backend and restart it.") from e
    try:
        get_index()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Database unavailable: {str(e).splitlines()[0][:200]}") from e
    result = run_agent(req.question)
    result["id"] = store.add_history(result)
    return result


@app.get("/api/history")
def history(limit: int = 15) -> list[dict[str, Any]]:
    return store.list_history(min(max(limit, 1), 100))


@app.get("/api/history/{hid}")
def history_item(hid: str) -> dict[str, Any]:
    item = store.get_history(hid)
    if not item:
        raise HTTPException(404, "Not found")
    item["id"] = hid
    return item


# ---- evaluation ---------------------------------------------------------------------------------------------------
_eval_thread: threading.Thread | None = None


@app.get("/api/eval/info")
def eval_info() -> dict[str, Any]:
    golden = load_golden()
    cats: dict[str, int] = {}
    for g in golden:
        cats[g["category"]] = cats.get(g["category"], 0) + 1
    return {"cases": len(golden), "categories": cats, "llm": llm_status()}


@app.post("/api/eval/run")
def eval_run(req: EvalRequest, request: Request) -> dict[str, Any]:
    global _eval_thread
    rate_limit(request, "eval", limit=3, window_s=300)
    try:
        llm = get_llm()
    except LLMNotConfigured as e:
        raise HTTPException(503, "LLM not configured: set ASKDATA_GEMINI_API_KEY (free) or ASKDATA_ANTHROPIC_API_KEY on the backend and restart it.") from e
    if _eval_thread and _eval_thread.is_alive():
        raise HTTPException(409, "An evaluation is already running")
    rid = store.create_eval({"done": 0, "total": 0})

    def work() -> None:
        try:
            result = run_eval(llm, rid, limit=req.limit, config_keys=req.configs)
            store.update_eval(rid, status="complete", result=result,
                              progress={"done": len(result["records"]), "total": len(result["records"])})
        except Exception as e:  # noqa: BLE001
            store.update_eval(rid, status="failed", progress={"error": str(e)[:500]})

    _eval_thread = threading.Thread(target=work, daemon=True)
    _eval_thread.start()
    return {"id": rid}


@app.get("/api/eval/latest")
def eval_latest() -> dict[str, Any]:
    run = store.latest_eval()
    return run or {"id": None, "status": "none", "progress": {}, "result": None}


@app.get("/api/eval/runs/{rid}")
def eval_get(rid: str) -> dict[str, Any]:
    run = store.get_eval(rid)
    if not run:
        raise HTTPException(404, "Not found")
    return run
