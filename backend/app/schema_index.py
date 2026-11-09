"""Schema introspection, retrieval (BM25 + foreign-key graph expansion) and prompt rendering."""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from rank_bm25 import BM25Okapi
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .config import get_settings
from .db import get_engine, jsonable

_TEXT_TYPES = ("char", "text", "varchar", "enum", "string")
_DATE_TYPES = ("date", "time", "timestamp")


@dataclass
class Column:
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    comment: str | None = None
    fk: str | None = None          # "table.column"
    sample_values: list[str] = field(default_factory=list)  # low-cardinality text columns
    value_range: tuple[str, str] | None = None               # date/time columns

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.type, "nullable": self.nullable,
                "primary_key": self.primary_key, "comment": self.comment, "fk": self.fk,
                "sample_values": self.sample_values, "value_range": self.value_range}


@dataclass
class Table:
    name: str
    comment: str | None
    row_count: int
    columns: list[Column]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "comment": self.comment, "row_count": self.row_count,
                "columns": [c.to_dict() for c in self.columns]}


def _tokenize(s: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", re.sub(r"[_\-]", " ", s.lower()))
    out = []
    for t in toks:
        out.append(t)
        # crude singularisation so "orders" matches "order"
        if len(t) > 3 and t.endswith("ies"):
            out.append(t[:-3] + "y")
        elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            out.append(t[:-1])
    return out


_STOP = set("the a an of in on for to by and or with per what which who how many much show me give list "
            "top each all is are was were from last this that their its as at be can you get".split())


class SchemaIndex:
    def __init__(self, tables: list[Table], database: str):
        self.tables = {t.name: t for t in tables}
        self.database = database
        self.built_at = time.time()
        self._names = list(self.tables)
        corpus = [self._doc_tokens(self.tables[n]) for n in self._names]
        self._bm25 = BM25Okapi(corpus) if corpus else None
        # undirected FK adjacency
        self.parents: dict[str, set[str]] = {n: set() for n in self._names}
        self.children: dict[str, set[str]] = {n: set() for n in self._names}
        for t in tables:
            for c in t.columns:
                if c.fk:
                    ref = c.fk.split(".")[0]
                    if ref in self.tables:
                        self.parents[t.name].add(ref)
                        self.children[ref].add(t.name)

    # -- retrieval ---------------------------------------------------------------------------
    @staticmethod
    def _doc_tokens(t: Table) -> list[str]:
        parts = [t.name, t.name, t.name, t.comment or ""]
        for c in t.columns:
            parts += [c.name, c.comment or "", " ".join(c.sample_values)]
            if c.fk:
                parts.append(c.fk.split(".")[0])
        return _tokenize(" ".join(parts))

    def retrieve(self, question: str, top_k: int | None = None) -> list[str]:
        top_k = top_k or get_settings().retrieval_top_k
        q = [t for t in _tokenize(question) if t not in _STOP and not t.isdigit()]
        if not q or self._bm25 is None:
            return list(self._names)
        scores = self._bm25.get_scores(q)
        ranked = sorted(zip(self._names, scores), key=lambda x: -x[1])
        picked = [n for n, sc in ranked[:top_k] if sc > 0]
        if not picked:
            return list(self._names)
        chosen = list(picked)
        # expand along foreign keys: parents (lookup tables) and children that bridge two chosen tables
        for n in list(picked):
            for p in sorted(self.parents[n]):
                if p not in chosen:
                    chosen.append(p)
        for n in self._names:
            if n not in chosen and len(self.parents[n] & set(picked)) >= 2:
                chosen.append(n)
        return chosen[: top_k + 4]

    # -- rendering -----------------------------------------------------------------------------
    def render(self, names: list[str]) -> str:
        blocks = []
        for n in names:
            t = self.tables[n]
            head = f"TABLE {t.name}  -- ~{t.row_count} rows"
            if t.comment:
                head += f". {t.comment}"
            lines = [head]
            for c in t.columns:
                bits = [f"  {c.name} {c.type}"]
                if c.primary_key:
                    bits.append("PRIMARY KEY")
                if c.fk:
                    bits.append(f"REFERENCES {c.fk}")
                notes = []
                if c.comment:
                    notes.append(c.comment)
                if c.sample_values:
                    notes.append("values: " + ", ".join(c.sample_values))
                if c.value_range:
                    notes.append(f"range: {c.value_range[0]} .. {c.value_range[1]}")
                if notes:
                    bits.append("-- " + "; ".join(notes))
                lines.append(" ".join(bits))
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def catalog(self) -> dict[str, set[str]]:
        return {n: {c.name for c in t.columns} for n, t in self.tables.items()}

    def sqlglot_schema(self) -> dict[str, dict[str, str]]:
        return {n: {c.name: c.type for c in t.columns} for n, t in self.tables.items()}

    def relationships(self) -> list[dict[str, str]]:
        rels = []
        for t in self.tables.values():
            for c in t.columns:
                if c.fk:
                    rt, rc = c.fk.split(".")
                    rels.append({"from_table": t.name, "from_column": c.name, "to_table": rt, "to_column": rc})
        return rels


def build_index(engine: Engine | None = None, schema: str = "public") -> SchemaIndex:
    engine = engine or get_engine()
    insp = inspect(engine)
    tables: list[Table] = []
    with engine.connect() as conn:
        db_name = conn.execute(text("select current_database()")).scalar() or "database"
        for tname in sorted(insp.get_table_names(schema=schema)):
            pk = set(insp.get_pk_constraint(tname, schema=schema).get("constrained_columns") or [])
            fks = {}
            for fk in insp.get_foreign_keys(tname, schema=schema):
                for lc, rc in zip(fk["constrained_columns"], fk["referred_columns"]):
                    fks[lc] = f"{fk['referred_table']}.{rc}"
            tcomment = (insp.get_table_comment(tname, schema=schema) or {}).get("text")
            est = conn.execute(text("select reltuples::bigint from pg_class where oid = to_regclass(:n)"),
                               {"n": f'"{schema}"."{tname}"'}).scalar()
            if est is None or est < 0:
                est = conn.execute(text(f'select count(*) from "{schema}"."{tname}"')).scalar()
            cols = []
            for c in insp.get_columns(tname, schema=schema):
                ctype = str(c["type"]).lower()
                col = Column(name=c["name"], type=ctype, nullable=bool(c.get("nullable", True)),
                             primary_key=c["name"] in pk, comment=c.get("comment"), fk=fks.get(c["name"]))
                qn = f'"{c["name"]}"'
                qt = f'"{schema}"."{tname}"'
                try:
                    if any(k in ctype for k in _TEXT_TYPES) and not col.primary_key and not col.fk:
                        vals = [r[0] for r in conn.execute(text(f"select distinct {qn} from {qt} where {qn} is not null limit 13"))]
                        if 0 < len(vals) <= 12:
                            col.sample_values = sorted(str(jsonable(v)) for v in vals)
                    elif any(k in ctype for k in _DATE_TYPES):
                        lo, hi = conn.execute(text(f"select min({qn}), max({qn}) from {qt}")).one()
                        if lo is not None:
                            col.value_range = (str(jsonable(lo))[:10], str(jsonable(hi))[:10])
                except Exception:  # noqa: BLE001 - sampling is best-effort
                    conn.rollback()
                cols.append(col)
            tables.append(Table(name=tname, comment=tcomment, row_count=int(est), columns=cols))
    return SchemaIndex(tables, db_name)


_lock = threading.Lock()
_index: SchemaIndex | None = None


def get_index(refresh: bool = False) -> SchemaIndex:
    global _index
    with _lock:
        if _index is None or refresh:
            _index = build_index()
        return _index
