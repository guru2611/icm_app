"""
seed.py — Populate all icm_analytics tables with realistic ICM data.

Org hierarchy:
  5 District Managers (DM)  → no supervisor
  15 Store Managers  (MGR)  → report to DMs
  20 Senior Reps     (SREP) → report to Managers
  60 Sales Reps      (REP)  → report to Managers

Comp plan structure:
  Plan 1 — Standard Rep Commission   : 6% monthly  (REP)
  Plan 2 — Senior Rep Commission     : 9% monthly  (SREP)
  Plan 3 — Manager Override          : 3% quarterly (MGR)  — % of team sales
  Plan 4 — District Manager Plan     : 2% quarterly (DM)   — % of district sales
  Plan 5 — Apple Vendor Bonus        : 10% monthly (REP/SREP)
  Plan 6 — Samsung Vendor Bonus      : 8%  monthly (REP/SREP)
  Plan 7 — Google Vendor Bonus       : 7%  monthly (REP/SREP)

Each plan has per-fiscal-year versions (FY2024, FY2025, FY2026).
Fiscal year runs Feb 1 → Jan 31.
"""

import random
from datetime import date, timedelta
from google.cloud import bigquery

PROJECT = "glossy-buffer-411806"
DATASET = "icm_analytics"

random.seed(42)
client = bigquery.Client(project=PROJECT)


def load(table_name, rows, truncate=True):
    table_ref = f"{PROJECT}.{DATASET}.{table_name}"
    disposition = (
        bigquery.WriteDisposition.WRITE_TRUNCATE
        if truncate
        else bigquery.WriteDisposition.WRITE_APPEND
    )
    job_config = bigquery.LoadJobConfig(
        write_disposition=disposition,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()
    print(f"[+] {table_name:30s} {len(rows):>5} rows")


# ── 1. Location_Details ────────────────────────────────────────────────────────
# 20 locations across 3 territories → 6 markets → 12 districts → 20 stores

GEO = {
    "East": {
        "Northeast": ["New England", "Mid-Atlantic"],
        "Southeast": ["Florida",     "Carolinas"],
    },
    "West": {
        "Northwest": ["Pacific NW",  "Mountain"],
        "Southwest": ["California",  "Arizona"],
    },
    "Central": {
        "Midwest":        ["Great Lakes", "Plains"],
        "South Central":  ["Texas",       "Gulf Coast"],
    },
}

locations = []
loc_id = 1
for territory, markets in GEO.items():
    for market, districts in markets.items():
        for district in districts:
            for suffix in ["Main", "North"]:          # 2 stores per district → 24 total; trim to 20
                if loc_id > 20:
                    break
                locations.append({
                    "Location_ID":   loc_id,
                    "Territory":     territory,
                    "Market":        market,
                    "District":      district,
                    "Location_Name": f"{district} {suffix}",
                    "Store_Name":    f"{district} {suffix} Store",
                })
                loc_id += 1

location_ids = [l["Location_ID"] for l in locations]


# ── 2. Plan_Details ────────────────────────────────────────────────────────────
# Multiple fiscal-year versions per comp plan.
# FY2024: Feb 2023 – Jan 2024 | FY2025: Feb 2024 – Jan 2025 | FY2026: Feb 2025 – Jan 2026

FISCAL_YEARS = [
    (2024, "2023-02-01", "2024-01-31"),
    (2025, "2024-02-01", "2025-01-31"),
    (2026, "2025-02-01", "2026-01-31"),
]

# (comp_plan_id, name, level, time_period, pct_by_fy)
PLAN_TEMPLATES = [
    (1, "Standard Rep Commission",  "Employee", "Monthly",   {2024: 5, 2025: 6, 2026: 6}),
    (2, "Senior Rep Commission",    "Employee", "Monthly",   {2024: 8, 2025: 9, 2026: 9}),
    (3, "Manager Override",         "Location", "Quarterly", {2024: 3, 2025: 3, 2026: 4}),
    (4, "District Manager Plan",    "Location", "Quarterly", {2024: 2, 2025: 2, 2026: 2}),
    (5, "Apple Vendor Bonus",       "Employee", "Monthly",   {2024: 10, 2025: 10, 2026: 12}),
    (6, "Samsung Vendor Bonus",     "Employee", "Monthly",   {2024: 8,  2025: 8,  2026: 9}),
    (7, "Google Vendor Bonus",      "Employee", "Monthly",   {2024: 7,  2025: 7,  2026: 8}),
]

plan_details = []
version_id = 1
for comp_plan_id, name, level, period, pcts in PLAN_TEMPLATES:
    for fy, start, end in FISCAL_YEARS:
        plan_details.append({
            "Comp_Plan_Version_ID": version_id,
            "Comp_Plan_ID":         comp_plan_id,
            "Comp_Plan_Name":       name,
            "Start_Date":           start,
            "End_Date":             end,
            "Plan_applicable_Level": level,
            "Time_Period":          period,
            "Percentage":           pcts[fy],
        })
        version_id += 1


# ── 3. Worker_Profile ──────────────────────────────────────────────────────────
FIRST_NAMES = [
    "James","Mary","John","Patricia","Robert","Jennifer","Michael","Linda",
    "William","Barbara","David","Susan","Richard","Jessica","Joseph","Sarah",
    "Thomas","Karen","Charles","Lisa","Christopher","Nancy","Daniel","Betty",
    "Matthew","Margaret","Anthony","Sandra","Mark","Ashley","Donald","Dorothy",
    "Steven","Kimberly","Paul","Emily","Andrew","Donna","Joshua","Michelle",
    "Kenneth","Carol","Kevin","Amanda","Brian","Melissa","George","Deborah",
    "Timothy","Stephanie","Ronald","Rebecca","Edward","Sharon","Jason","Laura",
    "Jeffrey","Cynthia","Ryan","Kathleen","Jacob","Amy","Gary","Angela",
    "Nicholas","Shirley","Eric","Anna","Jonathan","Brenda","Stephen","Pamela",
    "Larry","Emma","Justin","Nicole","Scott","Helen","Brandon","Samantha",
    "Benjamin","Katherine","Samuel","Christine","Raymond","Debra","Gregory","Rachel",
    "Frank","Carolyn","Alexander","Janet","Patrick","Catherine","Jack","Maria",
]
LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson",
    "Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson",
    "White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker",
    "Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores",
    "Green","Adams","Nelson","Baker","Hall","Rivera","Campbell","Mitchell",
    "Carter","Roberts",
]

# emp_num, job_code
WORKFORCE = (
    [(100 + i, "DM")   for i in range(1, 6)]   +   # 101-105
    [(100 + i, "MGR")  for i in range(6, 21)]  +   # 106-120
    [(100 + i, "SREP") for i in range(21, 41)] +   # 121-140
    [(100 + i, "REP")  for i in range(41, 101)]    # 141-200
)

workers = []
for idx, (emp_num, job_code) in enumerate(WORKFORCE):
    if job_code == "DM":
        supervisor = None
    elif job_code == "MGR":
        supervisor = 101 + (idx % 5)           # distribute across 5 DMs
    else:
        supervisor = 106 + (idx % 15)          # distribute across 15 Managers

    workers.append({
        "Employee_Number":       emp_num,
        "First_Name":            FIRST_NAMES[idx % len(FIRST_NAMES)],
        "Last_Name":             LAST_NAMES[idx % len(LAST_NAMES)],
        "Supervisor_Emp_Number": supervisor,
    })


# ── 4. Worker_History ──────────────────────────────────────────────────────────
# Most employees have one current record; ~20% have a prior record (transfer/promotion).

worker_history = []
for idx, (emp_num, job_code) in enumerate(WORKFORCE):
    primary_loc = location_ids[idx % len(location_ids)]

    # ~20% of employees had a prior role/location before Feb 2024
    if idx % 5 == 0 and job_code in ("SREP", "MGR"):
        prev_loc = location_ids[(idx + 3) % len(location_ids)]
        prev_code = "REP" if job_code == "SREP" else "SREP"
        worker_history.append({
            "Employee_Number": emp_num,
            "Location_ID":     prev_loc,
            "Job_Code":        prev_code,
            "Start_date":      "2023-02-01",
            "End_date":        "2024-01-31",
        })
        current_start = "2024-02-01"
    else:
        current_start = "2023-02-01"

    worker_history.append({
        "Employee_Number": emp_num,
        "Location_ID":     primary_loc,
        "Job_Code":        job_code,
        "Start_date":      current_start,
        "End_date":        None,            # NULL = currently active
    })


# ── 5. Plan_assignment ─────────────────────────────────────────────────────────
# Base plan per job level for all fiscal years.
# ~30% of REPs/SREPs also get a vendor bonus plan.

JOB_TO_BASE_PLAN = {"DM": 4, "MGR": 3, "SREP": 2, "REP": 1}
VENDOR_PLANS = [5, 6, 7]   # Apple, Samsung, Google

plan_assignments = []
vendor_eligible = [emp for emp, job in WORKFORCE if job in ("REP", "SREP")]
vendor_assigned  = set(random.sample(vendor_eligible, k=int(len(vendor_eligible) * 0.3)))

for emp_num, job_code in WORKFORCE:
    base_plan = JOB_TO_BASE_PLAN[job_code]
    for _, start, end in FISCAL_YEARS:
        plan_assignments.append({
            "Comp_Plan_ID":    base_plan,
            "Employee_Number": emp_num,
            "Start_Date":      start,
            "End_Date":        end,
        })

    # Add a single active vendor bonus plan for eligible reps
    if emp_num in vendor_assigned:
        vendor_plan = random.choice(VENDOR_PLANS)
        plan_assignments.append({
            "Comp_Plan_ID":    vendor_plan,
            "Employee_Number": emp_num,
            "Start_Date":      "2024-02-01",
            "End_Date":        "2026-01-31",
        })


# ── 6. Vendor_Program_Details ──────────────────────────────────────────────────
# Each location carries a subset of vendor programs, each tied to a comp plan.

VENDORS = [
    (1, "Apple",   5,  [1001, 1002, 1003]),   # comp_plan_id, SKU list
    (2, "Samsung", 6,  [2001, 2002, 2003]),
    (3, "Google",  7,  [3001, 3002]),
    (4, "LG",      1,  [4001, 4002]),
    (5, "Sony",    1,  [5001, 5002]),
]

vendor_programs = []
vp_num = 1
for loc_id in location_ids:
    for vendor_id, vendor_name, comp_plan_id, skus in VENDORS:
        for sku_id in skus:
            vendor_programs.append({
                "Location_ID":          loc_id,
                "Vendor_Program_Number": vp_num,
                "SKU_ID":               sku_id,
                "Comp_Plan_ID":         comp_plan_id,
                "Vendor_ID":            vendor_id,
                "Vendor_Name":          vendor_name,
            })
            vp_num += 1


# ── 7. Sale_Details ────────────────────────────────────────────────────────────
# 1000 transactions spread across reps, weighted toward recent fiscal years.
# Employee's primary location is used as the sale location.

emp_to_loc = {
    emp: location_ids[idx % len(location_ids)]
    for idx, (emp, _) in enumerate(WORKFORCE)
}
sales_reps = [emp for emp, job in WORKFORCE if job in ("REP", "SREP")]

SALE_DATE_RANGES = [
    (date(2023, 2,  1), date(2024, 1, 31), 200),   # FY2024 — 200 txns
    (date(2024, 2,  1), date(2025, 1, 31), 350),   # FY2025 — 350 txns
    (date(2025, 2,  1), date(2026, 1, 31), 450),   # FY2026 — 450 txns
]

sales = []
txn_id = 1
for start, end, count in SALE_DATE_RANGES:
    span = (end - start).days
    for _ in range(count):
        emp_num = random.choice(sales_reps)
        txn_date = start + timedelta(days=random.randint(0, span))
        amount   = random.randint(200, 5000)
        sales.append({
            "Transaction_ID":        txn_id,
            "Sale_Transaction_Date": txn_date.isoformat(),
            "Location_ID":           emp_to_loc[emp_num],
            "Employee_Number":       emp_num,
            "Total_Sale_Amount":     amount,
        })
        txn_id += 1


# ── Load ───────────────────────────────────────────────────────────────────────
print(f"\nLoading data into {PROJECT}.{DATASET}\n{'─'*50}")
load("Location_Details",      locations)
load("Plan_Details",          plan_details)
load("Worker_Profile",        workers)
load("Worker_History",        worker_history)
load("Plan_assignment",       plan_assignments)
load("Vendor_Program_Details",vendor_programs)
load("Sale_Details",          sales)
print(f"{'─'*50}\nDone.")
