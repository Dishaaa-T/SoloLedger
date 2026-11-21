"""
Rule-based cash-flow forecast for the next 30, 60 or 90 days.

Pure calculation: this module does not import FastAPI. It reads the invoices,
expenses and settings tables and returns plain Python values. Amounts are
summed as integer cents and converted to INR (2 decimal places) at the end.

Rules (window = today through today + days - 1):
- Starting balance: settings 'cash_balance_cents' (missing = 0).
- Income: unpaid invoices (status pending or overdue, paid_date NULL).
  - Overdue (status 'overdue', or due_date before today) is collected on
    today + 7 days. This is an assumption.
  - Pending and not yet due is collected on its due_date.
  - Paid invoices are never counted.
- Expenses: only 'upcoming' expenses dated from today to the window end.
  'paid' expenses are never counted. 'upcoming' expenses dated before today
  are treated as historical and not counted (a known limitation). No
  recurring expenses are invented.
- Daily balance = previous balance + day's income - day's expenses.

All SQL uses ? placeholders. Column names are fixed text in this file.
"""

import sqlite3
from datetime import date, timedelta
from decimal import Decimal

import database

# Forecast windows the service accepts.
ALLOWED_FORECAST_DAYS = (30, 60, 90)

# Assumed collection delay for overdue invoices, in days from today.
OVERDUE_COLLECTION_DAYS = 7


def _cents_to_inr(cents: int) -> float:
    """Convert integer cents to INR with 2 decimal places, as a float."""
    return float((Decimal(cents) / 100).quantize(Decimal("0.01")))


def _sum_by_date(events: list[tuple[str, int, int]]) -> dict[str, int]:
    """Add up event amounts per date. Each event is (date_iso, cents, id)."""
    totals: dict[str, int] = {}
    for date_iso, amount_cents, _event_id in events:
        totals[date_iso] = totals.get(date_iso, 0) + amount_cents
    return totals


def collect_income_events(
    conn: sqlite3.Connection, today: date
) -> list[tuple[str, int, int]]:
    """Return (collection_date_iso, amount_cents, invoice_id) for unpaid invoices.

    Overdue invoices (status 'overdue' or due_date before today) are collected
    on today + OVERDUE_COLLECTION_DAYS. Pending invoices not yet due are
    collected on their due_date. Ordered by invoice id.
    """
    rows = conn.execute(
        """
        SELECT id, amount_cents, status, due_date FROM invoices
         WHERE status IN ('pending', 'overdue') AND paid_date IS NULL
         ORDER BY id
        """
    ).fetchall()

    today_iso = today.isoformat()
    overdue_date = (today + timedelta(days=OVERDUE_COLLECTION_DAYS)).isoformat()
    events: list[tuple[str, int, int]] = []
    for row in rows:
        is_overdue = row["status"] == "overdue" or row["due_date"] < today_iso
        collect_on = overdue_date if is_overdue else row["due_date"]
        events.append((collect_on, int(row["amount_cents"]), int(row["id"])))
    return events


def collect_expense_events(
    conn: sqlite3.Connection, today: date, window_end: date
) -> list[tuple[str, int, int]]:
    """Return (expense_date_iso, amount_cents, expense_id) for upcoming bills.

    Only 'upcoming' expenses dated from today through window_end (inclusive)
    are returned. Ordered by expense id.
    """
    rows = conn.execute(
        """
        SELECT id, amount_cents, expense_date FROM expenses
         WHERE status = 'upcoming'
           AND expense_date >= ? AND expense_date <= ?
         ORDER BY id
        """,
        (today.isoformat(), window_end.isoformat()),
    ).fetchall()
    return [
        (row["expense_date"], int(row["amount_cents"]), int(row["id"]))
        for row in rows
    ]


def _read_starting_cents(conn: sqlite3.Connection) -> int:
    """Read the stored cash balance in cents. A missing value counts as 0."""
    return int(database.get_setting(conn, "cash_balance_cents") or "0")


def project_cashflow(
    starting_cents: int,
    income_events: list[tuple[str, int, int]],
    expense_events: list[tuple[str, int, int]],
    days: int,
    today: date,
) -> dict:
    """Project the daily balance for `days` days from `today`. Pure: no DB access.

    income_events and expense_events are (date_iso, cents, id) tuples as returned
    by collect_income_events and collect_expense_events. Events outside the
    window never match a daily entry, so they are ignored.

    Returns the forecast dict without the "currency" key; the caller adds it.
    Raises ValueError if days is not 30, 60 or 90.
    """
    if days not in ALLOWED_FORECAST_DAYS:
        raise ValueError("days must be 30, 60 or 90.")

    window_dates = [today + timedelta(days=offset) for offset in range(days)]

    income_by_day = _sum_by_date(income_events)
    expenses_by_day = _sum_by_date(expense_events)

    balance = starting_cents
    total_income = 0
    total_expenses = 0
    lowest_cents: int | None = None
    lowest_date = ""
    risk = False
    daily: list[dict] = []

    for day in window_dates:
        day_iso = day.isoformat()
        day_income = income_by_day.get(day_iso, 0)
        day_expenses = expenses_by_day.get(day_iso, 0)
        balance += day_income - day_expenses
        total_income += day_income
        total_expenses += day_expenses

        # Strict "<" keeps the FIRST day when two days tie for the minimum.
        if lowest_cents is None or balance < lowest_cents:
            lowest_cents = balance
            lowest_date = day_iso
        if balance < 0:
            risk = True

        daily.append({
            "date": day_iso,
            "expected_income": _cents_to_inr(day_income),
            "expected_expenses": _cents_to_inr(day_expenses),
            "projected_balance": _cents_to_inr(balance),
        })

    return {
        "starting_balance": _cents_to_inr(starting_cents),
        "forecast_days": days,
        "expected_income": _cents_to_inr(total_income),
        "expected_expenses": _cents_to_inr(total_expenses),
        "projected_closing_balance": _cents_to_inr(balance),
        "lowest_projected_balance": _cents_to_inr(lowest_cents),
        "lowest_balance_date": lowest_date,
        "risk_of_negative_balance": risk,
        "daily_forecast": daily,
    }


def build_cashflow_forecast(conn: sqlite3.Connection, days: int, today: date) -> dict:
    """Build the day-by-day cash-flow forecast for `days` days from `today`.

    Returns a dict that matches CashflowForecastOut. Money values are INR
    floats with 2 decimal places. Raises ValueError if days is not 30, 60 or 90.
    """
    if days not in ALLOWED_FORECAST_DAYS:
        raise ValueError("days must be 30, 60 or 90.")

    window_end = today + timedelta(days=days - 1)
    income_events = collect_income_events(conn, today)
    expense_events = collect_expense_events(conn, today, window_end)
    projection = project_cashflow(
        _read_starting_cents(conn), income_events, expense_events, days, today
    )

    return {
        "starting_balance": projection["starting_balance"],
        "currency": database.get_setting(conn, "currency") or "INR",
        "forecast_days": projection["forecast_days"],
        "expected_income": projection["expected_income"],
        "expected_expenses": projection["expected_expenses"],
        "projected_closing_balance": projection["projected_closing_balance"],
        "lowest_projected_balance": projection["lowest_projected_balance"],
        "lowest_balance_date": projection["lowest_balance_date"],
        "risk_of_negative_balance": projection["risk_of_negative_balance"],
        "daily_forecast": projection["daily_forecast"],
    }

