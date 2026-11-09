# AskData — natural-language analytics with a safe, evaluated SQL agent

Ask questions about a database in plain English. AskData retrieves the relevant part of the schema, has an LLM write **one read-only PostgreSQL query**, validates it, runs it with several layers of protection, repairs it if it fails, and returns a summary, an auto-selected chart, the result table, and the SQL itself.

The point of the project is not "an LLM writes SQL" — it's **making that trustworthy and measurable**: a safety validator, a bounded self-repair loop, and an evaluation harness that quantifies what each component contributes.

```
question ─► retrieve schema ─► generate SQL ─► validate ─► execute ─► summarise + chart
                                    ▲              │           │
                                    └──── repair ◄─┴───────────┘   (bounded; errors are fed back to the model)
```

Built with **FastAPI · LangGraph · SQLAlchemy · sqlglot · PostgreSQL · Anthropic API · Next.js · Tailwind · Recharts**.

## Quick start

### Docker (everything, one command)

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # needed to answer questions; Schema page works without it
docker compose up --build
# web: http://localhost:3000    api docs: http://localhost:8000/docs
```

### Local development

```bash
# 1. Postgres with the demo data (any Postgres 14+; admin URL needs CREATE rights)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python data/seed.py --admin-url postgresql://USER:PASS@localhost:5432/shop

# 2. API
cp .env.example .env        # add ASKDATA_ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000

# 3. Web
cd ../frontend && cp .env.example .env.local && npm install && npm run dev
```

## How it works

| Step | What happens | Where |
|---|---|---|
| **Schema retrieval** | Tables/columns/foreign keys are introspected once (including `COMMENT ON` text, low-cardinality text values such as `status`, and date ranges). A question is matched against tables with BM25, then expanded along foreign keys (parent lookup tables, and bridge tables that connect two matched tables). Only those tables go into the prompt. | `app/schema_index.py` |
| **SQL generation** | One LLM call with rules (PostgreSQL only, qualify columns, use listed sample values, relative dates are measured from the latest date in the data, `CANNOT_ANSWER` for unanswerable questions). | `app/prompts.py`, `app/llm.py` |
| **Validation** | sqlglot parses the statement and enforces: exactly one statement, read-only `SELECT`/`WITH`/set operations, no writes/DDL/`COPY`/`SELECT INTO`/row locks, no dangerous functions (`pg_sleep`, `pg_read_file`, `dblink`, …), no system schemas, every table exists, every column resolves (with "did you mean" hints), `LIMIT` applied. Policy violations are refused outright — never retried. | `app/validator.py` |
| **Execution** | Runs in a `READ ONLY` transaction with a statement timeout and a row cap, as a database role that only has `SELECT`. | `app/db.py` |
| **Repair loop** | Validator or database errors — and empty/zero-count results on the first attempt — are sent back to the model (max 2 retries). If the error says a table/column is missing, the full schema is shown on the retry. An empty-but-valid first result is kept if every repair fails. | `app/agent.py` (LangGraph) |
| **Answer** | A short factual summary (the model is told to use only numbers present in the rows), deterministic insight tiles, and a chart chosen by rules — not by the LLM. | `app/charts.py` |

### Safety model

Defence in depth — any single layer failing should not allow a write: (1) sqlglot allow-list, (2) read-only DB role, (3) `READ ONLY` transaction, (4) statement timeout + row cap, (5) per-IP rate limit on LLM-backed endpoints. User questions are treated as data; safety is enforced in code, not in the prompt. **There is no authentication** — put the API behind auth before exposing it beyond localhost, and use a role scoped to the tables you're happy to expose.

## Evaluation

`POST /api/eval/run` (or the **Run new eval** button) executes a golden set of **32 questions** (`backend/eval/golden_set.json`, regenerate with `eval/build_golden_set.py`) across four types — simple aggregations, multi-table joins, temporal bucketing, and window functions/CTEs — under three configurations:

1. **Baseline** — full schema in the prompt, no repair
2. **+ Schema retrieval**
3. **+ Repair loop** (the production pipeline)

**Metric: execution accuracy.** A generated query is correct if running it returns the same multiset of rows as the hand-written reference query (row order and column names ignored; numbers compared to 2 decimals), the same approach used by text-to-SQL benchmarks such as Spider. Also reported: median/P95 latency, repair rate, how many queries were healed by a retry, and invalid-SQL vs wrong-result failures, with expected-vs-actual SQL for every miss.

**Caveats, stated plainly:** the golden set is small, written by the author, and runs on a *synthetic* database, so treat results as a regression benchmark for this project rather than a general text-to-SQL score. Results depend on the model you configure. A full run makes roughly 100 LLM calls.

### Results

<!-- Fill in from your own first real run of the Evaluation page (model: ______, date: ______). -->

| Configuration | Execution accuracy | Median latency | Repair rate |
|---|---|---|---|
| Baseline | — | — | n/a |
| + Schema retrieval | — | — | n/a |
| + Repair loop | — | — | — |

## Demo data

`data/seed.py` generates a **synthetic** e-commerce dataset (customers, sellers, categories, products, orders, order items, payments, reviews; ~15k orders across 2017–2018) from a seeded random generator, with `COMMENT ON` descriptions that the agent uses as business context. To point AskData at your own PostgreSQL database, set `ASKDATA_DATABASE_URL` to a read-only role; add `COMMENT ON TABLE/COLUMN` descriptions for best results and edit `EXAMPLES` in `app/main.py`.

## Tests

```bash
cd backend && pytest -q        # 52 tests; needs the seeded demo DB; no API key needed
```

Tests use a scripted stand-in for the LLM (`tests/fakes.py`) to exercise the real graph, validator, executor and API deterministically: safety rejections, repair paths, empty-result handling, LLM outage handling, chart selection, retrieval, and the eval harness itself (an "oracle" model must score 100%, wrong answers must be counted and diagnosed). They verify the *machinery*; the model's actual SQL quality is what the evaluation measures.

## Project layout

```
backend/   app/{agent,validator,schema_index,db,charts,llm,prompts,evals,store,main}.py
           data/seed.py   eval/golden_set.json   tests/
frontend/  app/{page,schema,evaluation}   components/   lib/
docker-compose.yml   .github/workflows/ci.yml
```

## Known limitations / next steps

- Retrieval is lexical (BM25) plus foreign-key expansion. Embedding-based retrieval (e.g. pgvector) is a natural upgrade for large or poorly named schemas; the `SchemaIndex.retrieve` interface is the only thing to swap.
- Single-turn: no conversational follow-ups ("now break that down by state").
- PostgreSQL only; the validator and executor are dialect-specific.
- Model summaries can in principle misstate numbers; the prompt constrains this but there's no automated numeric-faithfulness check yet.
- No auth, multi-tenant isolation, or query result caching.
