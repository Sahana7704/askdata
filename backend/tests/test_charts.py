from app.charts import build_chart, build_tiles


def test_single_row_is_stat():
    c = build_chart(["n"], [[42]])
    assert c["type"] == "stat"
    assert build_tiles(["n"], [[42]])[0]["value"] == 42


def test_category_measure_is_bar_with_donut_option():
    c = build_chart(["cat", "rev"], [["a", 3], ["b", 2], ["c", 1]])
    assert c["type"] == "bar" and "donut" in c["available"]
    assert c["data"][0] == {"__x": "a", "rev": 3}


def test_time_series_is_line():
    c = build_chart(["month", "n"], [["2018-01-01", 3], ["2018-02-01", 5]])
    assert c["type"] == "line"


def test_long_format_is_pivoted_into_series():
    # series values deliberately include "x" to prove they cannot collide with the x-axis key
    rows = [["2018-01", "x", 1], ["2018-01", "y", 2], ["2018-02", "x", 3], ["2018-02", "y", 4]]
    c = build_chart(["month", "tier", "mrr"], rows)
    assert c["type"] == "line" and sorted(c["series"]) == ["x", "y"]
    assert c["data"][0] == {"__x": "2018-01", "x": 1, "y": 2}
    assert c["data"][1] == {"__x": "2018-02", "x": 3, "y": 4}


def test_text_only_and_empty_are_grid():
    assert build_chart(["a", "b"], [["x", "y"], ["z", "w"]])["type"] == "grid"
    assert build_chart(["a"], [])["type"] == "grid"


def test_tiles_top_share():
    t = build_tiles(["cat", "rev"], [["a", 75], ["b", 25]])
    top = next(x for x in t if x["label"].startswith("Top"))
    assert top["value"] == "a" and top["sub"] == "75.0% of total"
