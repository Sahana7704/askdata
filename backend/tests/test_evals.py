import json

from app import store
from app.evals import load_golden, result_signature, run_eval, same_result
from app.db import run_readonly


class OracleLLM:
    """Answers every golden question with its reference SQL, so a correct harness must score 100%."""

    def __init__(self, wrong_for: set[str] = frozenset()):
        self.by_q = {g["question"]: g["reference_sql"] for g in load_golden()}
        self.wrong_for = wrong_for

    def complete(self, system, user, max_tokens=None):
        q = user.split("Question: ", 1)[-1].strip() if "Question: " in user else user
        q = q.split("\n")[0]
        sql = self.by_q[q]
        if q in self.wrong_for:
            sql = "SELECT 1 AS x"
        return f"```sql\n{sql}\n```"


def test_all_reference_queries_execute_and_are_non_empty():
    for g in load_golden():
        r = run_readonly(g["reference_sql"])
        assert r.rows, g["id"]


def test_signature_ignores_order_names_and_float_noise():
    ref = result_signature(["a", "b"], [["x", 1.0], ["y", 2.004]])
    assert same_result(ref, ["name", "n"], [["y", 2.0], ["x", 1]])
    assert same_result(ref, ["n", "name"], [[1, "x"], [2, "y"]])          # column order ignored
    assert not same_result(ref, ["a", "b"], [["x", 1], ["y", 3]])
    assert not same_result(ref, ["a"], [["x"], ["y"]])                     # column count differs


def test_oracle_scores_100_percent(index):
    rid = store.create_eval({})
    out = run_eval(OracleLLM(), rid, limit=8, config_keys=["baseline", "repair"])
    assert [s["accuracy"] for s in out["summary"]] == [100.0, 100.0]
    assert all(r["correct"] for r in out["records"])


def test_wrong_answers_are_counted_and_diagnosed(index):
    golden = load_golden()[:4]
    wrong = {golden[0]["question"], golden[1]["question"]}
    out = run_eval(OracleLLM(wrong_for=wrong), store.create_eval({}), limit=4, config_keys=["schema"])
    s = out["summary"][0]
    assert s["correct"] == 2 and s["accuracy"] == 50.0 and s["wrong_result"] == 2
    fails = [r for r in out["records"] if not r["correct"]]
    assert {f["failure"] for f in fails} == {"wrong_result"} and fails[0]["expected_sql"]
    json.dumps(out)  # must be JSON-serialisable for storage
