"""Evaluation harness: execution accuracy on a golden set, with component ablations.

Method (as in text-to-SQL benchmarks such as Spider): a generated query is correct if executing it
returns the same multiset of rows as executing the reference query. Row order and column names are
ignored; numbers are compared at 2-decimal precision.
"""
from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from . import store
from .agent import AgentConfig, ask
from .db import QueryError, run_readonly
from .llm import LLM

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "eval" / "golden_set.json"

CONFIGS: list[tuple[str, str, str, AgentConfig]] = [
    ("baseline", "Baseline", "Zero-shot, full schema in the prompt, no repair",
     AgentConfig(use_retrieval=False, max_repairs=0, summarize=False)),
    ("schema", "+ Schema retrieval", "BM25 + foreign-key expansion picks the relevant tables",
     AgentConfig(use_retrieval=True, max_repairs=0, summarize=False)),
    ("repair", "+ Repair loop", "Validator/DB errors are fed back to the model (up to 2 retries)",
     AgentConfig(use_retrieval=True, max_repairs=2, summarize=False)),
]


def load_golden() -> list[dict[str, Any]]:
    return json.loads(GOLDEN_PATH.read_text())


def _norm(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return f"s:{v}"
    if isinstance(v, (int, float)):
        return f"n:{round(float(v), 2):.2f}"
    return "s:" + str(v).strip().lower()


def result_signature(columns: list[str], rows: list[list[Any]]) -> tuple[int, Counter]:
    return len(columns), Counter(tuple(sorted(_norm(v) for v in r)) for r in rows)


def same_result(ref: tuple[int, Counter], cols: list[str], rows: list[list[Any]]) -> bool:
    return result_signature(cols, rows) == ref


def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]


def run_eval(llm: LLM, run_id: str, limit: int | None = None, config_keys: list[str] | None = None) -> dict[str, Any]:
    cases = load_golden()[: limit or None]
    configs = [c for c in CONFIGS if not config_keys or c[0] in config_keys]
    total = len(cases) * len(configs)
    done = 0
    refs: dict[str, tuple[int, Counter]] = {}
    for c in cases:
        try:
            r = run_readonly(c["reference_sql"])
            refs[c["id"]] = result_signature(r.columns, r.rows)
        except QueryError as e:  # a broken reference is a bug in the golden set, not a model failure
            raise RuntimeError(f"Reference SQL for {c['id']} failed: {e}") from e

    records: list[dict[str, Any]] = []
    for key, label, _desc, cfg in configs:
        for case in cases:
            store.update_eval(run_id, progress={"done": done, "total": total, "config": label, "case": case["id"]})
            t0 = time.perf_counter()
            try:
                out = ask(case["question"], llm=llm, config=cfg)
            except Exception as e:  # noqa: BLE001
                out = {"status": "failed", "error": f"agent error: {e}", "repairs": 0, "sql": "", "columns": [],
                       "rows": [], "latency_ms": (time.perf_counter() - t0) * 1000, "first_error": None}
            correct = out["status"] == "ok" and same_result(refs[case["id"]], out["columns"], out["rows"])
            if correct:
                failure = None
            elif out["status"] == "ok":
                failure = "wrong_result"
            elif out["status"] == "unanswerable":
                failure = "refused"
            else:
                failure = "invalid_sql"
            records.append({
                "config": key, "case_id": case["id"], "category": case["category"], "question": case["question"],
                "correct": correct, "failure": failure, "repairs": out.get("repairs", 0),
                "healed": bool(correct and out.get("repairs", 0) > 0), "latency_ms": out.get("latency_ms", 0),
                "error": out.get("error"), "first_error": out.get("first_error"),
                "expected_sql": case["reference_sql"], "actual_sql": out.get("sql", ""),
            })
            done += 1

    summary = []
    for key, label, desc, _cfg in configs:
        rs = [r for r in records if r["config"] == key]
        n = len(rs)
        lat = [r["latency_ms"] for r in rs]
        cats: dict[str, dict[str, int]] = {}
        for r in rs:
            d = cats.setdefault(r["category"], {"n": 0, "correct": 0})
            d["n"] += 1
            d["correct"] += int(r["correct"])
        summary.append({
            "key": key, "label": label, "description": desc, "n": n,
            "correct": sum(r["correct"] for r in rs),
            "accuracy": round(100 * sum(r["correct"] for r in rs) / n, 1) if n else 0,
            "median_latency_ms": round(statistics.median(lat), 0) if lat else 0,
            "p95_latency_ms": round(_pct(lat, 0.95), 0),
            "repair_rate": round(100 * sum(1 for r in rs if r["repairs"] > 0) / n, 1) if n else 0,
            "healed": sum(r["healed"] for r in rs),
            "invalid_sql": sum(1 for r in rs if r["failure"] == "invalid_sql"),
            "wrong_result": sum(1 for r in rs if r["failure"] == "wrong_result"),
            "refused": sum(1 for r in rs if r["failure"] == "refused"),
            "categories": {k: {**v, "accuracy": round(100 * v["correct"] / v["n"], 1)} for k, v in cats.items()},
        })
    return {"n_cases": len(cases), "summary": summary, "records": records, "finished_at": time.time()}
