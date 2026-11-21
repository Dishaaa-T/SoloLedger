"""
What-if financial simulator: how hypothetical events change the cash balance.

Pure logic built on services.forecast. This module does not import FastAPI and
never writes to the database: it only reads invoices, expenses and settings.
Scenarios change in-memory copies of the event lists, so stored rows are never
touched.

Money is summed as integer cents and converted to INR (2 decimal places) at the
end, the same way services.forecast does it.
"""

import sqlite3
from datetime import date, timedelta
from decimal import Decimal

import database
from services.forecast import (
    collect_expense_events,
    collect_income_events,
    project_cashflow,
)

# Forecast windows the simulator accepts.
ALLOWED_FORECAST_DAYS = (30, 60, 90)


class SimulationError(Exception):
    """An error the router turns into an HTTP response.

    status_code is the HTTP status to send and message is the detail text.
    """

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _cents_to_inr(cents: int) -> float:
    """Convert integer cents to INR with 2 decimal places, as a float."""
    return float((Decimal(cents) / 100).quantize(Decimal("0.01")))


def _inr_to_cents(amount: float) -> int:
    """Convert a forecast amount (INR float) back to whole cents."""
    return int(round(amount * 100))


def _sum_by_day(events: list[tuple[str, int, int | None]]) -> dict[str, int]:
    """Add up event amounts per date. Each event is (date_iso, cents, id)."""
    totals: dict[str, int] = {}
    for date_iso, amount_cents, _event_id in events:
        totals[date_iso] = totals.get(date_iso, 0) + amount_cents
    return totals


def _read_starting_cents(conn: sqlite3.Connection) -> int:
    """Read the stored cash balance in cents. A missing value counts as 0."""
    return int(database.get_setting(conn, "cash_balance_cents") or "0")


def _summary(result: dict) -> dict:
    """Pick the four summary fields from one projection result."""
    return {
        "closing_balance": result["projected_closing_balance"],
        "lowest_balance": result["lowest_projected_balance"],
        "lowest_balance_date": result["lowest_balance_date"],
        "risk_of_negative_balance": result["risk_of_negative_balance"],
    }


def _add_scenario_event(
    events: list[tuple[str, int, int | None]],
    amount_cents: int,
    scenario_date: date | None,
    today: date,
    window_end: date,
) -> None:
    """Append a hypothetical event after checking its date is inside the window."""
    if scenario_date is None:
        raise ValueError("A scenario date is required with its amount.")
    if scenario_date < today:
        raise SimulationError(422, "Scenario date cannot be in the past.")
    if scenario_date > window_end:
        raise SimulationError(
            422,
            f"Scenario date must be between {today.isoformat()} "
            f"and {window_end.isoformat()}.",
        )
    # None means "not a stored row", so there is no id to point at.
    events.append((scenario_date.isoformat(), amount_cents, None))


def _apply_invoice_delay(
    conn: sqlite3.Connection,
    simulated_income: list[tuple[str, int, int | None]],
    invoice_id: int,
    delay_days: int,
) -> None:
    """Move one open invoice's expected payment later, in the simulated list only."""
    row = conn.execute(
        "SELECT id, status, paid_date FROM invoices WHERE id = ?",
        (invoice_id,),
    ).fetchone()
    if row is None:
        raise SimulationError(404, f"Invoice {invoice_id} not found.")
    if row["status"] == "paid" or row["paid_date"] is not None:
        raise SimulationError(
            422, f"Invoice {invoice_id} is already paid and cannot be delayed."
        )

    # Find this invoice's expected payment in the baseline list and shift it.
    for index, (date_iso, amount_cents, event_id) in enumerate(simulated_income):
        if event_id == invoice_id:
            shifted = date.fromisoformat(date_iso) + timedelta(days=delay_days)
            simulated_income[index] = (shifted.isoformat(), amount_cents, event_id)
            return
    raise SimulationError(422, f"Invoice {invoice_id} has no open payment to delay.")


def run_what_if(
    conn: sqlite3.Connection,
    today: date,
    forecast_days: int,
    delay_invoice_id: int | None,
    delay_days: int | None,
    expense_amount_cents: int | None,
    expense_date: date | None,
    income_amount_cents: int | None,
    income_date: date | None,
) -> dict:
    """Compare the baseline forecast with a simulated one that has scenarios applied.

    Raises ValueError for bad arguments and SimulationError for scenario
    problems (missing invoice, already paid, date out of range).
    """
    if forecast_days not in ALLOWED_FORECAST_DAYS:
        raise ValueError("forecast_days must be 30, 60 or 90.")
    if (delay_invoice_id is None) != (delay_days is None):
        raise ValueError("delay_invoice_id and delay_days must be provided together.")

    window_end = today + timedelta(days=forecast_days - 1)
    starting_cents = _read_starting_cents(conn)

    # Baseline: the same figures the normal forecast uses.
    baseline_income = collect_income_events(conn, today)
    baseline_expenses = collect_expense_events(conn, today, window_end)
    baseline = project_cashflow(
        starting_cents, baseline_income, baseline_expenses, forecast_days, today
    )

    # Simulated: copies of the baseline lists, changed by each scenario.
    simulated_income = list(baseline_income)
    simulated_expenses = list(baseline_expenses)
    applied_scenarios: list[str] = []

    if delay_invoice_id is not None:
        _apply_invoice_delay(conn, simulated_income, delay_invoice_id, delay_days)
        applied_scenarios.append("delay_payment")

    if expense_amount_cents is not None:
        _add_scenario_event(
            simulated_expenses, expense_amount_cents, expense_date, today, window_end
        )
        applied_scenarios.append("unexpected_expense")

    if income_amount_cents is not None:
        _add_scenario_event(
            simulated_income, income_amount_cents, income_date, today, window_end
        )
        applied_scenarios.append("additional_income")

    simulated = project_cashflow(
        starting_cents, simulated_income, simulated_expenses, forecast_days, today
    )

    # Per-day income and expenses come from the event lists, so they match the
    # balances. Balances come from the projection results.
    baseline_income_by_day = _sum_by_day(baseline_income)
    baseline_expenses_by_day = _sum_by_day(baseline_expenses)
    simulated_income_by_day = _sum_by_day(simulated_income)
    simulated_expenses_by_day = _sum_by_day(simulated_expenses)

    daily_forecast = []
    for base_day, sim_day in zip(baseline["daily_forecast"], simulated["daily_forecast"]):
        day_iso = base_day["date"]
        daily_forecast.append({
            "date": day_iso,
            "baseline_balance": base_day["projected_balance"],
            "simulated_balance": sim_day["projected_balance"],
            "baseline_income": _cents_to_inr(baseline_income_by_day.get(day_iso, 0)),
            "baseline_expenses": _cents_to_inr(baseline_expenses_by_day.get(day_iso, 0)),
            "simulated_income": _cents_to_inr(simulated_income_by_day.get(day_iso, 0)),
            "simulated_expenses": _cents_to_inr(simulated_expenses_by_day.get(day_iso, 0)),
        })

    # Difference is done in cents so float rounding cannot leak in.
    difference_cents = (
        _inr_to_cents(simulated["projected_closing_balance"])
        - _inr_to_cents(baseline["projected_closing_balance"])
    )

    return {
        "currency": "INR",
        "forecast_days": forecast_days,
        "baseline": _summary(baseline),
        "simulated": _summary(simulated),
        "difference": _cents_to_inr(difference_cents),
        "risk_of_negative_balance": simulated["risk_of_negative_balance"],
        "applied_scenarios": applied_scenarios,
        "daily_forecast": daily_forecast,
    }
