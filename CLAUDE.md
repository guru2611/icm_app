# ICM System

Incentive Compensation Management system backed by BigQuery, with Python tooling and an AI-powered intake agent.

## Project Structure

```
icm-system/
├── tables.py          # Creates all BigQuery tables in icm_analytics dataset
├── inserts.py         # Loads Fiscal_Calendar_Details (16 rows) via load_table_from_json
├── seed.py            # Populates all tables with realistic sample data
├── views.py           # Creates analytical views in BigQuery
├── icm_tools.py       # Agent-callable tool functions (BigQuery-backed)
├── intake_agent.py    # Claude-powered intake parser (unstructured → structured)
├── server.py          # Flask backend: serves React UI, investigation pipeline, and Slack slash command
├── agents/            # Intake, Planner, Investigation agent modules
├── tools/             # icm_tools.py (BigQuery tool functions)
├── ui/                # React + Vite frontend (runs on port 5173)
└── .env               # API keys (do not commit)
```

## BigQuery

- **Project:** `glossy-buffer-411806`
- **Dataset:** `icm_analytics`
- **Note:** Billing is not enabled on this project. Use `load_table_from_json` (free) instead of SQL INSERT/UPDATE/DELETE (blocked on free tier). DDL (CREATE VIEW, CREATE TABLE) works fine.

## Tables

| Table | PK | Description |
|---|---|---|
| `Worker_Profile` | Employee_Number | 100 employees across 4 job levels |
| `Worker_History` | — | Job + location assignments per employee (null End_date = active) |
| `Location_Details` | Location_ID | 20 stores across 3 territories → 6 markets → 12 districts |
| `Plan_Details` | Comp_Plan_Version_ID | 7 comp plans × 3 fiscal year versions = 21 rows |
| `Plan_assignment` | — | Maps employees to comp plans per fiscal year |
| `Vendor_Program_Details` | — | Vendor programs per location with associated comp plans |
| `Sale_Details` | Transaction_ID | 1000 sales transactions across FY2024–FY2026 |
| `Fiscal_Calendar_Details` | Fiscal_Calendar_ID | 16 rows — 4 quarters × 4 fiscal years (FY2024–FY2027) |

### Fiscal Year
Runs **Feb 1 → Jan 31**. FY2026 = Feb 2025 – Jan 2026.

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

`Plan_applicable_Level` is either `Employee` (commission on own sales) or `Location` (commission on location's total sales — used for manager overrides).

## Views

| View | Description |
|---|---|
| `vw_Employee_Roster` | Denormalised profile: name, job, location hierarchy, supervisor name |
| `vw_Active_Plan_Assignments` | Plans active as of today with rates, filtered to `CURRENT_DATE()` |
| `vw_Sales_With_Fiscal_Period` | Transactions tagged with fiscal year, quarter, employee name, location hierarchy |
| `vw_Employee_Sales_by_Period` | Sales aggregated per employee per fiscal year + quarter |
| `vw_Location_Sales_by_Period` | Sales aggregated per location per fiscal year + quarter |
| `vw_Commission_Estimate` | Estimated commission per employee per quarter — routes to Employee or Location sales based on plan level |
| `vw_Manager_Team_Summary` | Direct reports' sales + team total per manager per fiscal quarter |

## Tool Functions (`tools/icm_tools.py`)

All functions return plain dicts/lists and take typed parameters. Parameterised queries throughout — no string interpolation.

### Employee
| Function | Returns |
|---|---|
| `is_employee_valid(employee_number)` | `bool` |
| `get_employee_profile(employee_number)` | `dict \| None` |
| `get_employee_location_on_date(employee_number, date)` | `dict \| None` — resolves from Worker_History |

### Sales
| Function | Returns |
|---|---|
| `get_employee_sales_on_date(employee_number, date)` | `list[dict]` |
| `get_employee_sales_in_period(employee_number, start_date, end_date)` | `list[dict]` |
| `get_employee_sales_summary(employee_number, fiscal_year, quarter_number)` | `dict \| None` |

### Plan & Eligibility
| Function | Returns |
|---|---|
| `get_employee_plans_on_date(employee_number, date)` | `list[dict]` |
| `get_sales_qualifying_for_employee_plan(employee_number, date)` | `dict` — `{qualified, sales, qualifying_plans, reason}` |
| `get_sales_qualifying_for_location_plan(employee_number, date)` | `dict` — `{qualified, sales, location, qualifying_plans, location_day_sales, reason}` |

### Commission
| Function | Returns |
|---|---|
| `get_commission_estimate(employee_number, fiscal_year, quarter_number)` | `list[dict]` |
| `get_manager_team_summary(manager_employee_number, fiscal_year, quarter_number)` | `list[dict]` |

## Agents (`agents/`)

Three-stage investigation pipeline:

| Agent | Module | Description |
|---|---|---|
| Intake | `agents/intake` | Parses free-text query → `IntakeResult` (structured) |
| Planner | `agents/planner` | Routes by query type → ordered list of tool calls (`InvestigationPlan`) |
| Investigation | `agents/investigation` | Executes tool calls against BigQuery → forensic report |

### IntakeResult schema
```python
{
  "employee_number": int,
  "sale_date":       "YYYY-MM-DD" | null,
  "query_type":      "commission_not_received"
                   | "incorrect_commission_received"
                   | "how_much_commission"
                   | "other",
  "summary":         str
}
```

## Server (`server.py`)

Flask backend on **port 5000**. Serves the React app's API and the Slack slash command.

```bash
cd icm-system && python3 server.py
```

### Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Built-in HTML test page |
| `POST` | `/investigate` | SSE stream — runs full 3-stage pipeline, yields `{stage, result}` events |
| `POST` | `/slack` | Slack slash command handler (see below) |

### SSE events (`/investigate`)
```
data: {"stage": "intake",        "result": IntakeResult}
data: {"stage": "planner",       "result": InvestigationPlan}
data: {"stage": "investigation", "result": ForensicReport}
data: {"stage": "done"}
```

## React UI (`ui/`)

Vite + React frontend on **port 5173**. Proxies `/investigate` and `/slack` to Flask on port 5000.

```bash
cd ui && npm run dev
```

## Slack Integration

Slash command `/icm` posts an employee number + query to the investigation pipeline and returns a Block Kit formatted forensic report to the channel.

### Command format
```
/icm <employee_number> <query text>
/icm 145 I never got my November commission
```

### How it works
1. Slack sends `POST /slack` to the server
2. Server acknowledges immediately (within Slack's 3s window)
3. Pipeline runs in a background thread
4. Result is posted back via Slack's `response_url`

### Setup (local dev)
```bash
# 1. Start the Flask server
python3 server.py

# 2. Expose it publicly
ngrok http 5000

# 3. Set slash command Request URL in Slack app settings:
#    https://<ngrok-url>/slack
```

### Required Slack app scopes
- `chat:write`

## Environment

```bash
# .env
ANTHROPIC_API_KEY=...
SLACK_SIGNING_SECRET=...   # from Slack app Basic Information page
SLACK_BOT_TOKEN=xoxb-...   # from Slack app OAuth & Permissions page
```

Install dependencies:

```bash
pip install anthropic google-cloud-bigquery flask python-dotenv pydantic requests
```
