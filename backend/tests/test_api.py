import pytest
from fastapi.testclient import TestClient
from fakes import ScriptedLLM

from app import llm as llm_mod
from app.main import app


@pytest.fixture()
def client(index):
    with TestClient(app) as c:
        yield c


def test_health_and_schema(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["database"]["tables"] == 8
    s = client.get("/api/schema").json()
    assert {t["name"] for t in s["tables"]} >= {"orders", "customers"} and len(s["relationships"]) == 7


def test_ask_without_llm_returns_503(client, monkeypatch):
    monkeypatch.setattr(llm_mod, "_llm", None)
    monkeypatch.setenv("ASKDATA_ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("ASKDATA_GEMINI_API_KEY", "")
    monkeypatch.setenv("ASKDATA_LLM_PROVIDER", "")
    from app.config import get_settings
    get_settings.cache_clear()
    assert client.post("/api/ask", json={"question": "orders by status"}).status_code == 503
    get_settings.cache_clear()


def test_ask_roundtrip_and_history(client, monkeypatch):
    good = "```sql\nSELECT o.status, COUNT(*) AS n FROM orders o GROUP BY o.status\n```"
    monkeypatch.setattr(llm_mod, "_llm", ScriptedLLM([good]))
    r = client.post("/api/ask", json={"question": "orders by status"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["id"] and body["row_count"] == 4
    hist = client.get("/api/history").json()
    assert hist[0]["question"] == "orders by status"
    again = client.get(f"/api/history/{body['id']}").json()
    assert again["sql"] == body["sql"]


def test_input_validation(client):
    assert client.post("/api/ask", json={"question": "hi"}).status_code == 422
    assert client.post("/api/ask", json={"question": "x" * 501}).status_code == 422
    assert client.get("/api/history/doesnotexist").status_code == 404
