"""Create and populate the synthetic demo database ("shop").

The data is SYNTHETIC (seeded random generator) - an e-commerce schema in the
spirit of public marketplace datasets. It is meant for demos and evaluation,
not for drawing real-world conclusions.

Usage:
    python data/seed.py --admin-url postgresql://user:pass@localhost:5432/shop
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

import psycopg

DDL = """
DROP TABLE IF EXISTS reviews, payments, order_items, orders, products, categories, sellers, customers CASCADE;

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    signup_date DATE NOT NULL
);
CREATE TABLE sellers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL
);
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category_id INT NOT NULL REFERENCES categories(id),
    seller_id INT NOT NULL REFERENCES sellers(id),
    price NUMERIC(10,2) NOT NULL
);
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(id),
    order_date TIMESTAMP NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(id),
    product_id INT NOT NULL REFERENCES products(id),
    quantity INT NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL,
    freight_value NUMERIC(10,2) NOT NULL
);
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(id),
    payment_type TEXT NOT NULL,
    amount NUMERIC(10,2) NOT NULL
);
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(id),
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMP NOT NULL
);
CREATE INDEX ON orders(customer_id);
CREATE INDEX ON orders(order_date);
CREATE INDEX ON order_items(order_id);
CREATE INDEX ON order_items(product_id);
"""

COMMENTS = """
COMMENT ON TABLE customers IS 'People who place orders. One row per customer.';
COMMENT ON COLUMN customers.state IS 'Two-letter state code of the customer';
COMMENT ON COLUMN customers.signup_date IS 'Date the customer created an account';
COMMENT ON TABLE sellers IS 'Marketplace sellers that list products.';
COMMENT ON TABLE categories IS 'Product categories.';
COMMENT ON TABLE products IS 'Catalog of products. price is the current list price.';
COMMENT ON COLUMN products.price IS 'Current list price in USD';
COMMENT ON TABLE orders IS 'One row per customer order. Revenue lives in order_items and payments.';
COMMENT ON COLUMN orders.status IS 'Order lifecycle state; canceled orders generate no revenue';
COMMENT ON COLUMN orders.order_date IS 'When the order was placed';
COMMENT ON TABLE order_items IS 'Line items of an order. Line revenue = quantity * unit_price.';
COMMENT ON COLUMN order_items.unit_price IS 'Price per unit at time of purchase, USD';
COMMENT ON COLUMN order_items.freight_value IS 'Shipping cost charged for this line, USD';
COMMENT ON TABLE payments IS 'Payments received per order.';
COMMENT ON COLUMN payments.payment_type IS 'How the customer paid';
COMMENT ON TABLE reviews IS 'Customer review of an order, rating 1 (worst) to 5 (best).';
"""

STATES = ["CA", "NY", "TX", "FL", "WA", "IL", "MA", "CO", "GA", "OH"]
CITIES = {
    "CA": ["San Francisco", "Los Angeles", "San Diego"], "NY": ["New York", "Buffalo"],
    "TX": ["Austin", "Dallas", "Houston"], "FL": ["Miami", "Orlando"], "WA": ["Seattle", "Spokane"],
    "IL": ["Chicago", "Springfield"], "MA": ["Boston", "Worcester"], "CO": ["Denver", "Boulder"],
    "GA": ["Atlanta", "Savannah"], "OH": ["Columbus", "Cleveland"],
}
CATEGORIES = ["Electronics", "Home & Garden", "Books", "Toys", "Sports", "Beauty",
              "Fashion", "Grocery", "Pet Supplies", "Automotive", "Office", "Music"]
FIRST = ["Ava", "Liam", "Noah", "Emma", "Mia", "Lucas", "Ethan", "Zoe", "Ivy", "Owen", "Ruby", "Leo",
         "Nora", "Eli", "Maya", "Finn", "Aria", "Jude", "Cleo", "Theo"]
LAST = ["Smith", "Lee", "Patel", "Garcia", "Kim", "Brown", "Nguyen", "Davis", "Lopez", "Clark",
        "Young", "Baker", "Reed", "Cruz", "Shah", "Ortiz", "Moore", "Hall"]
PAYMENT_TYPES = ["credit_card", "debit_card", "paypal", "gift_card"]
STATUSES = ["delivered", "shipped", "processing", "canceled"]


def generate(conn: psycopg.Connection, seed: int = 7) -> None:
    rnd = random.Random(seed)
    cur = conn.cursor()
    start, end = datetime(2017, 1, 1), datetime(2018, 12, 31)
    span_days = (end - start).days

    n_customers, n_sellers, n_products, n_orders = 2000, 40, 300, 15000

    customers = []
    for i in range(1, n_customers + 1):
        st = rnd.choice(STATES)
        customers.append((f"{rnd.choice(FIRST)} {rnd.choice(LAST)}", rnd.choice(CITIES[st]), st,
                          (start + timedelta(days=rnd.randint(0, span_days))).date()))
    cur.executemany("INSERT INTO customers(name, city, state, signup_date) VALUES (%s,%s,%s,%s)", customers)

    sellers = []
    for i in range(1, n_sellers + 1):
        st = rnd.choice(STATES)
        sellers.append((f"Seller {i:02d}", rnd.choice(CITIES[st]), st))
    cur.executemany("INSERT INTO sellers(name, city, state) VALUES (%s,%s,%s)", sellers)
    cur.executemany("INSERT INTO categories(name) VALUES (%s)", [(c,) for c in CATEGORIES])

    products = []
    base_price = {c: rnd.uniform(8, 220) for c in CATEGORIES}
    for i in range(1, n_products + 1):
        cat_id = rnd.randint(1, len(CATEGORIES))
        price = round(max(2.0, rnd.gauss(base_price[CATEGORIES[cat_id - 1]], 15)), 2)
        products.append((f"{CATEGORIES[cat_id - 1]} item {i}", cat_id, rnd.randint(1, n_sellers), price))
    cur.executemany("INSERT INTO products(name, category_id, seller_id, price) VALUES (%s,%s,%s,%s)", products)

    orders, items, payments, reviews = [], [], [], []
    for oid in range(1, n_orders + 1):
        # mild growth over time: later dates are more likely
        day = int(span_days * (rnd.random() ** 0.8))
        odate = start + timedelta(days=day, seconds=rnd.randint(0, 86399))
        status = rnd.choices(STATUSES, weights=[78, 8, 4, 10])[0]
        orders.append((rnd.randint(1, n_customers), odate, status))
        order_total = 0.0
        for _ in range(rnd.choices([1, 2, 3], weights=[60, 28, 12])[0]):
            pid = rnd.randint(1, n_products)
            qty = rnd.choices([1, 2, 3], weights=[75, 18, 7])[0]
            unit = products[pid - 1][3]
            freight = round(rnd.uniform(2, 18), 2)
            items.append((oid, pid, qty, unit, freight))
            order_total += qty * unit + freight
        if status != "canceled":
            payments.append((oid, rnd.choices(PAYMENT_TYPES, weights=[55, 25, 15, 5])[0], round(order_total, 2)))
        if status == "delivered" and rnd.random() < 0.6:
            rating = rnd.choices([1, 2, 3, 4, 5], weights=[6, 6, 12, 28, 48])[0]
            reviews.append((oid, rating, odate + timedelta(days=rnd.randint(3, 20))))

    cur.executemany("INSERT INTO orders(customer_id, order_date, status) VALUES (%s,%s,%s)", orders)
    cur.executemany("INSERT INTO order_items(order_id, product_id, quantity, unit_price, freight_value) "
                    "VALUES (%s,%s,%s,%s,%s)", items)
    cur.executemany("INSERT INTO payments(order_id, payment_type, amount) VALUES (%s,%s,%s)", payments)
    cur.executemany("INSERT INTO reviews(order_id, rating, created_at) VALUES (%s,%s,%s)", reviews)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-url", required=True, help="libpq URL of a role allowed to create tables")
    ap.add_argument("--ro-user", default="askdata_ro")
    ap.add_argument("--ro-password", default="askdata_ro")
    ap.add_argument("--if-missing", action="store_true", help="skip (do not drop/reseed) if the demo tables already exist")
    args = ap.parse_args()

    with psycopg.connect(args.admin_url, autocommit=True) as conn:
        if args.if_missing and conn.execute("SELECT to_regclass('public.orders')").fetchone()[0]:
            print("Demo tables already exist; nothing to do (use without --if-missing to reseed).")
            return
        conn.execute(DDL)
        generate(conn)
        conn.execute(COMMENTS)
        conn.execute("ANALYZE")
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (args.ro_user,)).fetchone()
        if not exists:
            conn.execute(f"CREATE ROLE {args.ro_user} LOGIN PASSWORD '{args.ro_password}'")
        db = conn.execute("SELECT current_database()").fetchone()[0]
        conn.execute(f'GRANT CONNECT ON DATABASE "{db}" TO {args.ro_user}')
        conn.execute(f"GRANT USAGE ON SCHEMA public TO {args.ro_user}")
        conn.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {args.ro_user}")
        conn.execute(f"ALTER ROLE {args.ro_user} SET default_transaction_read_only = on")
        counts = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                  for t in ["customers", "sellers", "categories", "products", "orders", "order_items", "payments", "reviews"]}
    print("Seeded:", counts)


if __name__ == "__main__":
    main()
