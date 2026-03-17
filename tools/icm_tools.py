"""
icm_tools.py — Agent-callable tool functions for the ICM Analytics dataset.

Each function returns plain Python objects (dicts / lists of dicts / bools)
so they can be serialised directly into agent responses.
"""

from datetime import date, datetime
from google.cloud import bigquery

PROJECT = "glossy-buffer-411806"
DATASET = "icm_analytics"

_client = bigquery.Client(project=PROJECT)


# ── helpers ────────────────────────────────────────────────────────────────────

def _q(sql: str, params: list | None = None) -> list[dict]:
    """Execute a parameterised query and return rows as a list of dicts."""
    cfg = bigquery.QueryJobConfig(query_parameters=params or [])
    rows = _client.query(sql, job_config=cfg).result()
    return [dict(row) for row in rows]


def _int(name: str, value: int) -> bigquery.ScalarQueryParameter:
    return bigquery.ScalarQueryParameter(name, "INT64", value)


def _str(name: str, value: str) -> bigquery.ScalarQueryParameter:
    return bigquery.ScalarQueryParameter(name, "STRING", value)


def _date(name: str, value: str | date) -> bigquery.ScalarQueryParameter:
    if isinstance(value, (date, datetime)):
        value = value.isoformat()
    return bigquery.ScalarQueryParameter(name, "DATE", value)


def _ref(table: str) -> str:
    return f"`{PROJECT}.{DATASET}.{table}`"


# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYEE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def is_employee_valid(employee_number: int) -> bool:
    """
    Check whether an employee number exists in the system.

    Returns True if the employee is found in Worker_Profile, False otherwise.
    """
    rows = _q(
        f"SELECT 1 FROM {_ref('Worker_Profile')} WHERE Employee_Number = @emp LIMIT 1",
        [_int("emp", employee_number)],
    )
    return len(rows) > 0


def get_employee_profile(employee_number: int) -> dict | None:
    """
    Return the full profile for an employee.

    Includes: name, job code, current location and its full hierarchy
    (store → district → market → territory), and supervisor name.
    Returns None if the employee does not exist.
    """
    rows = _q(
        f"""
        SELECT *
        FROM   {_ref('vw_Employee_Roster')}
        WHERE  Employee_Number = @emp
        """,
        [_int("emp", employee_number)],
    )
    return rows[0] if rows else None


def get_employee_location_on_date(employee_number: int, on_date: str) -> dict | None:
    """
    Return the location an employee was assigned to on a specific date.

    Looks at Worker_History records to find the assignment that was active
    on that date (Start_date <= on_date AND (End_date IS NULL OR End_date >= on_date)).
    Returns location details or None if no record is found.
    """
    rows = _q(
        f"""
        SELECT
            wh.Employee_Number,
            wh.Job_Code,
            wh.Start_date,
            wh.End_date,
            ld.Location_ID,
            ld.Location_Name,
            ld.Store_Name,
            ld.District,
            ld.Market,
            ld.Territory
        FROM   {_ref('Worker_History')}   wh
        JOIN   {_ref('Location_Details')} ld ON wh.Location_ID = ld.Location_ID
        WHERE  wh.Employee_Number = @emp
          AND  wh.Start_date     <= @dt
          AND  (wh.End_date IS NULL OR wh.End_date >= @dt)
        """,
        [_int("emp", employee_number), _date("dt", on_date)],
    )
    return rows[0] if rows else None


# ══════════════════════════════════════════════════════════════════════════════
# SALES FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_employee_sales_on_date(employee_number: int, sale_date: str) -> list[dict]:
    """
    Return all sales transactions made by an employee on a specific date.

    Each row includes transaction details, fiscal year/quarter, and location
    hierarchy. Returns an empty list if no sales were made on that date.
    """
    return _q(
        f"""
        SELECT *
        FROM   {_ref('vw_Sales_With_Fiscal_Period')}
        WHERE  Employee_Number        = @emp
          AND  Sale_Transaction_Date  = @dt
        ORDER BY Transaction_ID
        """,
        [_int("emp", employee_number), _date("dt", sale_date)],
    )


def get_employee_sales_in_period(
    employee_number: int, start_date: str, end_date: str
) -> list[dict]:
    """
    Return all sales transactions made by an employee within a date range (inclusive).

    Each row includes transaction details, fiscal year/quarter, and location
    hierarchy. Returns an empty list if no sales were found.
    """
    return _q(
        f"""
        SELECT *
        FROM   {_ref('vw_Sales_With_Fiscal_Period')}
        WHERE  Employee_Number       = @emp
          AND  Sale_Transaction_Date BETWEEN @start AND @end
        ORDER BY Sale_Transaction_Date, Transaction_ID
        """,
        [
            _int("emp", employee_number),
            _date("start", start_date),
            _date("end", end_date),
        ],
    )


def get_employee_sales_summary(
    employee_number: int, fiscal_year: int, quarter_number: int
) -> dict | None:
    """
    Return aggregated sales totals for an employee in a specific fiscal quarter.

    Returns a dict with Transaction_Count and Total_Sales, or None if the
    employee had no sales in that period.
    """
    rows = _q(
        f"""
        SELECT *
        FROM   {_ref('vw_Employee_Sales_by_Period')}
        WHERE  Employee_Number = @emp
          AND  Fiscal_Year     = @fy
          AND  Quarter_Number  = @qtr
        """,
        [
            _int("emp", employee_number),
            _int("fy", fiscal_year),
            _int("qtr", quarter_number),
        ],
    )
    return rows[0] if rows else None


# ══════════════════════════════════════════════════════════════════════════════
# PLAN & ELIGIBILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_employee_plans_on_date(employee_number: int, on_date: str) -> list[dict]:
    """
    Return all comp plan assignments active for an employee on a given date.

    Each row includes the plan name, applicable level (Employee / Location),
    time period, and percentage rate. Returns an empty list if no active
    assignments are found.
    """
    return _q(
        f"""
        SELECT
            pa.Employee_Number,
            pa.Comp_Plan_ID,
            pd.Comp_Plan_Name,
            pd.Plan_applicable_Level,
            pd.Time_Period,
            pd.Percentage,
            pa.Start_Date AS Assignment_Start,
            pa.End_Date   AS Assignment_End
        FROM   {_ref('Plan_assignment')} pa
        JOIN   {_ref('Plan_Details')}    pd
               ON  pa.Comp_Plan_ID = pd.Comp_Plan_ID
               AND @dt BETWEEN pd.Start_Date AND pd.End_Date
        WHERE  pa.Employee_Number = @emp
          AND  @dt BETWEEN pa.Start_Date AND pa.End_Date
        """,
        [_int("emp", employee_number), _date("dt", on_date)],
    )


def get_sales_qualifying_for_employee_plan(
    employee_number: int, sale_date: str
) -> dict:
    """
    Check whether an employee made sales on a date that are eligible under
    an Employee-level comp plan.

    An Employee-level plan pays commission on the employee's own sales.
    Returns:
      qualified       — True if the employee has sales AND an active Employee-level plan.
      sales           — List of transactions made on that date.
      qualifying_plans— Active Employee-level plans on that date.
      reason          — Human-readable explanation when not qualified.
    """
    sales = get_employee_sales_on_date(employee_number, sale_date)

    plans = _q(
        f"""
        SELECT
            pa.Comp_Plan_ID,
            pd.Comp_Plan_Name,
            pd.Plan_applicable_Level,
            pd.Time_Period,
            pd.Percentage
        FROM   {_ref('Plan_assignment')} pa
        JOIN   {_ref('Plan_Details')}    pd
               ON  pa.Comp_Plan_ID          = pd.Comp_Plan_ID
               AND @dt BETWEEN pd.Start_Date AND pd.End_Date
        WHERE  pa.Employee_Number           = @emp
          AND  @dt BETWEEN pa.Start_Date AND pa.End_Date
          AND  pd.Plan_applicable_Level     = 'Employee'
        """,
        [_int("emp", employee_number), _date("dt", sale_date)],
    )

    has_sales = len(sales) > 0
    has_plan  = len(plans) > 0
    qualified = has_sales and has_plan

    if qualified:
        reason = None
    elif not has_sales and not has_plan:
        reason = "No sales on this date and no active Employee-level plan."
    elif not has_sales:
        reason = "Employee has an active Employee-level plan but made no sales on this date."
    else:
        reason = "Employee made sales on this date but has no active Employee-level plan."

    return {
        "qualified":        qualified,
        "sales":            sales,
        "qualifying_plans": plans,
        "reason":           reason,
    }


def get_sales_qualifying_for_location_plan(
    employee_number: int, sale_date: str
) -> dict:
    """
    Check whether an employee made a sale that qualifies under a Location-level
    comp plan based on their assigned location as of the sale date.

    A Location-level plan (e.g. manager override) pays commission on total
    location sales, not just the individual employee's sales. Qualification
    requires: (1) the employee made a sale on that date, (2) the employee has
    an active Location-level plan, and (3) the employee's location on that
    date can be resolved from their work history.

    Returns:
      qualified          — True when all three conditions are met.
      sales              — Transactions made by the employee on that date.
      location           — The employee's assigned location on that date.
      qualifying_plans   — Active Location-level plans on that date.
      location_day_sales — Total sales at that location on that date
                           (the base used for the override commission).
      reason             — Human-readable explanation when not qualified.
    """
    sales    = get_employee_sales_on_date(employee_number, sale_date)
    location = get_employee_location_on_date(employee_number, sale_date)

    plans = _q(
        f"""
        SELECT
            pa.Comp_Plan_ID,
            pd.Comp_Plan_Name,
            pd.Plan_applicable_Level,
            pd.Time_Period,
            pd.Percentage
        FROM   {_ref('Plan_assignment')} pa
        JOIN   {_ref('Plan_Details')}    pd
               ON  pa.Comp_Plan_ID          = pd.Comp_Plan_ID
               AND @dt BETWEEN pd.Start_Date AND pd.End_Date
        WHERE  pa.Employee_Number           = @emp
          AND  @dt BETWEEN pa.Start_Date AND pa.End_Date
          AND  pd.Plan_applicable_Level     = 'Location'
        """,
        [_int("emp", employee_number), _date("dt", sale_date)],
    )

    # Total sales at the employee's location on that date
    location_day_sales = None
    if location:
        loc_rows = _q(
            f"""
            SELECT
                Location_ID,
                COUNT(Transaction_ID)  AS Transaction_Count,
                SUM(Total_Sale_Amount) AS Total_Sales
            FROM   {_ref('Sale_Details')}
            WHERE  Location_ID            = @loc
              AND  Sale_Transaction_Date  = @dt
            GROUP BY Location_ID
            """,
            [_int("loc", location["Location_ID"]), _date("dt", sale_date)],
        )
        location_day_sales = loc_rows[0] if loc_rows else None

    has_sales    = len(sales) > 0
    has_plan     = len(plans) > 0
    has_location = location is not None
    qualified    = has_sales and has_plan and has_location

    if qualified:
        reason = None
    elif not has_location:
        reason = "Could not resolve employee's location from work history on this date."
    elif not has_plan:
        reason = "Employee has no active Location-level plan on this date."
    elif not has_sales:
        reason = "Employee has a Location-level plan but made no sales on this date."
    else:
        reason = "Conditions not met."

    return {
        "qualified":          qualified,
        "sales":              sales,
        "location":           location,
        "qualifying_plans":   plans,
        "location_day_sales": location_day_sales,
        "reason":             reason,
    }


# ══════════════════════════════════════════════════════════════════════════════
# COMMISSION FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_commission_estimate(
    employee_number: int, fiscal_year: int, quarter_number: int
) -> list[dict]:
    """
    Return estimated commission for an employee in a specific fiscal quarter,
    broken down by comp plan.

    Employee-level plans calculate commission from the employee's own sales.
    Location-level plans calculate commission from the total sales at the
    employee's assigned location (override / management plans).

    Returns a list of rows — one per active plan — each containing
    Eligible_Sales and Estimated_Commission.
    """
    return _q(
        f"""
        SELECT *
        FROM   {_ref('vw_Commission_Estimate')}
        WHERE  Employee_Number = @emp
          AND  Fiscal_Year     = @fy
          AND  Quarter_Number  = @qtr
        ORDER BY Comp_Plan_ID
        """,
        [
            _int("emp", employee_number),
            _int("fy", fiscal_year),
            _int("qtr", quarter_number),
        ],
    )


def get_manager_team_summary(
    manager_employee_number: int, fiscal_year: int, quarter_number: int
) -> list[dict]:
    """
    Return a breakdown of each direct report's sales performance for a manager
    in a specific fiscal quarter, along with the team total.

    Useful for manager override commission calculations (Location-level plans)
    and for performance reviews. Each row represents one direct report and
    includes Rep_Sales and the Team_Total_Sales window aggregate.
    """
    return _q(
        f"""
        SELECT *
        FROM   {_ref('vw_Manager_Team_Summary')}
        WHERE  Manager_Employee_Number = @mgr
          AND  Fiscal_Year             = @fy
          AND  Quarter_Number          = @qtr
        ORDER BY Rep_Sales DESC
        """,
        [
            _int("mgr", manager_employee_number),
            _int("fy", fiscal_year),
            _int("qtr", quarter_number),
        ],
    )
