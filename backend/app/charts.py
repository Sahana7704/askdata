"""Deterministic chart selection and insight tiles from a result set (no LLM involved)."""
from __future__ import annotations

import re
from typing import Any

_DATE_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$")
XKEY = "__x"          # reserved key for the x-axis value; series names come from user data and may be "x"
MAX_SERIES = 8
MAX_POINTS = 60


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def column_kinds(columns: list[str], rows: list[list[Any]]) -> list[str]:
    kinds = []
    for i, _ in enumerate(columns):
        vals = [r[i] for r in rows if r[i] is not None]
        if not vals:
            kinds.append("empty")
        elif all(_is_num(v) for v in vals):
            kinds.append("number")
        elif all(isinstance(v, str) and _DATE_RE.match(v) for v in vals):
            kinds.append("time")
        else:
            kinds.append("category")
    return kinds


def build_chart(columns: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    if not rows:
        return {"type": "grid", "available": ["grid"], "x": None, "series": [], "data": []}
    kinds = column_kinds(columns, rows)
    num_idx = [i for i, k in enumerate(kinds) if k == "number"]
    base = {"x": None, "series": [], "data": [], "available": ["grid"]}

    if len(rows) == 1 and num_idx:
        return {**base, "type": "stat"}

    # id-like numeric columns are poor x axes; look for a dimension column first
    dim_idx = next((i for i, k in enumerate(kinds) if k in ("time", "category")), None)
    if dim_idx is None or not num_idx:
        return {**base, "type": "grid"}

    # long format: dimension, second dimension, measure  -> pivot into series
    dim2 = next((i for i, k in enumerate(kinds) if k == "category" and i != dim_idx), None)
    if dim2 is not None and len(num_idx) >= 1 and len(columns) == 3:
        measure = num_idx[0]
        totals: dict[str, float] = {}
        for r in rows:
            totals[str(r[dim2])] = totals.get(str(r[dim2]), 0) + (r[measure] or 0)
        keep = [k for k, _ in sorted(totals.items(), key=lambda kv: -kv[1])[:MAX_SERIES]]
        xs: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for r in rows:
            xk = str(r[dim_idx])
            if xk not in xs:
                xs[xk] = {XKEY: xk}
                order.append(xk)
            if str(r[dim2]) in keep:
                xs[xk][str(r[dim2])] = r[measure]
        data = [xs[k] for k in order][:MAX_POINTS]
        ctype = "line" if kinds[dim_idx] == "time" else "bar"
        return {"type": ctype, "x": columns[dim_idx], "series": keep, "data": data, "stacked": True,
                "available": ["bar", "line", "grid"]}

    series = [columns[i] for i in num_idx if i != dim_idx][:MAX_SERIES]
    if not series:
        return {**base, "type": "grid"}
    data = []
    for r in rows[:MAX_POINTS]:
        point: dict[str, Any] = {XKEY: r[dim_idx] if r[dim_idx] is not None else "(null)"}
        for i in num_idx:
            if columns[i] in series:
                point[columns[i]] = r[i]
        data.append(point)
    is_time = kinds[dim_idx] == "time"
    available = ["bar", "line", "grid"] if is_time else ["bar", "line", "grid"]
    ctype = "line" if is_time else "bar"
    if not is_time and len(series) == 1 and len(data) <= 8 and all((d[series[0]] or 0) >= 0 for d in data):
        available = ["bar", "line", "donut", "grid"]
    return {"type": ctype, "x": columns[dim_idx], "series": series, "data": data, "stacked": False,
            "available": available}


_NON_ADDITIVE = re.compile(r"avg|average|mean|median|rate|ratio|pct|percent|share|price|rating|score", re.I)


def build_tiles(columns: list[str], rows: list[list[Any]]) -> list[dict[str, Any]]:
    """Up to four factual tiles computed directly from the rows."""
    if not rows:
        return []
    kinds = column_kinds(columns, rows)
    num_idx = [i for i, k in enumerate(kinds) if k == "number"]
    if not num_idx:
        return []
    if len(rows) == 1:
        return [{"label": columns[i], "value": rows[0][i], "kind": "number"} for i in num_idx[:4]]

    # measure = first numeric column that is not an obvious id/rank column
    measure = next((i for i in num_idx if not re.search(r"(^|_)(id|rank|year|month|day)$", columns[i], re.I)),
                   num_idx[0])
    dim = next((i for i, k in enumerate(kinds) if k in ("category", "time")), None)
    vals = [r[measure] for r in rows if r[measure] is not None]
    if not vals:
        return []
    name = columns[measure].replace("_", " ")
    top = max(rows, key=lambda r: r[measure] if r[measure] is not None else float("-inf"))
    if _NON_ADDITIVE.search(columns[measure]):
        # averages, prices, ratings, rates: a total or a share of total would be meaningless
        tiles = []
        if dim is not None:
            tiles.append({"label": f"Highest {name}", "value": str(top[dim]), "kind": "text", "sub": f"{top[measure]:,}"})
            low = min(rows, key=lambda r: r[measure] if r[measure] is not None else float("inf"))
            tiles.append({"label": f"Lowest {name}", "value": str(low[dim]), "kind": "text", "sub": f"{low[measure]:,}"})
        else:
            tiles.append({"label": f"Highest {name}", "value": max(vals), "kind": "number"})
            tiles.append({"label": f"Lowest {name}", "value": min(vals), "kind": "number"})
        tiles.append({"label": "Rows", "value": len(rows), "kind": "number"})
        return tiles
    total = sum(vals)
    tiles = [{"label": f"Total {name}", "value": round(total, 2), "kind": "number"}]
    if dim is not None:
        share = (top[measure] / total * 100) if total and top[measure] is not None and total > 0 else None
        tiles.append({"label": f"Top {columns[dim].replace('_', ' ')}", "value": str(top[dim]), "kind": "text",
                      "sub": f"{share:.1f}% of total" if share is not None and all(v >= 0 for v in vals) else None})
    tiles.append({"label": f"Average per row", "value": round(total / len(vals), 2), "kind": "number"})
    tiles.append({"label": "Rows", "value": len(rows), "kind": "number"})
    return tiles[:4]
