"""
pay_seed.py — Populate Worker_Pay_Details with biweekly commission payments.

Rules:
- Pay periods are biweekly, anchored from 2023-02-01.
- Employee-level plans (REP/SREP): commission earned per sale, paid in the
  first biweekly period whose start date falls after the sale date.
- Location-level plans (MGR/DM): quarterly commission, paid in the first
  biweekly period whose start date falls after the quarter end date.
- Payment_Date = Pay_Period_End_Date + 6 days.
- SKIP_EMPLOYEES are intentionally omitted to simulate payment discrepancies.
"""

from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict
from google.cloud import bigquery

PROJECT = "glossy-buffer-411806"
DATASET = "icm_analytics"

client = bigquery.Client(project=PROJECT)

# Intentionally unpaid — spread across all job levels for realistic discrepancies
#   REP:  145, 158, 172, 183
#   SREP: 127, 131
#   MGR:  108
#   DM:   103
SKIP_EMPLOYEES = {145, 158, 172, 183, 127, 131, 108, 103}


# ── Biweekly periods anchored Feb 1 2023 ───────────────────────────────────

def build_periods(through=date(2026, 3, 18)):
    periods, start = [], date(2023, 2, 1)
    while start <= through:
        p_end = start + timedelta(days=13)
        periods.append((start, p_end))
        start = p_end + timedelta(days=1)
    return periods

PERIODS = build_periods()


def next_period_after(ref_date):
    """First biweekly period whose start date is strictly after ref_date."""
    for p_start, p_end in PERIODS:
        if p_start > ref_date:
            return p_start, p_end
    return None, None


# ── 1. Employee-level plans: per-sale commission ───────────────────────────

print("Fetching employee-level sales with active plans...")
emp_rows = list(client.query(f"""
SELECT
    sd.Employee_Number,
    sd.Sale_Transaction_Date,
    sd.Total_Sale_Amount,
    pa.Comp_Plan_ID,
    pd.Percentage
FROM `{PROJECT}.{DATASET}.Sale_Details` sd
JOIN `{PROJECT}.{DATASET}.Plan_assignment` pa
    ON  sd.Employee_Number = pa.Employee_Number
    AND sd.Sale_Transaction_Date BETWEEN pa.Start_Date AND pa.End_Date
JOIN `{PROJECT}.{DATASET}.Plan_Details` pd
    ON  pa.Comp_Plan_ID = pd.Comp_Plan_ID
    AND sd.Sale_Transaction_Date BETWEEN pd.Start_Date AND pd.End_Date
    AND pd.Plan_applicable_Level = 'Employee'
ORDER BY sd.Employee_Number, sd.Sale_Transaction_Date
""").result())

# Aggregate commission by (employee, plan, pay_period)
buckets: dict[tuple, Decimal] = defaultdict(Decimal)

for row in emp_rows:
    if row.Employee_Number in SKIP_EMPLOYEES:
        continue
    p_start, p_end = next_period_after(row.Sale_Transaction_Date)
    if p_start is None:
        continue
    key = (row.Employee_Number, row.Comp_Plan_ID, p_start, p_end)
    commission = Decimal(str(row.Total_Sale_Amount)) * Decimal(str(row.Percentage)) / Decimal("100")
    buckets[key] += commission

print(f"  {len(emp_rows)} sale rows → {len(buckets)} employee-level pay buckets")


# ── 2. Location-level plans: quarterly lump sum for MGR/DM ─────────────────

print("Fetching location-level quarterly commissions (MGR/DM)...")
loc_rows = list(client.query(f"""
SELECT
    wh.Employee_Number,
    fc.Quarter_End_Date,
    pa.Comp_Plan_ID,
    pd.Percentage,
    SUM(sd.Total_Sale_Amount) AS Location_Sales
FROM `{PROJECT}.{DATASET}.Worker_History` wh
JOIN `{PROJECT}.{DATASET}.Plan_assignment` pa
    ON  wh.Employee_Number = pa.Employee_Number
JOIN `{PROJECT}.{DATASET}.Plan_Details` pd
    ON  pa.Comp_Plan_ID        = pd.Comp_Plan_ID
    AND pd.Plan_applicable_Level = 'Location'
    AND pa.Start_Date <= pd.End_Date
    AND pa.End_Date   >= pd.Start_Date
JOIN `{PROJECT}.{DATASET}.Sale_Details` sd
    ON  sd.Location_ID = wh.Location_ID
    AND sd.Sale_Transaction_Date BETWEEN pa.Start_Date AND pa.End_Date
    AND sd.Sale_Transaction_Date BETWEEN pd.Start_Date AND pd.End_Date
JOIN `{PROJECT}.{DATASET}.Fiscal_Calendar_Details` fc
    ON  sd.Sale_Transaction_Date
        BETWEEN fc.Quarter_Start_Date AND fc.Quarter_End_Date
WHERE wh.End_date IS NULL
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2
""").result())

loc_count_before = len(buckets)

for row in loc_rows:
    if row.Employee_Number in SKIP_EMPLOYEES:
        continue
    p_start, p_end = next_period_after(row.Quarter_End_Date)
    if p_start is None:
        continue
    key = (row.Employee_Number, row.Comp_Plan_ID, p_start, p_end)
    commission = Decimal(str(row.Location_Sales)) * Decimal(str(row.Percentage)) / Decimal("100")
    buckets[key] += commission

print(f"  {len(loc_rows)} quarter rows → {len(buckets) - loc_count_before} location-level pay buckets")


# ── 3. Build pay records ───────────────────────────────────────────────────

pay_rows = []
for (emp, plan_id, p_start, p_end), amount in buckets.items():
    pay_rows.append({
        "Employee_Number":       emp,
        "Payment_Date":          (p_end + timedelta(days=6)).isoformat(),
        "Comp_Plan_ID":          plan_id,
        "Pay_Period_Start_Date": p_start.isoformat(),
        "Pay_Period_End_Date":   p_end.isoformat(),
        "Amount_Paid":           float(round(amount, 2)),
    })


# ── 4. Load ────────────────────────────────────────────────────────────────

table_ref = f"{PROJECT}.{DATASET}.Worker_Pay_Details"
job_config = bigquery.LoadJobConfig(
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
)
job = client.load_table_from_json(pay_rows, table_ref, job_config=job_config)
job.result()

print(f"\n[+] Worker_Pay_Details    {len(pay_rows):>5} rows loaded")
print(f"    Skipped employees ({len(SKIP_EMPLOYEES)}): {sorted(SKIP_EMPLOYEES)}")
print(f"      REP:  145, 158, 172, 183")
print(f"      SREP: 127, 131")
print(f"      MGR:  108")
print(f"      DM:   103")
