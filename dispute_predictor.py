"""
dispute_predictor.py — Identify employees who were owed commission but not paid.

Logic:
  1. vw_Commission_Estimate gives expected commission per (employee, plan, fiscal quarter).
  2. Worker_Pay_Details records what was actually paid, keyed to biweekly pay periods.
  3. We aggregate payments into fiscal quarters and left-join against estimates.
  4. Rows where Estimated_Commission > 0 and Total_Paid < Estimated_Commission are disputes.
"""

from google.cloud import bigquery

PROJECT = "glossy-buffer-411806"
DATASET = "icm_analytics"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = bigquery.Client(project=PROJECT)
    return _client


def _q(sql: str) -> list[dict]:
    rows = _get_client().query(sql).result()
    return [dict(row) for row in rows]


def get_dispute_predictions() -> dict:
    """
    Return a dict with:
      - disputes: list of individual dispute records
      - summary:  aggregated stats (total employees, total discrepancy, by job level)
    """
    sql = f"""
    WITH payments_by_quarter AS (
      SELECT
        wpd.Employee_Number,
        wpd.Comp_Plan_ID,
        fc.Fiscal_Year,
        fc.Quarter_Number,
        SUM(wpd.Amount_Paid) AS Total_Paid
      FROM `{PROJECT}.{DATASET}.Worker_Pay_Details` wpd
      JOIN `{PROJECT}.{DATASET}.Fiscal_Calendar_Details` fc
        ON wpd.Pay_Period_Start_Date
           BETWEEN fc.Quarter_Start_Date AND fc.Quarter_End_Date
      GROUP BY 1, 2, 3, 4
    ),
    disputes AS (
      SELECT
        ce.Employee_Number,
        ce.Employee_Name,
        COALESCE(ce.Job_Code, 'UNKNOWN')          AS Job_Code,
        ce.Comp_Plan_ID,
        ce.Comp_Plan_Name,
        ce.Plan_applicable_Level,
        ce.Fiscal_Year,
        ce.Quarter_Number,
        ce.Eligible_Sales,
        ROUND(ce.Estimated_Commission, 2)          AS Estimated_Commission,
        ROUND(COALESCE(pbq.Total_Paid, 0), 2)      AS Total_Paid,
        ROUND(ce.Estimated_Commission
              - COALESCE(pbq.Total_Paid, 0), 2)    AS Discrepancy
      FROM `{PROJECT}.{DATASET}.vw_Commission_Estimate` ce
      LEFT JOIN payments_by_quarter pbq
        ON  ce.Employee_Number = pbq.Employee_Number
        AND ce.Comp_Plan_ID    = pbq.Comp_Plan_ID
        AND ce.Fiscal_Year     = pbq.Fiscal_Year
        AND ce.Quarter_Number  = pbq.Quarter_Number
      WHERE ce.Estimated_Commission > 0
        AND ROUND(COALESCE(pbq.Total_Paid, 0), 2)
            < ROUND(ce.Estimated_Commission, 2)
    )
    SELECT *
    FROM disputes
    ORDER BY Fiscal_Year DESC, Quarter_Number DESC, Discrepancy DESC
    """

    rows = _q(sql)

    # Convert any date/Decimal objects to plain Python types for JSON
    disputes = []
    for r in rows:
        disputes.append({
            "employee_number":       int(r["Employee_Number"]),
            "employee_name":         r["Employee_Name"],
            "job_code":              r["Job_Code"],
            "comp_plan_id":          int(r["Comp_Plan_ID"]),
            "comp_plan_name":        r["Comp_Plan_Name"],
            "plan_level":            r["Plan_applicable_Level"],
            "fiscal_year":           int(r["Fiscal_Year"]),
            "quarter_number":        int(r["Quarter_Number"]),
            "eligible_sales":        float(r["Eligible_Sales"]),
            "estimated_commission":  float(r["Estimated_Commission"]),
            "total_paid":            float(r["Total_Paid"]),
            "discrepancy":           float(r["Discrepancy"]),
        })

    # Build summary stats
    affected_employees = len({d["employee_number"] for d in disputes})
    total_discrepancy  = round(sum(d["discrepancy"] for d in disputes), 2)
    total_owed         = round(sum(d["estimated_commission"] for d in disputes), 2)
    total_paid         = round(sum(d["total_paid"] for d in disputes), 2)

    by_job_code: dict[str, dict] = {}
    for d in disputes:
        jc = d["job_code"]
        if jc not in by_job_code:
            by_job_code[jc] = {"employees": set(), "discrepancy": 0.0, "count": 0}
        by_job_code[jc]["employees"].add(d["employee_number"])
        by_job_code[jc]["discrepancy"] = round(by_job_code[jc]["discrepancy"] + d["discrepancy"], 2)
        by_job_code[jc]["count"] += 1

    by_job_code_out = [
        {
            "job_code":    jc,
            "employees":   len(v["employees"]),
            "plan_gaps":   v["count"],
            "discrepancy": v["discrepancy"],
        }
        for jc, v in sorted(by_job_code.items())
    ]

    return {
        "disputes": disputes,
        "summary": {
            "affected_employees": affected_employees,
            "total_discrepancy":  total_discrepancy,
            "total_owed":         total_owed,
            "total_paid":         total_paid,
            "by_job_code":        by_job_code_out,
        },
    }
