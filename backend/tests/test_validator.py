import pytest

from app.validator import validate_sql


@pytest.fixture(scope="module")
def schema(index):
    return index.sqlglot_schema()


OK = {
    "join_group": "SELECT c.name, SUM(oi.quantity*oi.unit_price) rev FROM order_items oi JOIN products p ON p.id=oi.product_id "
                  "JOIN categories c ON c.id=p.category_id GROUP BY c.name ORDER BY rev DESC LIMIT 5",
    "cte_window": "WITH m AS (SELECT date_trunc('month', o.order_date)::date mon, COUNT(*) n FROM orders o GROUP BY 1) "
                  "SELECT mon, n, LAG(n) OVER (ORDER BY mon) FROM m",
    "filter_clause": "SELECT COUNT(*) FILTER (WHERE status='canceled') FROM orders",
    "like_percent": "SELECT name FROM customers WHERE name LIKE 'A%' AND city ILIKE '%an%'",
    "union": "SELECT name FROM customers UNION SELECT name FROM sellers",
    "generate_series": "SELECT g::date FROM generate_series('2018-01-01'::date,'2018-03-01'::date,'1 month') g",
}


@pytest.mark.parametrize("name", OK)
def test_accepts_valid_selects(schema, name):
    r = validate_sql(OK[name], schema)
    assert r.ok, r.error


BLOCKED = {
    "drop": "DROP TABLE orders",
    "delete": "DELETE FROM orders",
    "update": "UPDATE orders SET status='x'",
    "insert": "INSERT INTO customers(name) VALUES ('x')",
    "multi": "SELECT 1; DELETE FROM orders",
    "sleep": "SELECT pg_sleep(10)",
    "read_file": "SELECT pg_read_file('/etc/passwd')",
    "sys_schema": "SELECT * FROM pg_catalog.pg_user",
    "info_schema": "SELECT * FROM information_schema.tables",
    "select_into": "SELECT * INTO newt FROM orders",
    "for_update": "SELECT * FROM orders FOR UPDATE",
    "cte_delete": "WITH d AS (DELETE FROM orders RETURNING *) SELECT * FROM d",
    "copy": "COPY orders TO '/tmp/x'",
    "set": "SET statement_timeout = 0",
}


@pytest.mark.parametrize("name", BLOCKED)
def test_blocks_unsafe_statements(schema, name):
    r = validate_sql(BLOCKED[name], schema)
    assert not r.ok, f"{name} should be rejected"


def test_policy_violations_are_fatal(schema):
    assert validate_sql("DROP TABLE orders", schema).fatal
    assert not validate_sql("SELECT nope FROM orders", schema).fatal


def test_unknown_table_and_column_messages(schema):
    assert "Unknown table 'invoices'" in validate_sql("SELECT * FROM invoices", schema).error
    e = validate_sql("SELECT custmer_id FROM orders", schema).error
    assert "customer_id" in e  # suggests the closest column


def test_ambiguous_column(schema):
    e = validate_sql("SELECT id FROM orders o JOIN customers c ON c.id=o.customer_id", schema).error
    assert "ambiguous" in e


def test_limit_is_applied_and_preserved(schema):
    assert "LIMIT 1000" in validate_sql("SELECT * FROM orders", schema, row_limit=1000).sql
    assert "LIMIT 5" in validate_sql("SELECT * FROM orders LIMIT 5", schema).sql
