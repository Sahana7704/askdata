from fakes import ScriptedLLM

from app.agent import AgentConfig, ask

GOOD = "```sql\nSELECT o.status, COUNT(*) AS n FROM orders o GROUP BY o.status ORDER BY n DESC\n```"


def steps(r):
    return [(s["step"], s["status"]) for s in r["trace"]]


def test_happy_path(index):
    r = ask("orders by status", ScriptedLLM([GOOD]), index=index)
    assert r["status"] == "ok" and r["repairs"] == 0 and r["row_count"] == 4
    assert r["summary"] == "Scripted summary." and r["chart"]["type"] == "bar"
    assert steps(r)[0] == ("schema", "ok") and steps(r)[-1] == ("summarize", "ok")


def test_repairs_after_bad_column(index):
    bad = "```sql\nSELECT o.status FROM orders o WHERE o.discount_code IS NULL\n```"
    llm = ScriptedLLM([bad, GOOD])
    r = ask("orders by status", llm, index=index)
    assert r["status"] == "ok" and r["repairs"] == 1
    assert "discount_code" in r["first_error"]
    # the repair prompt carried the validator's error back to the model
    assert "discount_code" in llm.calls[1][1]


def test_gives_up_after_max_repairs(index):
    bad = "```sql\nSELECT nope FROM orders\n```"
    r = ask("x", ScriptedLLM([bad] * 5), config=AgentConfig(max_repairs=2), index=index)
    assert r["status"] == "failed" and r["repairs"] == 2 and r["rows"] == []


def test_no_repair_when_disabled(index):
    bad = "```sql\nSELECT nope FROM orders\n```"
    r = ask("x", ScriptedLLM([bad, GOOD]), config=AgentConfig(max_repairs=0), index=index)
    assert r["status"] == "failed" and r["repairs"] == 0


def test_write_statements_are_refused_without_retry(index):
    llm = ScriptedLLM(["```sql\nDELETE FROM orders\n```"] * 3)
    r = ask("delete all orders", llm, index=index)
    assert r["status"] == "failed" and r["repairs"] == 0 and "Only SELECT" in r["error"]
    assert len(llm.calls) == 1


def test_unanswerable(index):
    r = ask("weather?", ScriptedLLM(["CANNOT_ANSWER: no weather data"]), index=index)
    assert r["status"] == "unanswerable" and r["error"] == "no weather data"


def test_zero_count_triggers_one_repair(index):
    first = "```sql\nSELECT COUNT(*) AS n FROM orders WHERE status='shipping'\n```"
    second = "```sql\nSELECT COUNT(*) AS n FROM orders WHERE status='shipped'\n```"
    r = ask("shipped orders", ScriptedLLM([first, second]), index=index)
    assert r["repairs"] == 1 and r["rows"][0][0] > 0


def test_empty_result_survives_failed_repair(index):
    first = "```sql\nSELECT COUNT(*) AS n FROM orders WHERE status='shipping'\n```"
    r = ask("x", ScriptedLLM([first, "```sql\nSELECT nope FROM orders\n```"] * 3), index=index)
    assert r["status"] == "ok" and r["rows"] == [[0]]


def test_summary_failure_does_not_fail_the_answer(index):
    class Flaky(ScriptedLLM):
        def complete(self, system, user, max_tokens=None):
            if system.startswith("You write a short factual summary"):
                raise RuntimeError("boom")
            return super().complete(system, user, max_tokens)

    r = ask("orders by status", Flaky([GOOD]), index=index)
    assert r["status"] == "ok" and r["summary"].startswith("Returned 4 rows")


def test_llm_outage_is_reported(index):
    class Down:
        def complete(self, *a, **k):
            raise RuntimeError("api down")

    r = ask("anything", Down(), index=index)
    assert r["status"] == "failed" and "LLM error" in r["error"]


def test_cannot_answer_inside_code_block_is_a_refusal(index):
    # Gemini sometimes wraps the refusal in ```sql ... ``` instead of replying in plain text
    r = ask("weather?", ScriptedLLM(["```sql\nCANNOT_ANSWER: The database does not contain information about weather.\n```"]), index=index)
    assert r["unanswerable"] is True
    assert "weather" in r["error"].lower() or "weather" in (r.get("summary") or "").lower()


def test_extract_sql_variants():
    from app.llm import extract_sql
    assert extract_sql("```sql\nSELECT 1\n```") == ("SELECT 1", None)
    assert extract_sql("CANNOT_ANSWER: nope") == (None, "nope")
    assert extract_sql("```\nCANNOT_ANSWER: nope\n```") == (None, "nope")


def test_extract_sql_strips_stray_language_tag():
    from app.llm import extract_sql
    for raw in ["``` sql\nSELECT 1\n```", "```\nsql\nSELECT 1\n```", "```\nSQL SELECT 1\n```", "```postgresql\nSELECT 1\n```"]:
        assert extract_sql(raw) == ("SELECT 1", None), raw
