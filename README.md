# ICM System

An AI-powered **Incentive Compensation Management** system. Employees submit free-text compensation queries; a three-stage agent pipeline parses the query, plans an investigation, executes it against BigQuery, and returns a forensic summary identifying what went wrong and why.

---

## Architecture

```
User query (text)
      │
      ▼
┌─────────────────┐
│  Intake Agent   │  Parses free text → structured IntakeResult
│ agents/intake/  │  (employee_number, sale_date, query_type, summary)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Planner Agent   │  Routes by query_type → ordered list of tool calls
│ agents/planner/ │  (InvestigationPlan with ToolCall steps)
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│ Investigation Agent  │  Executes each tool call against BigQuery
│ agents/investigation/│  Synthesises evidence → ForensicSummary
└──────────────────────┘
         │
         ▼
  InvestigationReport
  (expected / actual / root_cause / recommendation / confidence)
```

Both the Planner and Investigation agents use **LangGraph** `StateGraph` for their internal flow control.

---

## Project Structure

```
icm-system/
├── agents/
│   ├── intake/           # Intake agent — text → IntakeResult
│   │   ├── agent.py
│   │   └── __init__.py
│   ├── planner/          # Planner agent — IntakeResult → InvestigationPlan
│   │   ├── agent.py
│   │   └── __init__.py
│   └── investigation/    # Investigation agent — plan → InvestigationReport
│       ├── agent.py
│       └── __init__.py
├── tools/
│   ├── icm_tools.py      # All BigQuery-backed tool functions
│   └── __init__.py
├── db/
│   ├── tables.py         # DDL — creates all BigQuery tables
│   ├── inserts.py        # Loads Fiscal_Calendar_Details (16 rows)
│   ├── seed.py           # Populates all tables with sample data
│   └── views.py          # Creates analytical views
├── server.py             # Flask test server for the intake agent
├── pyproject.toml
└── .env                  # ANTHROPIC_API_KEY (do not commit)
```

---

## Setup

```bash
# 1. Install dependencies (editable mode makes all packages importable)
pip install -e .

# 2. Set your API key
echo "ANTHROPIC_API_KEY=sk-..." > .env

# 3. Authenticate with Google Cloud (BigQuery)
gcloud auth application-default login
```

### First-time database setup

Run these once in order to build the BigQuery dataset:

```bash
python -c "from db.tables import deploy_full_icm_schema; deploy_full_icm_schema('glossy-buffer-411806', 'icm_analytics')"
python -c "from db.inserts import load_fiscal_calendar; load_fiscal_calendar('glossy-buffer-411806', 'icm_analytics')"
python db/seed.py
python db/views.py
```

---

## Running the pipeline

### As a Python API

```python
from agents.intake import parse_query
from agents.planner import plan_investigation
from agents.investigation import investigate

# 1. Parse the free-text query
intake = parse_query(employee_number=145, query_text="I made a sale in November but never got my commission.")

# 2. Build the investigation plan
plan = plan_investigation(intake)

# 3. Execute and get the forensic report
report = investigate(plan)

print(report.summary.root_cause)
print(report.summary.recommendation)
```

### As a web server

```bash
python server.py   # http://localhost:5000
```

The server exposes a browser UI at `GET /` and a JSON API at `POST /parse`:

```bash
curl -X POST http://localhost:5000/parse \
     -H "Content-Type: application/json" \
     -d '{"employee_number": 145, "query_text": "I never received my November commission."}'
```

### Agent CLI demos

Each agent can be run standalone for testing:

```bash
python -m agents.intake.agent
python -m agents.planner.agent
python -m agents.investigation.agent
```

---

## BigQuery

- **Project:** `glossy-buffer-411806`
- **Dataset:** `icm_analytics`
- Billing is not enabled — use `load_table_from_json` for writes (free). DDL and reads work fine.

### Fiscal calendar

Fiscal year runs **Feb 1 → Jan 31**. FY2026 = Feb 2025 – Jan 2026.

| Quarter | Months |
|---------|--------|
| Q1 | Feb – Apr |
| Q2 | May – Jul |
| Q3 | Aug – Oct |
| Q4 | Nov – Jan |

### Org hierarchy

```
DM  (101–105)
└── MGR  (106–120)
    ├── SREP (121–140)
    └── REP  (141–200)
```

---

## Query types

| Type | Triggers on |
|------|-------------|
| `commission_not_received` | "didn't receive", "missing", "not paid", "never got" |
| `incorrect_commission_received` | "wrong amount", "too low/high", "miscalculated", "short-paid" |
| `how_much_commission` | "how much", "what will I get", "estimate", "what am I owed" |
| `other` | anything else |
