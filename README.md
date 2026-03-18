# ICM System — AI-Powered Incentive Compensation Management

An end-to-end platform that uses a multi-agent AI pipeline to investigate, diagnose, and proactively detect incentive compensation disputes — replacing weeks of manual payroll investigation with seconds of automated forensic analysis.

---

## The Problem

Incentive compensation is one of the most dispute-prone areas in sales organizations. When a rep believes they were underpaid or missed a commission entirely, the investigation process is slow, opaque, and manual:

- Payroll teams must cross-reference sales records, plan assignments, eligibility rules, and payment histories across multiple systems
- Disputes can take days or weeks to resolve, damaging trust between sales and finance
- Underpayments often go unreported — reps give up before escalating
- There is no proactive mechanism to catch payment gaps before employees notice them

**This system solves all three dimensions:** reactive investigation via natural language, real-time forensic analysis via AI agents, and proactive gap detection via automated dispute prediction.

---

## What It Does

### 1. Investigation Pipeline (Reactive)
An employee submits a free-text compensation question. The system automatically:
- Identifies the employee and validates their profile
- Classifies the query type
- Plans a structured BigQuery investigation
- Executes the investigation and synthesizes a forensic report with root cause and recommendation

### 2. Dispute Predictor (Proactive)
A system-wide scan that identifies every employee who had qualifying sales and an active compensation plan but received no payment — before they ever file a complaint.

### 3. Slack Integration
Sales reps can submit queries directly from Slack via a slash command and receive formatted investigation results without ever leaving their workflow.

---

## Live Demo

| Layer | URL |
|---|---|
| React Frontend | http://localhost:5173 |
| Flask Backend | http://localhost:5000 |

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        React UI (Vite)                       │
│   Tab 1: Investigation Pipeline  │  Tab 2: Dispute Predictor │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP / SSE
┌────────────────────▼────────────────────────────────────────┐
│                    Flask Backend (server.py)                  │
│  POST /investigate  │  GET /dispute-predictor                │
│  GET  /employee/:n  │  POST /slack                           │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┼──────────────┐
         ▼           ▼              ▼
   Intake Agent  Planner Agent  Investigation Agent
   (Claude API)  (LangGraph)    (LangGraph + Claude API)
         │           │              │
         └───────────┴──────────────┘
                     │
              BigQuery Tools
              (icm_tools.py)
                     │
         ┌───────────▼───────────┐
         │   Google BigQuery      │
         │   Project: icm_analytics│
         └───────────────────────┘
```

### Agent Pipeline — Step by Step

```
User query (natural language)
        │
        ▼
┌───────────────────┐
│   Intake Agent    │  claude.messages.parse() → IntakeResult
│   agents/intake/  │  Extracts: employee_number, sale_date,
└────────┬──────────┘           query_type, summary
         │
         ▼
┌───────────────────┐
│  Planner Agent    │  LangGraph StateGraph → InvestigationPlan
│  agents/planner/  │  Produces: ordered list of BigQuery tool
└────────┬──────────┘  calls to execute, with fiscal period
         │
         ▼
┌────────────────────────┐
│  Investigation Agent   │  LangGraph StateGraph — executes each
│  agents/investigation/ │  tool call, collects evidence, then
└────────────────────────┘  synthesizes → InvestigationReport
         │
         ▼
  ForensicSummary
  ├── Expected   (what the employee should have received)
  ├── Actual     (what the records show they received)
  ├── Root Cause (why the discrepancy exists)
  ├── Recommendation (next action)
  └── Confidence (High / Medium / Low)
```

---

## Key Features

### Investigation Pipeline
- **Natural language input** — reps describe their issue in plain English, no forms or structured data entry
- **Live SSE streaming** — the UI updates in real time as each agent stage completes, showing intermediate results
- **Employee validation with profile lookup** — entering an employee number instantly fetches and displays their name, job level, location, district, market, territory, and supervisor
- **Four query types** handled automatically:
  - `commission_not_received` — payment entirely missing
  - `incorrect_commission_received` — wrong amount paid
  - `how_much_commission` — forward-looking estimate
  - `other` — escalated to compensation admin
- **Forensic evidence trail** — every BigQuery tool call is logged with OK/ERR status so the investigation is fully auditable

### Dispute Predictor
- **System-wide proactive scan** — not tied to any individual complaint; runs against all employees simultaneously
- **Gap detection logic** — cross-references `vw_Commission_Estimate` (what should have been paid) against `Worker_Pay_Details` (what was actually paid), aggregated to the correct fiscal period
- **Summary dashboard** with four stat cards: affected employees, total discrepancy, total owed, total paid
- **Job-level breakdown bar** — visual proportional breakdown of discrepancy by Rep / Sr. Rep / Manager / District Manager
- **Sortable, filterable disputes table** — sort by any column, free-text filter by name, ID, plan, or job level; color-coded job badges and red gap pills
- **On-demand refresh** — data loads once on first visit and only re-queries when the Refresh button is clicked

### Slack Integration
- Slash command: `/icm <employee_number> <query text>`
- Responds immediately with an acknowledgment, runs the full pipeline in a background thread
- Posts formatted Block Kit results back to the channel with all forensic findings

---

## Data Model

### BigQuery Tables

| Table | Description |
|---|---|
| `Worker_Profile` | Employee registry — number, name, supervisor |
| `Worker_History` | Job assignments over time — location, job code, start/end dates |
| `Location_Details` | Store hierarchy — store → district → market → territory |
| `Plan_Details` | Compensation plan versions — rates, period type, applicable level |
| `Plan_assignment` | Which employees are enrolled in which plans, and when |
| `Sale_Details` | Individual sales transactions with date, location, amount |
| `Fiscal_Calendar_Details` | Fiscal year/quarter definitions (Feb–Jan fiscal year) |
| `Worker_Pay_Details` | Actual commission payments made — amount, period, plan |
| `Vendor_Program_Details` | Vendor bonus program mappings to comp plans |

### Analytical Views

| View | Purpose |
|---|---|
| `vw_Employee_Roster` | Denormalized employee profile with current job, location hierarchy, supervisor name |
| `vw_Active_Plan_Assignments` | All currently active comp plan enrollments per employee |
| `vw_Sales_With_Fiscal_Period` | Each transaction enriched with employee name, location hierarchy, and fiscal quarter |
| `vw_Employee_Sales_by_Period` | Sales totals per employee per fiscal year and quarter |
| `vw_Location_Sales_by_Period` | Sales totals per location per fiscal year and quarter (feeds manager override plans) |
| `vw_Commission_Estimate` | Expected commission per employee per plan per fiscal quarter — the source of truth for dispute detection |
| `vw_Manager_Team_Summary` | Manager's direct reports with per-rep and team total sales by quarter |

### Compensation Plans

| ID | Plan | Applies To | Period | Rate |
|---|---|---|---|---|
| 1 | Standard Rep Commission | Individual sales | Monthly | 5–6% |
| 2 | Senior Rep Commission | Individual sales | Monthly | 8–9% |
| 3 | Manager Override | Location total sales | Quarterly | 3–4% |
| 4 | District Manager Plan | Location total sales | Quarterly | 2% |
| 5 | Apple Vendor Bonus | Individual sales | Monthly | 10–12% |
| 6 | Samsung Vendor Bonus | Individual sales | Monthly | 8–9% |
| 7 | Google Vendor Bonus | Individual sales | Monthly | 7–8% |

### Org Hierarchy

```
District Manager — DM  (Emp 101–105)
└── Manager        — MGR (Emp 106–120)
    ├── Sr. Rep    — SREP (Emp 121–140)
    └── Rep        — REP  (Emp 141–200)
```

### Fiscal Calendar

Fiscal year runs **February 1 → January 31**.

| Quarter | Months | Example (FY2026) |
|---|---|---|
| Q1 | Feb – Apr | Feb 2025 – Apr 2025 |
| Q2 | May – Jul | May 2025 – Jul 2025 |
| Q3 | Aug – Oct | Aug 2025 – Oct 2025 |
| Q4 | Nov – Jan | Nov 2025 – Jan 2026 |

---

## Tool Functions

All BigQuery interactions go through parameterized tool functions in `tools/icm_tools.py`. These are the building blocks the Investigation Agent uses to gather evidence.

| Function | Returns |
|---|---|
| `is_employee_valid(employee_number)` | `bool` — exists in system |
| `get_employee_profile(employee_number)` | Full profile from `vw_Employee_Roster` |
| `get_employee_location_on_date(employee_number, date)` | Location assignment on a specific date |
| `get_employee_sales_on_date(employee_number, date)` | All sales transactions on a date |
| `get_employee_sales_in_period(employee_number, start, end)` | Sales across a date range |
| `get_employee_sales_summary(employee_number, fiscal_year, quarter)` | Aggregated sales for a fiscal quarter |
| `get_employee_plans_on_date(employee_number, date)` | Active comp plan enrollments on a date |
| `get_sales_qualifying_for_employee_plan(employee_number, date)` | Eligibility check for employee-level plans |
| `get_sales_qualifying_for_location_plan(employee_number, date)` | Eligibility check for location-level plans |
| `get_commission_estimate(employee_number, fiscal_year, quarter)` | Expected commission from `vw_Commission_Estimate` |
| `get_manager_team_summary(manager_number, fiscal_year, quarter)` | Team performance summary for managers |

---

## Tech Stack

### Backend
| Component | Technology |
|---|---|
| Language | Python 3.12 |
| Web framework | Flask |
| AI model | Claude (Anthropic API) — `claude-sonnet-4-6` |
| Agent orchestration | LangGraph `StateGraph` |
| Structured outputs | `client.messages.parse()` with Pydantic models |
| Data warehouse | Google BigQuery |
| BigQuery client | `google-cloud-bigquery` |
| Streaming | Server-Sent Events (SSE) |
| Slack | Slash command with HMAC-SHA256 signature verification |

### Frontend
| Component | Technology |
|---|---|
| Framework | React 18 |
| Build tool | Vite 5 |
| Styling | Tailwind CSS 3 |
| State management | React `useState` / `useEffect` (no external library) |
| Data fetching | Native `fetch` API with SSE `ReadableStream` |

---

## API Reference

### Backend Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Built-in HTML test page |
| `GET` | `/employee/:id` | Employee profile lookup (name, job, location, supervisor) |
| `POST` | `/investigate` | SSE stream — runs full 3-stage pipeline |
| `GET` | `/dispute-predictor` | System-wide payment gap analysis |
| `POST` | `/slack` | Slack slash command handler |

### SSE Event Stages (`POST /investigate`)

```
data: {"stage": "intake",        "result": {...IntakeResult}}
data: {"stage": "planner",       "result": {...InvestigationPlan}}
data: {"stage": "investigation", "result": {...InvestigationReport}}
data: {"stage": "done"}
```

### Dispute Predictor Response (`GET /dispute-predictor`)

```json
{
  "summary": {
    "affected_employees": 8,
    "total_discrepancy": 14823.50,
    "total_owed": 18200.00,
    "total_paid": 3376.50,
    "by_job_code": [
      { "job_code": "DM",   "employees": 1, "plan_gaps": 4,  "discrepancy": 3200.00 },
      { "job_code": "MGR",  "employees": 1, "plan_gaps": 4,  "discrepancy": 2800.00 },
      { "job_code": "REP",  "employees": 4, "plan_gaps": 12, "discrepancy": 6400.00 },
      { "job_code": "SREP", "employees": 2, "plan_gaps": 6,  "discrepancy": 2423.50 }
    ]
  },
  "disputes": [
    {
      "employee_number": 145,
      "employee_name": "Jane Smith",
      "job_code": "REP",
      "comp_plan_name": "Standard Rep Commission",
      "fiscal_year": 2026,
      "quarter_number": 1,
      "eligible_sales": 42000.00,
      "estimated_commission": 2100.00,
      "total_paid": 0.00,
      "discrepancy": 2100.00
    }
  ]
}
```

---

## Project Structure

```
icm-system/
├── agents/
│   ├── intake/              # Stage 1 — text → IntakeResult
│   │   ├── agent.py         # parse_query() using claude.messages.parse()
│   │   └── __init__.py
│   ├── planner/             # Stage 2 — IntakeResult → InvestigationPlan
│   │   ├── agent.py         # LangGraph StateGraph, routes by query_type
│   │   └── __init__.py
│   └── investigation/       # Stage 3 — plan → InvestigationReport
│       ├── agent.py         # LangGraph StateGraph, executes tools, synthesizes
│       └── __init__.py
├── tools/
│   └── icm_tools.py         # 11 BigQuery-backed tool functions
├── db/
│   ├── tables.py            # DDL — creates all 8 BigQuery tables
│   ├── inserts.py           # Loads Fiscal_Calendar_Details (16 rows)
│   ├── seed.py              # Populates all tables with realistic sample data
│   ├── pay_seed.py          # Populates Worker_Pay_Details (with intentional gaps)
│   └── views.py             # Creates 7 analytical BigQuery views
├── ui/                      # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx           # Root component, tab navigation, SSE stream handler
│   │   └── components/
│   │       ├── Header.jsx
│   │       ├── InputForm.jsx          # Employee lookup + query form
│   │       ├── Pipeline.jsx           # 3-stage pipeline layout
│   │       ├── IntakeCard.jsx
│   │       ├── PlannerCard.jsx
│   │       ├── InvestigationCard.jsx
│   │       ├── DisputePredictorPage.jsx  # Proactive payment gap dashboard
│   │       ├── AgentCard.jsx
│   │       ├── StatusBadge.jsx
│   │       ├── Connector.jsx
│   │       └── Skeleton.jsx
│   └── vite.config.js
├── dispute_predictor.py     # BigQuery gap analysis logic
├── server.py                # Flask backend — all routes + Slack handler
├── pyproject.toml
└── .env                     # ANTHROPIC_API_KEY, SLACK_SIGNING_SECRET, SLACK_BOT_TOKEN
```

---

## Setup

### Prerequisites
- Python 3.12+
- Node.js 18+
- Google Cloud project with BigQuery enabled
- Anthropic API key

### Installation

```bash
# 1. Clone and install Python dependencies (editable mode required)
pip install -e .

# 2. Configure environment
cp .env.example .env
# Edit .env and set:
#   ANTHROPIC_API_KEY=sk-ant-...
#   GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
#   SLACK_SIGNING_SECRET=...   (optional)
#   SLACK_BOT_TOKEN=...        (optional)

# 3. Authenticate with Google Cloud
gcloud auth application-default login

# 4. First-time BigQuery setup (run once in order)
python -c "from db.tables import deploy_full_icm_schema; deploy_full_icm_schema('YOUR_PROJECT', 'icm_analytics')"
python -c "from db.inserts import load_fiscal_calendar; load_fiscal_calendar('YOUR_PROJECT', 'icm_analytics')"
python db/seed.py
python db/pay_seed.py
python db/views.py

# 5. Install frontend dependencies
cd ui && npm install
```

### Running

```bash
# Backend (terminal 1)
python server.py          # http://localhost:5000

# Frontend (terminal 2)
cd ui && npm run dev      # http://localhost:5173
```

### Slack Setup (optional)

```bash
# 1. Start the Flask server
python server.py

# 2. Expose it publicly
ngrok http 5000

# 3. In your Slack app settings:
#    Request URL → https://<ngrok-url>/slack
#    Required scopes: chat:write
```

Slash command format: `/icm <employee_number> <query>`

---

## Future Enhancements

### AI & Investigation
- **Multi-turn conversation** — allow employees to follow up on an investigation with clarifying questions, with the agent maintaining context across turns
- **Confidence-driven escalation** — automatically route low-confidence findings to a human reviewer queue with a pre-populated case file
- **Anomaly detection** — use historical payment patterns to flag statistically unusual commission amounts (both over- and under-payments)
- **Cross-employee pattern recognition** — identify systemic issues affecting entire teams or locations (e.g., a plan configuration bug impacting all reps at a district)
- **Natural language plan explanation** — allow employees to ask "how does my comp plan work?" and receive a personalized, plain-English breakdown of their specific plan rules

### Dispute Predictor
- **Scheduled automatic runs** — trigger the gap scan on a configurable schedule (e.g., 3 days after each pay cycle closes) and surface new gaps immediately
- **Email / Slack alerts** — notify affected employees and their managers automatically when a payment gap is detected, before the complaint is filed
- **Dispute status tracking** — add a workflow layer where flagged disputes can be marked as "investigating," "resolved," or "intentional" with audit trail
- **Partial payment detection** — distinguish between completely missing payments and underpayments, with a separate severity classification for each
- **Historical trend view** — visualize dispute rates over time by team, region, or plan type to identify chronic problem areas

### Platform & Integration
- **Authentication & RBAC** — role-based access so reps see only their own data, managers see their team, and finance sees everything
- **HRIS integration** — sync employee profiles, org hierarchy, and plan assignments automatically from Workday, SAP, or similar systems
- **Payroll system integration** — pull actual payment records directly from ADP, Ceridian, or the core payroll platform instead of a manual seed table
- **CRM integration** — link sales transactions directly to Salesforce or similar CRM for real-time eligibility validation
- **Audit logging** — full immutable log of every investigation, tool call result, and dispute prediction for compliance and SOX audit readiness
- **Mobile app** — React Native version of the investigation form so field reps can submit queries from their phones
- **Multi-language support** — internationalize the UI and extend the Intake Agent to handle queries in Spanish, French, Portuguese, and other languages common in sales organizations

### Analytics & Reporting
- **Executive dashboard** — org-wide compensation health metrics: total commission liability, payment accuracy rate, average dispute resolution time
- **Plan performance analytics** — which comp plans are generating the most disputes, and why
- **Forecasting** — project expected commission liability for the current quarter based on sales-to-date
- **Exportable reports** — download dispute predictor results as CSV or PDF for finance review meetings
- **API webhooks** — publish dispute events to downstream systems (ticketing, BI tools, data lakes) in real time
