"""
views.py — Create analytical views in icm_analytics dataset.
"""

from google.cloud import bigquery

PROJECT = "glossy-buffer-411806"
DATASET = "icm_analytics"

client = bigquery.Client(project=PROJECT)


def create_view(name, sql):
    full_name = f"`{PROJECT}.{DATASET}.{name}`"
    ddl = f"CREATE OR REPLACE VIEW {full_name} AS\n{sql}"
    client.query(ddl).result()
    print(f"[+] {name}")


# ── 1. vw_Employee_Roster ──────────────────────────────────────────────────────
# Denormalized employee view: profile + current job + location + supervisor name.
create_view("vw_Employee_Roster", """
SELECT
  wp.Employee_Number,
  wp.First_Name,
  wp.Last_Name,
  CONCAT(wp.First_Name, ' ', wp.Last_Name)         AS Full_Name,
  wh.Job_Code,
  wh.Location_ID,
  ld.Location_Name,
  ld.Store_Name,
  ld.District,
  ld.Market,
  ld.Territory,
  wp.Supervisor_Emp_Number,
  CONCAT(sup.First_Name, ' ', sup.Last_Name)        AS Supervisor_Name
FROM `{p}.{d}.Worker_Profile`  wp
LEFT JOIN `{p}.{d}.Worker_History`   wh  ON wp.Employee_Number      = wh.Employee_Number AND wh.End_date IS NULL
LEFT JOIN `{p}.{d}.Location_Details` ld  ON wh.Location_ID          = ld.Location_ID
LEFT JOIN `{p}.{d}.Worker_Profile`   sup ON wp.Supervisor_Emp_Number = sup.Employee_Number
""".format(p=PROJECT, d=DATASET))


# ── 2. vw_Active_Plan_Assignments ──────────────────────────────────────────────
# Comp plan assignments active as of today, with full plan details per employee.
create_view("vw_Active_Plan_Assignments", """
SELECT
  pa.Employee_Number,
  CONCAT(wp.First_Name, ' ', wp.Last_Name) AS Full_Name,
  wh.Job_Code,
  pa.Comp_Plan_ID,
  pd.Comp_Plan_Version_ID,
  pd.Comp_Plan_Name,
  pd.Plan_applicable_Level,
  pd.Time_Period,
  pd.Percentage,
  pa.Start_Date  AS Assignment_Start,
  pa.End_Date    AS Assignment_End
FROM `{p}.{d}.Plan_assignment` pa
JOIN `{p}.{d}.Plan_Details`    pd  ON pa.Comp_Plan_ID    = pd.Comp_Plan_ID
                                   AND CURRENT_DATE() BETWEEN pd.Start_Date AND pd.End_Date
JOIN `{p}.{d}.Worker_Profile`  wp  ON pa.Employee_Number = wp.Employee_Number
LEFT JOIN `{p}.{d}.Worker_History` wh ON pa.Employee_Number = wh.Employee_Number AND wh.End_date IS NULL
WHERE CURRENT_DATE() BETWEEN pa.Start_Date AND pa.End_Date
""".format(p=PROJECT, d=DATASET))


# ── 3. vw_Sales_With_Fiscal_Period ─────────────────────────────────────────────
# Each transaction enriched with employee name, location hierarchy, and fiscal period.
create_view("vw_Sales_With_Fiscal_Period", """
SELECT
  sd.Transaction_ID,
  sd.Sale_Transaction_Date,
  sd.Employee_Number,
  CONCAT(wp.First_Name, ' ', wp.Last_Name) AS Employee_Name,
  sd.Location_ID,
  ld.Location_Name,
  ld.District,
  ld.Market,
  ld.Territory,
  sd.Total_Sale_Amount,
  fc.Fiscal_Year,
  fc.Quarter_Number,
  fc.Quarter_Start_Date,
  fc.Quarter_End_Date
FROM `{p}.{d}.Sale_Details`              sd
JOIN `{p}.{d}.Worker_Profile`            wp  ON sd.Employee_Number = wp.Employee_Number
JOIN `{p}.{d}.Location_Details`          ld  ON sd.Location_ID     = ld.Location_ID
JOIN `{p}.{d}.Fiscal_Calendar_Details`   fc  ON sd.Sale_Transaction_Date
                                                 BETWEEN fc.Quarter_Start_Date AND fc.Quarter_End_Date
""".format(p=PROJECT, d=DATASET))


# ── 4. vw_Employee_Sales_by_Period ─────────────────────────────────────────────
# Sales totals per employee per fiscal year + quarter.
create_view("vw_Employee_Sales_by_Period", """
SELECT
  sd.Employee_Number,
  CONCAT(wp.First_Name, ' ', wp.Last_Name) AS Employee_Name,
  wh.Job_Code,
  wh.Location_ID,
  fc.Fiscal_Year,
  fc.Quarter_Number,
  COUNT(sd.Transaction_ID)   AS Transaction_Count,
  SUM(sd.Total_Sale_Amount)  AS Total_Sales
FROM `{p}.{d}.Sale_Details`            sd
JOIN `{p}.{d}.Worker_Profile`          wp  ON sd.Employee_Number = wp.Employee_Number
LEFT JOIN `{p}.{d}.Worker_History`     wh  ON sd.Employee_Number = wh.Employee_Number AND wh.End_date IS NULL
JOIN `{p}.{d}.Fiscal_Calendar_Details` fc  ON sd.Sale_Transaction_Date
                                               BETWEEN fc.Quarter_Start_Date AND fc.Quarter_End_Date
GROUP BY 1, 2, 3, 4, 5, 6
""".format(p=PROJECT, d=DATASET))


# ── 5. vw_Location_Sales_by_Period ─────────────────────────────────────────────
# Sales totals per location per fiscal year + quarter (feeds Location-level override plans).
create_view("vw_Location_Sales_by_Period", """
SELECT
  sd.Location_ID,
  ld.Location_Name,
  ld.District,
  ld.Market,
  ld.Territory,
  fc.Fiscal_Year,
  fc.Quarter_Number,
  COUNT(sd.Transaction_ID)  AS Transaction_Count,
  SUM(sd.Total_Sale_Amount) AS Total_Sales
FROM `{p}.{d}.Sale_Details`            sd
JOIN `{p}.{d}.Location_Details`        ld  ON sd.Location_ID = ld.Location_ID
JOIN `{p}.{d}.Fiscal_Calendar_Details` fc  ON sd.Sale_Transaction_Date
                                               BETWEEN fc.Quarter_Start_Date AND fc.Quarter_End_Date
GROUP BY 1, 2, 3, 4, 5, 6, 7
""".format(p=PROJECT, d=DATASET))


# ── 6. vw_Commission_Estimate ──────────────────────────────────────────────────
# Estimated commission per employee per plan per fiscal quarter.
# Employee-level plans: employee's own sales × plan %.
# Location-level plans: location's total sales × plan % (manager/DM overrides).
create_view("vw_Commission_Estimate", """
WITH plan_periods AS (
  -- Resolve each (employee, plan version, fiscal quarter) combination
  SELECT
    pa.Employee_Number,
    pa.Comp_Plan_ID,
    pd.Comp_Plan_Version_ID,
    pd.Comp_Plan_Name,
    pd.Plan_applicable_Level,
    pd.Time_Period,
    pd.Percentage,
    fc.Fiscal_Year,
    fc.Quarter_Number,
    fc.Quarter_Start_Date,
    fc.Quarter_End_Date
  FROM `{p}.{d}.Plan_assignment`          pa
  JOIN `{p}.{d}.Plan_Details`             pd  ON pa.Comp_Plan_ID = pd.Comp_Plan_ID
                                              AND pa.Start_Date  <= pd.End_Date
                                              AND pa.End_Date    >= pd.Start_Date
  JOIN `{p}.{d}.Fiscal_Calendar_Details`  fc  ON fc.Quarter_Start_Date >= pd.Start_Date
                                              AND fc.Quarter_End_Date   <= pd.End_Date
),
emp_sales AS (
  SELECT Employee_Number, Fiscal_Year, Quarter_Number, SUM(Total_Sale_Amount) AS Sales
  FROM `{p}.{d}.Sale_Details` sd
  JOIN `{p}.{d}.Fiscal_Calendar_Details` fc
    ON sd.Sale_Transaction_Date BETWEEN fc.Quarter_Start_Date AND fc.Quarter_End_Date
  GROUP BY 1, 2, 3
),
loc_sales AS (
  SELECT Location_ID, Fiscal_Year, Quarter_Number, SUM(Total_Sale_Amount) AS Sales
  FROM `{p}.{d}.Sale_Details` sd
  JOIN `{p}.{d}.Fiscal_Calendar_Details` fc
    ON sd.Sale_Transaction_Date BETWEEN fc.Quarter_Start_Date AND fc.Quarter_End_Date
  GROUP BY 1, 2, 3
)
SELECT
  pp.Employee_Number,
  CONCAT(wp.First_Name, ' ', wp.Last_Name)  AS Employee_Name,
  wh.Job_Code,
  wh.Location_ID,
  pp.Comp_Plan_ID,
  pp.Comp_Plan_Name,
  pp.Plan_applicable_Level,
  pp.Time_Period,
  pp.Percentage,
  pp.Fiscal_Year,
  pp.Quarter_Number,
  CASE
    WHEN pp.Plan_applicable_Level = 'Employee' THEN COALESCE(es.Sales, 0)
    ELSE                                             COALESCE(ls.Sales, 0)
  END                                               AS Eligible_Sales,
  ROUND(
    CASE
      WHEN pp.Plan_applicable_Level = 'Employee' THEN COALESCE(es.Sales, 0)
      ELSE                                             COALESCE(ls.Sales, 0)
    END * pp.Percentage / 100.0, 2)                 AS Estimated_Commission
FROM plan_periods pp
JOIN `{p}.{d}.Worker_Profile`  wp  ON pp.Employee_Number = wp.Employee_Number
LEFT JOIN `{p}.{d}.Worker_History` wh ON pp.Employee_Number = wh.Employee_Number AND wh.End_date IS NULL
LEFT JOIN emp_sales es ON pp.Employee_Number = es.Employee_Number
                       AND pp.Fiscal_Year    = es.Fiscal_Year
                       AND pp.Quarter_Number = es.Quarter_Number
LEFT JOIN loc_sales ls ON wh.Location_ID     = ls.Location_ID
                       AND pp.Fiscal_Year    = ls.Fiscal_Year
                       AND pp.Quarter_Number = ls.Quarter_Number
""".format(p=PROJECT, d=DATASET))


# ── 7. vw_Manager_Team_Summary ─────────────────────────────────────────────────
# Each manager's direct reports, per-rep sales, and team totals by fiscal quarter.
create_view("vw_Manager_Team_Summary", """
SELECT
  mgr.Employee_Number                              AS Manager_Employee_Number,
  CONCAT(mgr.First_Name, ' ', mgr.Last_Name)       AS Manager_Name,
  mwh.Job_Code                                     AS Manager_Job_Code,
  mwh.Location_ID                                  AS Manager_Location_ID,
  rep.Employee_Number                              AS Rep_Employee_Number,
  CONCAT(rep.First_Name, ' ', rep.Last_Name)       AS Rep_Name,
  rwh.Job_Code                                     AS Rep_Job_Code,
  fc.Fiscal_Year,
  fc.Quarter_Number,
  COUNT(sd.Transaction_ID)                         AS Rep_Transaction_Count,
  SUM(sd.Total_Sale_Amount)                        AS Rep_Sales,
  SUM(SUM(sd.Total_Sale_Amount)) OVER (
    PARTITION BY mgr.Employee_Number, fc.Fiscal_Year, fc.Quarter_Number
  )                                                AS Team_Total_Sales
FROM `{p}.{d}.Worker_Profile`          mgr
JOIN `{p}.{d}.Worker_History`          mwh ON mgr.Employee_Number     = mwh.Employee_Number
                                           AND mwh.End_date IS NULL
                                           AND mwh.Job_Code IN ('MGR', 'DM')
JOIN `{p}.{d}.Worker_Profile`          rep ON rep.Supervisor_Emp_Number = mgr.Employee_Number
JOIN `{p}.{d}.Worker_History`          rwh ON rep.Employee_Number       = rwh.Employee_Number
                                           AND rwh.End_date IS NULL
JOIN `{p}.{d}.Sale_Details`            sd  ON rep.Employee_Number       = sd.Employee_Number
JOIN `{p}.{d}.Fiscal_Calendar_Details` fc  ON sd.Sale_Transaction_Date
                                              BETWEEN fc.Quarter_Start_Date AND fc.Quarter_End_Date
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
""".format(p=PROJECT, d=DATASET))


print("\nAll views created successfully.")
