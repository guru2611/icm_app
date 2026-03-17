"""
intake_agent.py — Parses unstructured compensation query text into a structured object.

Input:  employee_number (int) + free-text query (str)
Output: IntakeResult with employee_number, sale_date, and query_type
"""

from dotenv import load_dotenv
load_dotenv()

import anthropic
from pydantic import BaseModel, Field
from typing import Literal
from datetime import date


# ── Output schema ──────────────────────────────────────────────────────────────

class IntakeResult(BaseModel):
    employee_number: int = Field(
        description="The employee number provided by the caller."
    )
    sale_date: str | None = Field(
        description=(
            "ISO 8601 date (YYYY-MM-DD) extracted from the query. "
            "If no day is mentioned, default to the 1st of the stated month. "
            "If no date can be determined, set to null."
        )
    )
    query_type: Literal[
        "commission_not_received",
        "incorrect_commission_received",
        "how_much_commission",
        "other",
    ] = Field(
        description=(
            "Classified intent of the query:\n"
            "  commission_not_received      — employee expected commission but did not receive it\n"
            "  incorrect_commission_received — employee received commission but the amount is wrong\n"
            "  how_much_commission          — employee is asking what commission they will or should receive\n"
            "  other                        — none of the above"
        )
    )
    summary: str = Field(
        description="One-sentence plain-English summary of what the employee is asking."
    )


# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an intake parser for an Incentive Compensation Management (ICM) system.

Your job is to read a compensation-related query submitted by or on behalf of an employee and
extract structured fields from it. Follow these rules precisely:

EMPLOYEE NUMBER
- Always use the employee number passed to you — never infer it from the text.

SALE DATE
- Extract any date or time reference related to the compensation query (e.g., sale date,
  pay period, month of commission, when the sale occurred).
- If a full date (day + month + year) is given, use it exactly.
- If only month and year are given (e.g., "March 2025"), default the day to 01 → "2025-03-01".
- If only a month name is given with no year (e.g., "last March"), infer the most recent
  occurrence of that month relative to today's date.
- If no date can be determined, set sale_date to null.
- Always output dates in ISO 8601 format: YYYY-MM-DD.

QUERY TYPE — classify into exactly one of:
  commission_not_received       The employee expected to receive commission/payment but has not.
                                Keywords: "didn't receive", "missing", "not paid", "never got",
                                "where is my commission", "hasn't arrived".
  incorrect_commission_received The employee received commission but believes the amount is wrong.
                                Keywords: "wrong amount", "incorrect", "too low", "too high",
                                "should have been more/less", "miscalculated", "short-paid".
  how_much_commission           The employee is asking what they will receive or what they are owed.
                                Keywords: "how much", "what will I get", "calculate", "estimate",
                                "what am I owed", "what should I expect".
  other                         Anything that does not clearly fit the above categories.

SUMMARY
- Write a single sentence summarising the employee's concern in plain English.
  Do not mention the employee number. Do not repeat the query verbatim.
"""


# ── Agent ──────────────────────────────────────────────────────────────────────

_client = anthropic.Anthropic()


def parse_query(employee_number: int, query_text: str) -> IntakeResult:
    """
    Parse an unstructured compensation query into a structured IntakeResult.

    Args:
        employee_number: The employee's ID number (provided by the caller).
        query_text:      Free-form text describing the employee's compensation concern.

    Returns:
        IntakeResult with employee_number, sale_date, query_type, and summary.
    """
    user_message = (
        f"Employee number: {employee_number}\n\n"
        f"Query:\n{query_text.strip()}"
    )

    response = _client.messages.parse(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        output_format=IntakeResult,
    )

    result: IntakeResult = response.parsed_output
    # Always enforce the provided employee number (never let the model override it)
    result.employee_number = employee_number
    return result


# ── CLI demo ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    today = date.today().isoformat()
    print(f"ICM Intake Agent  |  today: {today}\n{'─'*60}")

    test_cases = [
        (
            145,
            "Hi, I made a sale back in November 2024 but I never received "
            "my commission for it. Can someone look into this?",
        ),
        (
            162,
            "The commission I got paid for my March 15th sale is completely wrong. "
            "I sold a $4,200 package and only got paid $50. Something's off.",
        ),
        (
            131,
            "Hey, I closed a big deal last week. How much commission am I going to get for it?",
        ),
        (
            110,
            "I'd like to understand my comp plan structure for the current fiscal year.",
        ),
        (
            178,
            "I did a sale on 5th January 2025 and I haven't seen any commission come through yet.",
        ),
    ]

    for emp, text in test_cases:
        print(f"\nEmployee #{emp}")
        print(f"Input: {text}")
        result = parse_query(emp, text)
        print(f"Output: {json.dumps(result.model_dump(), indent=2)}")
        print("─" * 60)
