"""SQL safety + sanity validation using sqlglot.

Rules (all must pass before a statement may touch the database):
  1. exactly one statement, parseable as PostgreSQL
  2. a read-only query: SELECT / set operations / WITH ... SELECT
  3. no writes, DDL, COPY, SELECT INTO, row locks, or dangerous functions
  4. every referenced table exists (CTE names excluded) and every column resolves
  5. a LIMIT is applied to plain SELECTs
"""
from __future__ import annotations

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError, TokenError
from sqlglot.optimizer.qualify import qualify

DIALECT = "postgres"

_FORBIDDEN_NODES = tuple(
    getattr(exp, n) for n in (
        "Insert", "Update", "Delete", "Drop", "Create", "Alter", "Merge", "Command", "Copy",
        "TruncateTable", "Grant", "Revoke", "Set", "Use", "Pragma", "Transaction", "Commit", "Rollback",
        "Into", "Lock", "Analyze", "Kill", "Declare",
    ) if hasattr(exp, n)
)
_FORBIDDEN_FUNCS = {
    "pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file", "lo_import", "lo_export",
    "dblink", "dblink_exec", "set_config", "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
    "current_setting", "pg_advisory_lock", "query_to_xml", "copy",
}
_SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


@dataclass
class Validation:
    ok: bool
    sql: str = ""                     # normalised SQL (LIMIT applied, pretty printed)
    error: str | None = None
    tables: list[str] = field(default_factory=list)
    fatal: bool = False               # policy violation: never retry, refuse


def _fail(msg: str, fatal: bool = False) -> Validation:
    return Validation(ok=False, error=msg, fatal=fatal)


def validate_sql(sql: str, schema: dict[str, dict[str, str]], row_limit: int = 1000) -> Validation:
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        return _fail("Empty query.")
    try:
        statements = sqlglot.parse(sql, read=DIALECT)
    except (ParseError, TokenError) as e:
        return _fail(f"Syntax error: {str(e).splitlines()[0]}")
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        return _fail("Exactly one SQL statement is allowed.")
    tree = statements[0]

    if not isinstance(tree, (exp.Select, exp.Union, exp.Subquery)):
        return _fail(f"Only SELECT queries are allowed (got {type(tree).__name__.upper()}).", fatal=True)

    for node in tree.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            return _fail(f"Forbidden operation: {type(node).__name__.upper()}.", fatal=True)
        if isinstance(node, (exp.Func, exp.Anonymous)):
            name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()
            if name in _FORBIDDEN_FUNCS or name.startswith(("pg_", "lo_")):
                return _fail(f"Forbidden function: {name}.", fatal=True)

    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    known = {t.lower() for t in schema}
    used: list[str] = []
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        db = (t.args.get("db").name.lower() if t.args.get("db") else "")
        if db in _SYSTEM_SCHEMAS:
            return _fail(f"Access to system schema '{db}' is not allowed.", fatal=True)
        if not name or (name in cte_names and not db):
            continue
        if isinstance(t.this, exp.Func):   # e.g. generate_series(...) used as a table
            continue
        if name not in known:
            hint = _closest(name, known)
            return _fail(f"Unknown table '{t.name}'." + (f" Did you mean '{hint}'?" if hint else ""))
        if name not in used:
            used.append(name)

    # column resolution
    try:
        qualify(tree.copy(), schema=schema, dialect=DIALECT, validate_qualify_columns=True,
                identify=False, quote_identifiers=False)
    except OptimizeError as e:
        msg = str(e)
        low = msg.lower()
        if "could not be resolved" in low or "unknown column" in low or "ambiguous" in low:
            return _fail(_friendly_column_error(msg, tree, schema))
        # other optimiser limitations: let the database decide
    except Exception:  # noqa: BLE001 - optimiser gaps must not block valid SQL
        pass

    if isinstance(tree, exp.Select) and not tree.args.get("limit"):
        tree = tree.limit(row_limit)
    return Validation(ok=True, sql=tree.sql(dialect=DIALECT, pretty=True), tables=used)


def _closest(name: str, options: set[str]) -> str | None:
    import difflib
    m = difflib.get_close_matches(name, sorted(options), n=1, cutoff=0.6)
    return m[0] if m else None


def _friendly_column_error(msg: str, tree: exp.Expression, schema: dict[str, dict[str, str]]) -> str:
    import re
    m = re.search(r"Column '([^']+)'|Unknown column: (\S+)", msg)
    if not m:
        return f"Column resolution error: {msg}"
    col = (m.group(1) or m.group(2)).rstrip(".,")
    bare = col.split(".")[-1].lower()
    tables = sorted({t.name.lower() for t in tree.find_all(exp.Table)} & {t.lower() for t in schema})
    holders = [t for t in tables if bare in {c.lower() for c in schema.get(t, {})}]
    if "." not in col and len(holders) >= 2:
        return (f"Column '{col}' is ambiguous (exists in {', '.join(holders)}); "
                f"qualify it with a table alias, e.g. {holders[0][0]}.{col}.")
    pool = {c.lower() for t in tables for c in schema.get(t, {})} or {c.lower() for cols in schema.values() for c in cols}
    hint = _closest(bare, pool)
    where = f" among tables {', '.join(tables)}" if tables else ""
    return f"Column '{col}' does not exist{where}." + (f" Did you mean '{hint}'?" if hint and hint != bare else "")
