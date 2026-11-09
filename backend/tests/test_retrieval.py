def test_retrieval_finds_relevant_tables(index):
    names = index.retrieve("average review rating by customer state")
    assert {"reviews", "customers"} <= set(names)
    assert "orders" in names  # bridge table between reviews and customers


def test_revenue_question_reaches_order_items(index):
    names = index.retrieve("Top 5 product categories by revenue")
    assert {"categories", "products", "order_items"} <= set(names)


def test_render_includes_values_and_ranges(index):
    text = index.render(["orders"])
    assert "canceled" in text and "range:" in text and "REFERENCES customers.id" in text


def test_unrelated_question_falls_back_to_all_tables(index):
    assert len(index.retrieve("zzzz qqqq")) == len(index.tables)
