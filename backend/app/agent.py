"""The AskData agent: a LangGraph state machine.

    retrieve_schema -> generate_sql -> validate -> execute -> summarize
                              ^           |           |
                              +-- repair <+-----------+      (bounded by max_repairs)

The graph is built per (llm, config) so evaluation can ablate components:
  * use_retrieval=False  -> the full schema is sent instead of retrieved tables
  * max_repairs=0        -> no self-repair loop
"""
from __future__ import annotations

import json
import operator
import re
import time
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .charts import build_chart, build_tiles
from .config import get_settings
from .db import QueryError, QueryResult, run_readonly
from .llm import LLM, extract_sql, get_llm
from .prompts import EMPTY_HINT, REPAIR_USER, SQL_SYSTEM, SQL_USER, SUMMARY_SYSTEM, SUMMARY_USER
from .schema_index import SchemaIndex, get_index
from .validator import validate_sql


@dataclass(frozen=True)
class AgentConfig:
    use_retrieval: bool = True
    max_repairs: int = 2
    summarize: bool = True        # evals switch this off to save LLM calls


class State(TypedDict, total=False):
    question: str
    tables: list[str]
    schema_text: str
    widened: bool
    sql: str
    final_sql: str
    validated_tables: list[str]
    attempt: int
    error: str | None
    error_kind: str | None        # validation | execution | empty | llm
    cannot_answer: str | None
    result: QueryResult | None
    fallback_result: QueryResult | None
    fallback_sql: str | None
    first_error: str | None       # error that triggered the first repair (for stats)
    status: str                   # ok | failed | unanswerable
    summary: str
    trace: Annotated[list[dict], operator.add]


def _step(step: str, status: str, t0: float, detail: str = "") -> dict:
    return {"step": step, "status": status, "ms": round((time.perf_counter() - t0) * 1000, 1), "detail": detail}


def _looks_empty(res: QueryResult) -> bool:
    """No rows, or a single aggregate row whose values are all 0/NULL (e.g. COUNT(*) = 0)."""
    if not res.rows:
        return True
    return len(res.rows) == 1 and all(v in (0, 0.0, None) for v in res.rows[0])


def _short(s: str | None, n: int = 160) -> str:
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def build_graph(llm: LLM | None = None, config: AgentConfig | None = None, index: SchemaIndex | None = None):
    cfg = config or AgentConfig(max_repairs=get_settings().max_repairs)
    settings = get_settings()

    def idx() -> SchemaIndex:
        return index or get_index()

    def get_model() -> LLM:
        return llm or get_llm()

    # ---------------------------------------------------------------- nodes
    def retrieve_schema(state: State) -> dict:
        t0 = time.perf_counter()
        ix = idx()
        names = ix.retrieve(state["question"]) if cfg.use_retrieval else list(ix.tables)
        return {"tables": names, "schema_text": ix.render(names), "widened": not cfg.use_retrieval, "attempt": 0,
                "trace": [_step("schema", "ok", t0, f"{len(names)} of {len(ix.tables)} tables: {', '.join(names)}")]}

    def generate_sql(state: State) -> dict:
        t0 = time.perf_counter()
        try:
            raw = get_model().complete(SQL_SYSTEM.format(schema=state["schema_text"]),
                                       SQL_USER.format(question=state["question"]))
        except Exception as e:  # noqa: BLE001
            return {"error": f"LLM error: {_short(str(e), 300)}", "error_kind": "llm", "status": "failed",
                    "trace": [_step("generate", "error", t0, f"LLM error: {_short(str(e))}")]}
        sql, cannot = extract_sql(raw)
        if cannot:
            return {"cannot_answer": cannot, "status": "unanswerable",
                    "trace": [_step("generate", "warn", t0, f"Cannot answer: {cannot}")]}
        if not sql:
            return {"sql": "", "trace": [_step("generate", "warn", t0, "No SQL found in model output")]}
        return {"sql": sql, "trace": [_step("generate", "ok", t0, "SQL written")]}

    def validate(state: State) -> dict:
        t0 = time.perf_counter()
        v = validate_sql(state.get("sql", ""), idx().sqlglot_schema(), settings.row_limit)
        if v.ok:
            return {"final_sql": v.sql, "validated_tables": v.tables, "error": None, "error_kind": None,
                    "trace": [_step("validate", "ok", t0, "Read-only SELECT verified; tables and columns resolve")]}
        return {"error": v.error, "error_kind": "policy" if v.fatal else "validation",
                "trace": [_step("validate", "error", t0, v.error or "invalid")]}

    def execute(state: State) -> dict:
        t0 = time.perf_counter()
        try:
            res = run_readonly(state["final_sql"], settings.row_limit, settings.statement_timeout_ms)
        except QueryError as e:
            return {"error": str(e), "error_kind": "execution",
                    "trace": [_step("execute", "error", t0, _short(str(e)))]}
        if _looks_empty(res) and state.get("attempt", 0) == 0 and cfg.max_repairs > 0:
            return {"error": EMPTY_HINT, "error_kind": "empty", "result": res,
                    "fallback_result": res, "fallback_sql": state["final_sql"],
                    "trace": [_step("execute", "warn", t0, "Empty result; asking the model to re-check filters")]}
        return {"result": res, "error": None, "error_kind": None, "status": "ok",
                "trace": [_step("execute", "ok", t0, f"{len(res.rows)} rows" + (" (truncated)" if res.truncated else ""))]}

    def repair(state: State) -> dict:
        t0 = time.perf_counter()
        attempt = state.get("attempt", 0) + 1
        update: dict[str, Any] = {"attempt": attempt}
        err = state.get("error") or "unknown error"
        if state.get("first_error") is None:
            update["first_error"] = err
        # a missing table/column often means retrieval cut something off: show the full schema
        widened = state.get("widened", False)
        schema_text = state["schema_text"]
        if not widened and re.search(r"unknown table|does not exist|could not be resolved|relation", err, re.I):
            ix = idx()
            schema_text = ix.render(list(ix.tables))
            update.update(schema_text=schema_text, widened=True)
        try:
            raw = get_model().complete(
                SQL_SYSTEM.format(schema=schema_text),
                REPAIR_USER.format(question=state["question"], sql=state.get("sql", ""), error=err))
        except Exception as e:  # noqa: BLE001
            update.update(error=f"LLM error: {_short(str(e), 300)}", error_kind="llm", status="failed",
                          trace=[_step("repair", "error", t0, f"LLM error: {_short(str(e))}")])
            return update
        sql, cannot = extract_sql(raw)
        label = f"Retry {attempt}: {_short(err, 120)}"
        if cannot:
            update.update(cannot_answer=cannot, status="unanswerable", trace=[_step("repair", "warn", t0, label)])
            return update
        update.update(sql=sql or "", trace=[_step("repair", "warn", t0, label)])
        return update

    def give_up(state: State) -> dict:
        t0 = time.perf_counter()
        # an empty-but-valid first result beats a failed repair
        if state.get("fallback_result") is not None and state.get("error_kind") not in ("llm", "policy"):
            return {"result": state["fallback_result"], "final_sql": state["fallback_sql"], "status": "ok",
                    "error": None, "error_kind": None,
                    "trace": [_step("execute", "ok", t0, "Returning the original (empty) result")]}
        return {"status": "failed"}

    def summarize(state: State) -> dict:
        t0 = time.perf_counter()
        res = state["result"]
        if res is None or not cfg.summarize:
            return {}
        if not res.rows:
            return {"summary": "The query ran successfully but returned no rows.",
                    "trace": [_step("summarize", "ok", t0, "No rows to summarise")]}
        shown = res.rows[:20]
        try:
            text = get_model().complete(
                SUMMARY_SYSTEM,
                SUMMARY_USER.format(question=state["question"], columns=", ".join(res.columns), shown=len(shown),
                                    total=len(res.rows), trunc=", more rows exist" if res.truncated else "",
                                    rows="\n".join(json.dumps(r, default=str) for r in shown)),
                max_tokens=300)
            return {"summary": text.strip(), "trace": [_step("summarize", "ok", t0, "Summary written")]}
        except Exception as e:  # noqa: BLE001 - never fail the answer because the summary failed
            return {"summary": f"Returned {len(res.rows)} rows across {len(res.columns)} columns.",
                    "trace": [_step("summarize", "warn", t0, f"Summary unavailable: {_short(str(e))}")]}

    # ---------------------------------------------------------------- routing
    def can_repair(state: State) -> bool:
        return state.get("attempt", 0) < cfg.max_repairs and state.get("error_kind") not in ("llm", "policy")

    def after_generate(state: State) -> str:
        if state.get("status") in ("unanswerable", "failed"):
            return "end"
        return "validate"

    def after_validate(state: State) -> str:
        if state.get("error_kind") is None:
            return "execute"
        return "repair" if can_repair(state) else "give_up"

    def after_execute(state: State) -> str:
        kind = state.get("error_kind")
        if kind is None:
            return "summarize"
        return "repair" if can_repair(state) else "give_up"

    def after_repair(state: State) -> str:
        return "end" if state.get("status") in ("unanswerable", "failed") else "validate"

    g = StateGraph(State)
    for name, fn in [("retrieve_schema", retrieve_schema), ("generate_sql", generate_sql), ("validate", validate),
                     ("execute", execute), ("repair", repair), ("give_up", give_up), ("summarize", summarize)]:
        g.add_node(name, fn)
    g.add_edge(START, "retrieve_schema")
    g.add_edge("retrieve_schema", "generate_sql")
    g.add_conditional_edges("generate_sql", after_generate, {"validate": "validate", "end": END})
    g.add_conditional_edges("validate", after_validate, {"execute": "execute", "repair": "repair", "give_up": "give_up"})
    g.add_conditional_edges("execute", after_execute, {"summarize": "summarize", "repair": "repair", "give_up": "give_up"})
    g.add_conditional_edges("repair", after_repair, {"validate": "validate", "end": END})
    g.add_conditional_edges("give_up", lambda s: "summarize" if s.get("status") == "ok" else "end",
                            {"summarize": "summarize", "end": END})
    g.add_edge("summarize", END)
    return g.compile()


def ask(question: str, llm: LLM | None = None, config: AgentConfig | None = None,
        index: SchemaIndex | None = None) -> dict[str, Any]:
    """Run the agent and return a JSON-serialisable response."""
    t0 = time.perf_counter()
    graph = build_graph(llm, config, index)
    final: State = graph.invoke({"question": question.strip(), "trace": []}, config={"recursion_limit": 40})
    res: QueryResult | None = final.get("result") if final.get("status") == "ok" else None
    columns = res.columns if res else []
    rows = res.rows if res else []
    status = final.get("status") or "failed"
    out: dict[str, Any] = {
        "question": question.strip(),
        "status": status,
        "summary": final.get("summary") if status == "ok" else None,
        "sql": final.get("final_sql") or final.get("sql") or "",
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": bool(res.truncated) if res else False,
        "chart": build_chart(columns, rows) if res else None,
        "tiles": build_tiles(columns, rows) if res else [],
        "trace": final.get("trace", []),
        "retrieved_tables": final.get("tables", []),
        "tables_used": final.get("validated_tables", []),
        "repairs": final.get("attempt", 0),
        "first_error": final.get("first_error"),
        "error": None if status == "ok" else (final.get("cannot_answer") or final.get("error")),
        "unanswerable": status == "unanswerable",
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
    return out
