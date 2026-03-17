"""
planner_agent.py — Converts an IntakeResult into an ordered investigation plan.

Receives the structured output from the intake agent and produces an
InvestigationPlan: an ordered list of ToolCall steps to execute against
tools/icm_tools.py, routed by query_type using a LangGraph StateGraph.

Usage:
    from agents.intake import IntakeResult
    from agents.planner import plan_investigation

    intake = IntakeResult(employee_number=145, sale_date="2024-11-01",
                          query_type="commission_not_received", summary="...")
    plan   = plan_investigation(intake)
    for step in plan.steps:
        print(step.tool, step.args)
"""

import operator
from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from agents.intake.agent import IntakeResult


# ── Output schema ──────────────────────────────────────────────────────────────

class ToolCall(BaseModel):
    """A single planned call to a function in tools/icm_tools.py."""
    step:        int
    tool:        str
    args:        dict[str, Any]
    description: str


class InvestigationPlan(BaseModel):
    employee_number: int
    query_type:      str
    sale_date:       str | None
    fiscal_year:     int | None
    quarter_number:  int | None
    steps:           list[ToolCall]


# ── Graph state ────────────────────────────────────────────────────────────────

class PlannerState(TypedDict):
    intake:  IntakeResult
    # Each node appends its ToolCall(s); the reducer merges them in order.
    steps:   Annotated[list[ToolCall], operator.add]


# ── Fiscal-period helper ───────────────────────────────────────────────────────

def _fiscal_period(date_str: str | None) -> tuple[int, int]:
    """
    Convert a YYYY-MM-DD string to (fiscal_year, quarter_number).

    Fiscal year runs Feb 1 → Jan 31.
      FY2026 = Feb 1 2025 – Jan 31 2026
    Quarters:
      Q1 = Feb–Apr   Q2 = May–Jul
      Q3 = Aug–Oct   Q4 = Nov–Jan
    """
    d = date.fromisoformat(date_str) if date_str else date.today()

    fy  = d.year if d.month == 1 else d.year + 1
    m   = d.month
    qtr = 4 if m == 1 else (
          1 if 2 <= m <= 4 else
          2 if 5 <= m <= 7 else
          3 if 8 <= m <= 10 else
          4)   # Nov–Dec

    return fy, qtr


# ── Node helpers ───────────────────────────────────────────────────────────────

def _step(state: PlannerState, tool: str, args: dict, description: str) -> dict:
    """Build the reducer-compatible return value for a single node."""
    n = len(state["steps"]) + 1
    return {"steps": [ToolCall(step=n, tool=tool, args=args, description=description)]}


# ── Nodes ──────────────────────────────────────────────────────────────────────

def node_validate_employee(state: PlannerState) -> dict:
    emp = state["intake"].employee_number
    return _step(
        state, "is_employee_valid",
        {"employee_number": emp},
        f"Verify employee #{emp} exists in Worker_Profile.",
    )


def node_get_profile(state: PlannerState) -> dict:
    emp = state["intake"].employee_number
    return _step(
        state, "get_employee_profile",
        {"employee_number": emp},
        f"Fetch full profile for employee #{emp}: job level, location hierarchy, supervisor.",
    )


def node_get_location_on_date(state: PlannerState) -> dict:
    emp = state["intake"].employee_number
    dt  = state["intake"].sale_date
    return _step(
        state, "get_employee_location_on_date",
        {"employee_number": emp, "on_date": dt},
        f"Resolve which store employee #{emp} was assigned to on {dt} via Worker_History.",
    )


def node_get_sales_on_date(state: PlannerState) -> dict:
    emp = state["intake"].employee_number
    dt  = state["intake"].sale_date
    return _step(
        state, "get_employee_sales_on_date",
        {"employee_number": emp, "sale_date": dt},
        f"Retrieve all sales transactions for employee #{emp} on {dt}.",
    )


def node_get_plans_on_date(state: PlannerState) -> dict:
    emp = state["intake"].employee_number
    dt  = state["intake"].sale_date
    return _step(
        state, "get_employee_plans_on_date",
        {"employee_number": emp, "on_date": dt},
        f"List all active comp plans for employee #{emp} on {dt}.",
    )


def node_check_employee_plan(state: PlannerState) -> dict:
    emp = state["intake"].employee_number
    dt  = state["intake"].sale_date
    return _step(
        state, "get_sales_qualifying_for_employee_plan",
        {"employee_number": emp, "sale_date": dt},
        (
            f"Check whether employee #{emp}'s sales on {dt} qualify under "
            "an Employee-level comp plan (commission on own sales)."
        ),
    )


def node_check_location_plan(state: PlannerState) -> dict:
    emp = state["intake"].employee_number
    dt  = state["intake"].sale_date
    return _step(
        state, "get_sales_qualifying_for_location_plan",
        {"employee_number": emp, "sale_date": dt},
        (
            f"Check whether employee #{emp}'s sales on {dt} qualify under "
            "a Location-level plan (manager override — commission on location's total sales)."
        ),
    )


def node_get_sales_summary(state: PlannerState) -> dict:
    emp     = state["intake"].employee_number
    fy, qtr = _fiscal_period(state["intake"].sale_date)
    return _step(
        state, "get_employee_sales_summary",
        {"employee_number": emp, "fiscal_year": fy, "quarter_number": qtr},
        f"Get aggregated sales totals for employee #{emp} in FY{fy} Q{qtr}.",
    )


def node_estimate_commission(state: PlannerState) -> dict:
    emp     = state["intake"].employee_number
    fy, qtr = _fiscal_period(state["intake"].sale_date)
    return _step(
        state, "get_commission_estimate",
        {"employee_number": emp, "fiscal_year": fy, "quarter_number": qtr},
        (
            f"Estimate commission for employee #{emp} in FY{fy} Q{qtr}, "
            "broken down by comp plan."
        ),
    )


# ── Routing ────────────────────────────────────────────────────────────────────

def route_by_query_type(
    state: PlannerState,
) -> Literal["get_location_on_date", "get_sales_summary", "__end__"]:
    qt = state["intake"].query_type
    if qt in ("commission_not_received", "incorrect_commission_received"):
        return "get_location_on_date"
    if qt == "how_much_commission":
        return "get_sales_summary"
    return "__end__"          # query_type == "other"


# ── Graph definition ───────────────────────────────────────────────────────────

def _build_graph() -> Any:
    g = StateGraph(PlannerState)

    g.add_node("validate_employee",    node_validate_employee)
    g.add_node("get_profile",          node_get_profile)
    g.add_node("get_location_on_date", node_get_location_on_date)
    g.add_node("get_sales_on_date",    node_get_sales_on_date)
    g.add_node("get_plans_on_date",    node_get_plans_on_date)
    g.add_node("check_employee_plan",  node_check_employee_plan)
    g.add_node("check_location_plan",  node_check_location_plan)
    g.add_node("get_sales_summary",    node_get_sales_summary)
    g.add_node("estimate_commission",  node_estimate_commission)

    g.set_entry_point("validate_employee")
    g.add_edge("validate_employee", "get_profile")

    g.add_conditional_edges(
        "get_profile",
        route_by_query_type,
        {
            "get_location_on_date": "get_location_on_date",
            "get_sales_summary":    "get_sales_summary",
            "__end__":              END,
        },
    )

    # commission_not_received / incorrect_commission_received path
    g.add_edge("get_location_on_date", "get_sales_on_date")
    g.add_edge("get_sales_on_date",    "get_plans_on_date")
    g.add_edge("get_plans_on_date",    "check_employee_plan")
    g.add_edge("check_employee_plan",  "check_location_plan")
    g.add_edge("check_location_plan",  "estimate_commission")
    g.add_edge("estimate_commission",  END)

    # how_much_commission path
    g.add_edge("get_sales_summary", "estimate_commission")

    return g.compile()


_graph = _build_graph()


# ── Public API ─────────────────────────────────────────────────────────────────

def plan_investigation(intake: IntakeResult) -> InvestigationPlan:
    """
    Convert an IntakeResult into an ordered InvestigationPlan.

    Runs the LangGraph planner synchronously and returns the list of
    ToolCall steps that should be executed (in order) against tools/icm_tools.py.
    """
    final_state: PlannerState = _graph.invoke({"intake": intake, "steps": []})

    fy, qtr = _fiscal_period(intake.sale_date)

    return InvestigationPlan(
        employee_number=intake.employee_number,
        query_type=intake.query_type,
        sale_date=intake.sale_date,
        fiscal_year=fy,
        quarter_number=qtr,
        steps=final_state["steps"],
    )


# ── CLI demo ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    cases: list[IntakeResult] = [
        IntakeResult(
            employee_number=145,
            sale_date="2024-11-01",
            query_type="commission_not_received",
            summary="Employee expected commission for a November 2024 sale but never received it.",
        ),
        IntakeResult(
            employee_number=162,
            sale_date="2025-03-15",
            query_type="incorrect_commission_received",
            summary="Employee believes the commission paid for a March 15 sale was incorrect.",
        ),
        IntakeResult(
            employee_number=131,
            sale_date="2026-03-10",
            query_type="how_much_commission",
            summary="Employee wants to know how much commission they will receive for a recent sale.",
        ),
        IntakeResult(
            employee_number=110,
            sale_date=None,
            query_type="other",
            summary="Employee wants to understand their comp plan structure for the current fiscal year.",
        ),
    ]

    for intake in cases:
        plan = plan_investigation(intake)
        print(f"\nEmployee #{intake.employee_number}  |  {intake.query_type}")
        print(f"Summary : {intake.summary}")
        print(f"Period  : FY{plan.fiscal_year} Q{plan.quarter_number}")
        print("Steps:")
        for s in plan.steps:
            print(f"  {s.step}. [{s.tool}]  {s.description}")
            print(f"     args: {json.dumps(s.args)}")
        print("─" * 70)
