"""
investigation_agent.py — Executes an InvestigationPlan and produces a forensic report.

Receives an InvestigationPlan from the planner agent, calls each tool in
tools/icm_tools.py in order, accumulates the evidence, then asks Claude to
reason over all collected data and produce a structured ForensicSummary.

Usage:
    from agents.planner import plan_investigation
    from agents.intake import IntakeResult
    from agents.investigation import investigate

    intake = IntakeResult(employee_number=145, sale_date="2024-11-01",
                          query_type="commission_not_received", summary="...")
    plan   = plan_investigation(intake)
    report = investigate(plan)
    print(report.summary.root_cause)
"""

from dotenv import load_dotenv
load_dotenv()

import json
import operator
from typing import Annotated, Any, Literal, TypedDict

import anthropic
from pydantic import BaseModel, Field

from agents.planner.agent import InvestigationPlan
from tools import icm_tools


# ── Schemas ────────────────────────────────────────────────────────────────────

class EvidenceItem(BaseModel):
    step:        int
    tool:        str
    args:        dict[str, Any]
    description: str
    result:      Any
    error:       str | None = None


class ForensicSummary(BaseModel):
    expected: str = Field(
        description=(
            "What the employee expected to happen — the outcome they should have received "
            "if the system worked correctly and all eligibility conditions were met."
        )
    )
    actual: str = Field(
        description=(
            "What the evidence shows actually happened — discrepancies between "
            "expected commission, recorded sales, active plans, and qualifying conditions."
        )
    )
    root_cause: str = Field(
        description=(
            "The specific reason the gap between expected and actual exists. "
            "Be precise: name the missing plan, the date with no sales, the "
            "disqualifying condition, the calculation error, or confirm everything looks correct."
        )
    )
    recommendation: str = Field(
        description=(
            "Concrete next action: escalate to payroll, correct the plan assignment, "
            "verify the transaction, confirm no action needed, etc."
        )
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description=(
            "Confidence in this conclusion. High = all data present and unambiguous. "
            "Medium = data present but some gaps or ambiguity. "
            "Low = insufficient data to draw a firm conclusion."
        )
    )


class InvestigationReport(BaseModel):
    employee_number: int
    query_type:      str
    sale_date:       str | None
    fiscal_year:     int | None
    quarter_number:  int | None
    evidence:        list[EvidenceItem]
    summary:         ForensicSummary


# ── Tool registry ──────────────────────────────────────────────────────────────

_TOOLS: dict[str, Any] = {
    "is_employee_valid":                      icm_tools.is_employee_valid,
    "get_employee_profile":                   icm_tools.get_employee_profile,
    "get_employee_location_on_date":          icm_tools.get_employee_location_on_date,
    "get_employee_sales_on_date":             icm_tools.get_employee_sales_on_date,
    "get_employee_sales_in_period":           icm_tools.get_employee_sales_in_period,
    "get_employee_sales_summary":             icm_tools.get_employee_sales_summary,
    "get_employee_plans_on_date":             icm_tools.get_employee_plans_on_date,
    "get_sales_qualifying_for_employee_plan": icm_tools.get_sales_qualifying_for_employee_plan,
    "get_sales_qualifying_for_location_plan": icm_tools.get_sales_qualifying_for_location_plan,
    "get_commission_estimate":                icm_tools.get_commission_estimate,
    "get_manager_team_summary":               icm_tools.get_manager_team_summary,
}


# ── Graph state ────────────────────────────────────────────────────────────────

class InvestigationState(TypedDict):
    plan:       InvestigationPlan
    step_index: int                                          # incremented by execute_step
    evidence:   Annotated[list[EvidenceItem], operator.add]  # accumulated across nodes
    summary:    ForensicSummary | None                       # set once by synthesize


# ── Nodes ──────────────────────────────────────────────────────────────────────

def node_execute_step(state: InvestigationState) -> dict:
    """Execute the next planned tool call and append its result as an EvidenceItem."""
    idx  = state["step_index"]
    step = state["plan"].steps[idx]

    fn = _TOOLS.get(step.tool)
    if fn is None:
        result = None
        error  = f"Unknown tool: {step.tool!r}"
    else:
        try:
            result = fn(**step.args)
            error  = None
        except Exception as exc:
            result = None
            error  = str(exc)

    item = EvidenceItem(
        step=step.step,
        tool=step.tool,
        args=step.args,
        description=step.description,
        result=result,
        error=error,
    )
    return {"step_index": idx + 1, "evidence": [item]}


_SYSTEM_PROMPT = """\
You are a forensic analyst for an Incentive Compensation Management (ICM) system.

You will receive:
- A compensation query submitted by (or on behalf of) an employee.
- An ordered set of tool results collected during the investigation.

Your task is to reason carefully over the evidence and produce a structured conclusion
with four fields:

EXPECTED
  What the employee should have received if every system condition was satisfied.
  Ground this in the actual plan rates and sales amounts present in the evidence.
  If the query is "how_much_commission", state the projected amount.

ACTUAL
  What the evidence shows really happened. Point to specific missing records,
  zero-sales results, absent plan assignments, disqualifying conditions, or
  commission amounts that differ from expectation.

ROOT_CAUSE
  The single most specific cause of the discrepancy (or confirmation that there
  is no discrepancy). Examples:
    - "Employee had no sales recorded on the claimed date."
    - "No active Employee-level plan was assigned for the pay period."
    - "Commission was calculated at 5% but the FY2025 rate should be 6%."
    - "All conditions are met — commission matches expectation."

RECOMMENDATION
  A concrete next step for the compensation team.

CONFIDENCE
  high   — all relevant data present, conclusion is unambiguous.
  medium — data present but some gaps or edge-case ambiguity.
  low    — insufficient data to draw a firm conclusion.

ICM domain facts:
- Fiscal year runs Feb 1 → Jan 31. FY2026 = Feb 2025 – Jan 2026.
- Quarters: Q1 Feb–Apr, Q2 May–Jul, Q3 Aug–Oct, Q4 Nov–Jan.
- Employee-level plans (Plans 1, 2, 5, 6, 7) pay commission on the employee's OWN sales.
- Location-level plans (Plans 3, 4) pay commission on the LOCATION'S total sales (manager overrides).
- Org hierarchy: DM (101–105) > MGR (106–120) > SREP (121–140) > REP (141–200).
"""


def node_synthesize(state: InvestigationState) -> dict:
    """Send all collected evidence to Claude and parse a structured ForensicSummary."""
    plan     = state["plan"]
    evidence = state["evidence"]

    evidence_lines: list[str] = []
    for item in evidence:
        evidence_lines.append(f"Step {item.step}: {item.tool}({json.dumps(item.args)})")
        evidence_lines.append(f"  Description : {item.description}")
        if item.error:
            evidence_lines.append(f"  ERROR       : {item.error}")
        else:
            result_str = json.dumps(item.result, indent=4, default=str)
            indented   = "\n".join("  " + ln for ln in result_str.splitlines())
            evidence_lines.append(f"  Result      :\n{indented}")
        evidence_lines.append("")

    user_message = (
        f"EMPLOYEE NUMBER : {plan.employee_number}\n"
        f"QUERY TYPE      : {plan.query_type}\n"
        f"SALE DATE       : {plan.sale_date or 'not specified'}\n"
        f"FISCAL PERIOD   : FY{plan.fiscal_year} Q{plan.quarter_number}\n"
        f"\n{'─' * 60}\n"
        f"EVIDENCE\n"
        f"{'─' * 60}\n"
        + "\n".join(evidence_lines)
    )

    client   = anthropic.Anthropic()
    response = client.messages.parse(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        output_format=ForensicSummary,
    )
    return {"summary": response.parsed_output}


# ── Routing ────────────────────────────────────────────────────────────────────

def _route_after_execute(state: InvestigationState) -> str:
    if state["step_index"] < len(state["plan"].steps):
        return "execute_step"
    return "synthesize"


# ── Graph definition ───────────────────────────────────────────────────────────

def _build_graph():
    from langgraph.graph import END, StateGraph

    g = StateGraph(InvestigationState)

    g.add_node("execute_step", node_execute_step)
    g.add_node("synthesize",   node_synthesize)

    g.set_entry_point("execute_step")

    g.add_conditional_edges(
        "execute_step",
        _route_after_execute,
        {"execute_step": "execute_step", "synthesize": "synthesize"},
    )
    g.add_edge("synthesize", END)

    return g.compile()


_graph = _build_graph()


# ── Public API ─────────────────────────────────────────────────────────────────

def investigate(plan: InvestigationPlan) -> InvestigationReport:
    """
    Execute every step in an InvestigationPlan and return a forensic report.

    Each tool in plan.steps is called against tools/icm_tools.py in order.
    The collected evidence is then passed to Claude which produces a
    ForensicSummary identifying expected outcome, actual outcome, root cause,
    and recommendation.
    """
    initial: InvestigationState = {
        "plan":       plan,
        "step_index": 0,
        "evidence":   [],
        "summary":    None,
    }
    final: InvestigationState = _graph.invoke(initial)

    return InvestigationReport(
        employee_number=plan.employee_number,
        query_type=plan.query_type,
        sale_date=plan.sale_date,
        fiscal_year=plan.fiscal_year,
        quarter_number=plan.quarter_number,
        evidence=final["evidence"],
        summary=final["summary"],
    )


# ── CLI demo ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from agents.intake import IntakeResult
    from agents.planner import plan_investigation

    cases: list[IntakeResult] = [
        IntakeResult(
            employee_number=145,
            sale_date="2024-11-01",
            query_type="commission_not_received",
            summary="Employee expected commission for a November 2024 sale but never received it.",
        ),
        IntakeResult(
            employee_number=131,
            sale_date="2026-03-01",
            query_type="how_much_commission",
            summary="Employee wants to know how much commission they will receive this quarter.",
        ),
    ]

    for intake in cases:
        print(f"\n{'═' * 70}")
        print(f"Employee #{intake.employee_number}  |  {intake.query_type}")
        print(f"{'═' * 70}")

        plan   = plan_investigation(intake)
        report = investigate(plan)

        print(f"\n[EVIDENCE — {len(report.evidence)} steps]")
        for item in report.evidence:
            status = f"ERROR: {item.error}" if item.error else "OK"
            print(f"  {item.step:>2}. {item.tool:<45} [{status}]")

        print(f"\n[FORENSIC SUMMARY]")
        s = report.summary
        print(f"  Expected    : {s.expected}")
        print(f"  Actual      : {s.actual}")
        print(f"  Root Cause  : {s.root_cause}")
        print(f"  Recommend   : {s.recommendation}")
        print(f"  Confidence  : {s.confidence}")
