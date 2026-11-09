"""Generates eval/golden_set.json. Each case: question, category, reference SQL (executed to get ground truth)."""
import json
from pathlib import Path

REV = "oi.quantity * oi.unit_price"
CASES = [
 # ---- simple aggregations
 ("simple", "How many customers are there?", "SELECT COUNT(*) FROM customers"),
 ("simple", "How many orders are there in each status? Return status and count.", "SELECT status, COUNT(*) FROM orders GROUP BY status"),
 ("simple", "What is the average product price, rounded to 2 decimals?", "SELECT ROUND(AVG(price),2) FROM products"),
 ("simple", "How many customers are in each state? Return state and count.", "SELECT state, COUNT(*) FROM customers GROUP BY state"),
 ("simple", "How many reviews have a rating of 5?", "SELECT COUNT(*) FROM reviews WHERE rating = 5"),
 ("simple", "What is the total payment amount for each payment type? Return payment type and total.", "SELECT payment_type, ROUND(SUM(amount),2) FROM payments GROUP BY payment_type"),
 ("simple", "How many sellers are there in each state? Return state and count.", "SELECT state, COUNT(*) FROM sellers GROUP BY state"),
 ("simple", "What is the price of the most expensive product?", "SELECT MAX(price) FROM products"),
 # ---- multi-table joins
 ("joins", "What are the top 5 product categories by revenue? Return category name and revenue rounded to 2 decimals.",
  f"SELECT c.name, ROUND(SUM({REV}),2) FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN products p ON p.id=oi.product_id JOIN categories c ON c.id=p.category_id WHERE o.status <> 'canceled' GROUP BY c.name ORDER BY 2 DESC LIMIT 5"),
 ("joins", "What is the average review rating for customers in each state? Return state and average rating rounded to 2 decimals.",
  "SELECT cu.state, ROUND(AVG(r.rating),2) FROM reviews r JOIN orders o ON o.id=r.order_id JOIN customers cu ON cu.id=o.customer_id GROUP BY cu.state"),
 ("joins", "Which 5 sellers have the highest revenue? Return seller name and revenue rounded to 2 decimals.",
  f"SELECT s.name, ROUND(SUM({REV}),2) FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN products p ON p.id=oi.product_id JOIN sellers s ON s.id=p.seller_id WHERE o.status <> 'canceled' GROUP BY s.name ORDER BY 2 DESC LIMIT 5"),
 ("joins", "How many distinct customers have ordered a product in the Electronics category?",
  "SELECT COUNT(DISTINCT o.customer_id) FROM orders o JOIN order_items oi ON oi.order_id=o.id JOIN products p ON p.id=oi.product_id JOIN categories c ON c.id=p.category_id WHERE c.name='Electronics'"),
 ("joins", "What is the total freight value for orders from customers in each state? Return state and total freight.",
  "SELECT cu.state, ROUND(SUM(oi.freight_value),2) FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN customers cu ON cu.id=o.customer_id GROUP BY cu.state"),
 ("joins", "How many canceled orders are there for customers in each state? Return state and count.",
  "SELECT cu.state, COUNT(*) FROM orders o JOIN customers cu ON cu.id=o.customer_id WHERE o.status='canceled' GROUP BY cu.state"),
 ("joins", "How many orders contain more than one line item?",
  "SELECT COUNT(*) FROM (SELECT order_id FROM order_items GROUP BY order_id HAVING COUNT(*) > 1) t"),
 ("joins", "Which payment type is used most often for delivered orders? Return only the payment type.",
  "SELECT p.payment_type FROM payments p JOIN orders o ON o.id=p.order_id WHERE o.status='delivered' GROUP BY p.payment_type ORDER BY COUNT(*) DESC LIMIT 1"),
 # ---- temporal
 ("temporal", "How many orders were placed in each month of 2018? Return month number (1-12) and order count.",
  "SELECT EXTRACT(MONTH FROM order_date)::int, COUNT(*) FROM orders WHERE order_date >= '2018-01-01' AND order_date < '2019-01-01' GROUP BY 1"),
 ("temporal", "What was the revenue in each year? Return year and revenue rounded to 2 decimals.",
  f"SELECT EXTRACT(YEAR FROM o.order_date)::int, ROUND(SUM({REV}),2) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE o.status <> 'canceled' GROUP BY 1"),
 ("temporal", "How many customers signed up in each year? Return year and count.",
  "SELECT EXTRACT(YEAR FROM signup_date)::int, COUNT(*) FROM customers GROUP BY 1"),
 ("temporal", "What was the revenue in each month from July to December 2018? Return month number (7-12) and revenue rounded to 2 decimals.",
  f"SELECT EXTRACT(MONTH FROM o.order_date)::int, ROUND(SUM({REV}),2) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE o.status <> 'canceled' AND o.order_date >= '2018-07-01' AND o.order_date < '2019-01-01' GROUP BY 1"),
 ("temporal", "How many orders were placed in each quarter of 2017? Return quarter number (1-4) and count.",
  "SELECT EXTRACT(QUARTER FROM order_date)::int, COUNT(*) FROM orders WHERE order_date >= '2017-01-01' AND order_date < '2018-01-01' GROUP BY 1"),
 ("temporal", "What is the average review rating for each calendar year of the review date? Return year and average rating rounded to 2 decimals.",
  "SELECT EXTRACT(YEAR FROM created_at)::int, ROUND(AVG(rating),2) FROM reviews GROUP BY 1"),
 ("temporal", "How many orders were placed in December 2018?",
  "SELECT COUNT(*) FROM orders WHERE order_date >= '2018-12-01' AND order_date < '2019-01-01'"),
 ("temporal", "What was the total revenue in the first quarter of 2018, rounded to 2 decimals?",
  f"SELECT ROUND(SUM({REV}),2) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE o.status <> 'canceled' AND o.order_date >= '2018-01-01' AND o.order_date < '2018-04-01'"),
 # ---- window functions / CTEs
 ("window", "Rank all product categories by total revenue. Return category name, revenue rounded to 2 decimals, and rank (1 = highest).",
  f"SELECT c.name, ROUND(SUM({REV}),2) AS rev, RANK() OVER (ORDER BY SUM({REV}) DESC) FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN products p ON p.id=oi.product_id JOIN categories c ON c.id=p.category_id WHERE o.status <> 'canceled' GROUP BY c.name"),
 ("window", "For each customer state, which product category has the highest revenue? Return state and category name.",
  f"SELECT state, name FROM (SELECT cu.state, c.name, ROW_NUMBER() OVER (PARTITION BY cu.state ORDER BY SUM({REV}) DESC) rn FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN customers cu ON cu.id=o.customer_id JOIN products p ON p.id=oi.product_id JOIN categories c ON c.id=p.category_id WHERE o.status <> 'canceled' GROUP BY cu.state, c.name) t WHERE rn=1"),
 ("window", "How many customers have placed at least 10 orders?",
  "SELECT COUNT(*) FROM (SELECT customer_id FROM orders GROUP BY customer_id HAVING COUNT(*) >= 10) t"),
 ("window", "What is the cumulative number of orders by month number (1-12) during 2017? Return month number and cumulative count.",
  "SELECT m, SUM(n) OVER (ORDER BY m)::bigint FROM (SELECT EXTRACT(MONTH FROM order_date)::int m, COUNT(*) n FROM orders WHERE order_date >= '2017-01-01' AND order_date < '2018-01-01' GROUP BY 1) t"),
 ("window", "What percentage of total revenue does each product category contribute? Return category name and percentage rounded to 1 decimal.",
  f"SELECT c.name, ROUND(100.0 * SUM({REV}) / SUM(SUM({REV})) OVER (), 1) FROM order_items oi JOIN orders o ON o.id=oi.order_id JOIN products p ON p.id=oi.product_id JOIN categories c ON c.id=p.category_id WHERE o.status <> 'canceled' GROUP BY c.name"),
 ("window", "What percentage of all orders were canceled, rounded to 2 decimals?",
  "SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status='canceled') / COUNT(*), 2) FROM orders"),
 ("window", "How many products are priced above the average price of their own category?",
  "SELECT COUNT(*) FROM (SELECT price, AVG(price) OVER (PARTITION BY category_id) a FROM products) t WHERE price > a"),
 ("window", "For each year, which month had the most orders? Return year and month number.",
  "SELECT y, m FROM (SELECT y, m, ROW_NUMBER() OVER (PARTITION BY y ORDER BY n DESC) rn FROM (SELECT EXTRACT(YEAR FROM order_date)::int y, EXTRACT(MONTH FROM order_date)::int m, COUNT(*) n FROM orders GROUP BY 1,2) a) b WHERE rn=1"),
]

out = [{"id": f"G{i+1:02d}", "category": c, "question": q, "reference_sql": s} for i, (c, q, s) in enumerate(CASES)]
Path(__file__).with_name("golden_set.json").write_text(json.dumps(out, indent=2))
print(len(out), "cases")
