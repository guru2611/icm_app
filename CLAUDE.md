# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# ICM System

Incentive Compensation Management system backed by BigQuery, with Python tooling, an AI-powered investigation pipeline, and a proactive dispute prediction engine.

## Commands

```bash
# Install (editable mode — required so agents/tools/db are importable as packages)
pip install -e .

# Run the Flask backend
python server.py          # http://localhost:5000

# Run the React frontend
cd ui && npm run dev      # http://localhost:5173

# Run agent CLI demos (standalone testing)
python -m agents.intake.agent
python -m agents.planner.agent
python -m agents.investigation.agent

# First-time BigQuery setup (run once, in order)
python -c "from db.tables import deploy_full_icm_schema; deploy_full_icm_schema('glossy-buffer-411806', 'icm_analytics')"
python -c "from db.inserts import load_fiscal_calendar; load_fiscal_calendar('glossy-buffer-411806', 'icm_analytics')"
python db/seed.py
python db/pay_seed.py
python db/views.py
```

## Architecture

```
User query (text)
      │
      ▼
┌─────────────────┐
│  Intake Agent   │  claude.messages.parse() → IntakeResult (structured output)
│ agents/intake/  │  (employee_number, sale_date, query_type, summary)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Planner Agent   │  LangGraph StateGraph → InvestigationPlan (ordered ToolCall steps)
│ agents/planner/ │
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│ Investigation Agent  │  LangGraph StateGraph — loops execute_step until done,
│ agents/investigation/│  then synthesize → InvestigationReport (ForensicSummary)
└──────────────────────┘
```

Both the Planner and Investigation agents use **LangGraph** `StateGraph` for flow control. The Intake and Investigation synthesis steps use `client.messages.parse(output_format=PydanticModel)` for structured output — not tool use.

### Python API

```python
from agents.intake import parse_query
from agents.planner import plan_investigation
from agents.investigation import investigate

intake = parse_query(employee_number=145, query_text="I made a sale in November but never got my commission.")
plan   = plan_investigation(intake)
report = investigate(plan)
print(report.summary.root_cause)
```

### Server routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Built-in HTML test page |
| `GET` | `/employee/<id>` | Employee profile lookup — returns name, job_code, location_name, store_name, district, market, territory, supervisor |
| `POST` | `/investigate` | SSE stream — runs full 3-stage pipeline, yields `{stage, result}` events |
| `GET` | `/dispute-predictor` | System-wide payment gap analysis — returns summary stats + disputes list |
| `GET` | `/audit-log?date=YYYY-MM-DD` | SOX audit log for a given date — returns events + summary stats (defaults to today) |
| `POST` | `/slack` | Slack slash command handler |

SSE event stages: `intake` → `planner` → `investigation` → `done`

## Project Structure

```
icm-system/
├── agents/
│   ├── intake/              # Intake agent — text → IntakeResult
│   ├── planner/             # Planner agent — IntakeResult → InvestigationPlan
│   └── investigation/       # Investigation agent — plan → InvestigationReport
├── tools/
│   └── icm_tools.py         # All BigQuery-backed tool functions (parameterised queries)
├── db/
│   ├── tables.py            # DDL — creates all BigQuery tables (including Audit_Log)
│   ├── inserts.py           # Loads Fiscal_Calendar_Details (16 rows)
│   ├── seed.py              # Populates all tables with sample data
│   ├── pay_seed.py          # Populates Worker_Pay_Details (biweekly, with intentional gaps)
│   ├── views.py             # Creates 7 analytical views
│   └── audit.py             # SOX audit layer — log_event() (fire-and-forget) + get_audit_log(date)
├── ui/                      # React + Vite frontend (Tailwind CSS)
│   └── src/
│       ├── App.jsx                          # Root — tab nav, SSE handler
│       └── components/
│           ├── Header.jsx
│           ├── InputForm.jsx                # Employee lookup + query form
│           ├── Pipeline.jsx
│           ├── IntakeCard.jsx
│           ├── PlannerCard.jsx
│           ├── InvestigationCard.jsx
│           ├── DisputePredictorPage.jsx     # Proactive gap dashboard
│           ├── AuditPage.jsx                # SOX audit log viewer (date picker + events table)
│           ├── AgentCard.jsx
│           ├── StatusBadge.jsx
│           ├── Connector.jsx
│           └── Skeleton.jsx
├── dispute_predictor.py     # BigQuery gap analysis: vw_Commission_Estimate vs Worker_Pay_Details
├── server.py                # Flask backend — all routes + Slack handler
├── pyproject.toml
└── .env                     # ANTHROPIC_API_KEY, SLACK_SIGNING_SECRET, SLACK_BOT_TOKEN
```

## BigQuery

- **Project:** `glossy-buffer-411806` | **Dataset:** `icm_analytics`
- Billing is not enabled — use `load_table_from_json` for writes (free). DDL and reads work fine. SQL INSERT/UPDATE/DELETE are blocked.

### Tables

| Table | Description |
|---|---|
| `Worker_Profile` | Employee registry — number, name, supervisor |
| `Worker_History` | Job assignments over time — location, job code, start/end dates |
| `Location_Details` | Store hierarchy — store → district → market → territory |
| `Plan_Details` | Comp plan versions — rates, period type, applicable level |
| `Plan_assignment` | Employee plan enrollments with start/end dates |
| `Sale_Details` | Individual sales transactions |
| `Fiscal_Calendar_Details` | Fiscal year/quarter definitions |
| `Worker_Pay_Details` | Actual commission payments — amount, period, plan |
| `Vendor_Program_Details` | Vendor bonus program mappings |
| `Audit_Log` | Append-only SOX audit trail — every data access and investigation is written here via `db/audit.py` |

### Views

| View | Purpose |
|---|---|
| `vw_Employee_Roster` | Denormalized profile: name, job, location hierarchy, supervisor |
| `vw_Active_Plan_Assignments` | Currently active plan enrollments per employee |
| `vw_Sales_With_Fiscal_Period` | Transactions enriched with fiscal quarter |
| `vw_Employee_Sales_by_Period` | Sales totals per employee per fiscal quarter |
| `vw_Location_Sales_by_Period` | Sales totals per location per fiscal quarter |
| `vw_Commission_Estimate` | Expected commission per employee per plan per quarter — source of truth for dispute detection |
| `vw_Manager_Team_Summary` | Manager's direct reports with per-rep and team sales |

### Fiscal Year
Runs **Feb 1 → Jan 31**. FY2026 = Feb 2025 – Jan 2026.
Quarters: Q1 Feb–Apr · Q2 May–Jul · Q3 Aug–Oct · Q4 Nov–Jan

### Org Hierarchy
```
DM (101–105)
└── MGR (106–120)
    ├── SREP (121–140)
    └── REP (141–200)
```

### Comp Plans

| ID | Name | Level | Period | Rate |
|---|---|---|---|---|
| 1 | Standard Rep Commission | Employee | Monthly | 5→6% |
| 2 | Senior Rep Commission | Employee | Monthly | 8→9% |
| 3 | Manager Override | Location | Quarterly | 3→4% |
| 4 | District Manager Plan | Location | Quarterly | 2% |
| 5 | Apple Vendor Bonus | Employee | Monthly | 10→12% |
| 6 | Samsung Vendor Bonus | Employee | Monthly | 8→9% |
| 7 | Google Vendor Bonus | Employee | Monthly | 7→8% |

`Plan_applicable_Level`: `Employee` = commission on own sales; `Location` = commission on location's total sales (manager overrides).

### Intentional Payment Gaps (seed data)

`db/pay_seed.py` deliberately skips these employees to simulate disputes:
- **REP:** 145, 158, 172, 183
- **SREP:** 127, 131
- **MGR:** 108
- **DM:** 103

These will always appear in the Dispute Predictor results.

## Tool Functions (`tools/icm_tools.py`)

All functions return plain dicts/lists and use parameterised queries.

| Function | Returns |
|---|---|
| `is_employee_valid(employee_number)` | `bool` |
| `get_employee_profile(employee_number)` | `dict \| None` — from `vw_Employee_Roster` |
| `get_employee_location_on_date(employee_number, date)` | `dict \| None` |
| `get_employee_sales_on_date(employee_number, date)` | `list[dict]` |
| `get_employee_sales_in_period(employee_number, start_date, end_date)` | `list[dict]` |
| `get_employee_sales_summary(employee_number, fiscal_year, quarter_number)` | `dict \| None` |
| `get_employee_plans_on_date(employee_number, date)` | `list[dict]` |
| `get_sales_qualifying_for_employee_plan(employee_number, date)` | `dict` — `{qualified, sales, qualifying_plans, reason}` |
| `get_sales_qualifying_for_location_plan(employee_number, date)` | `dict` — `{qualified, sales, location, qualifying_plans, location_day_sales, reason}` |
| `get_commission_estimate(employee_number, fiscal_year, quarter_number)` | `list[dict]` |
| `get_manager_team_summary(manager_employee_number, fiscal_year, quarter_number)` | `list[dict]` |

## Dispute Predictor (`dispute_predictor.py`)

`get_dispute_predictions()` runs a BigQuery query that:
1. Aggregates `Worker_Pay_Details` into fiscal quarters (payments are biweekly; must be summed per quarter to compare)
2. Left-joins against `vw_Commission_Estimate` (expected commission per employee/plan/quarter)
3. Returns rows where `Estimated_Commission > 0` and `Total_Paid < Estimated_Commission`

Returns a dict:
```python
{
  "disputes": [list of individual gap records],
  "summary": {
    "affected_employees": int,
    "total_discrepancy": float,
    "total_owed": float,
    "total_paid": float,
    "by_job_code": [{"job_code", "employees", "plan_gaps", "discrepancy"}]
  }
}
```

## UI — Tab Navigation

The React UI (`ui/src/App.jsx`) has three tabs rendered with CSS `hidden` (not conditional rendering) so components stay mounted and data is not re-fetched on tab switch:

- **Tab 1: Investigation Pipeline** — employee lookup form + 3-stage SSE pipeline
- **Tab 2: Dispute Predictor** — loads once on mount, refreshes only on button click
- **Tab 3: Audit Log** — date-filtered view of `Audit_Log`; loads on mount and on date change

### InputForm behavior
- Employee number field is `type="text"` with `inputMode="numeric"` — no browser spinner arrows
- Debounced lookup (400ms) hits `GET /employee/<id>` and shows a profile card (name, job badge, store, location, district, market, territory, supervisor) on success
- Query textarea and submit button are disabled until a valid employee is found
- Submit button is also disabled while the employee lookup is in-flight

### Vite proxy routes (dev only)
All these paths are proxied from `localhost:5173` → `localhost:5000`:
- `/investigate`
- `/slack`
- `/dispute-predictor`
- `/employee`
- `/audit-log`

## SOX Audit Layer (`db/audit.py`)

Every sensitive data access and investigation is logged to `Audit_Log` via `log_event()`, which writes on a daemon thread (fire-and-forget — never blocks the request path). Audit failures are silently printed to stderr; they never crash the app.

Actor identity comes from the `X-Actor` HTTP header. In production this should be set by a trusted auth proxy (Google IAP, JWT middleware, etc.) — it is never trusted from an unauthenticated client. Unauthenticated requests log as `"anonymous"`.

The `/investigate` route logs its own audit event inside the SSE generator (to capture duration). All other routes are logged by the `@app.after_request` hook in `server.py`.

## Slack Integration

Slash command format: `/icm <employee_number> <query text>`

Local dev: start Flask → `ngrok http 5000` → set Request URL to `https://<ngrok-url>/slack` in Slack app settings.
Required scopes: `chat:write`
