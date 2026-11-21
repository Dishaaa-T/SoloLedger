"""
Financial dashboard calculations.

Every money value is summed in SQL from the real invoices, expenses and
settings tables. Nothing is hardcoded or sampled. Amounts are stored as
integer cents and converted to INR (2 decimal places) only at the end.

Definitions:
- total_income: paid invoices, by paid_date, inside the period.
- total_expenses: all recorded expenses (any status), by expense_date,
  inside the period.
- net_profit: total_income - total_expenses (can be negative).
- pending_payments: every unpaid invoice (status pending or overdue), all time.
  Overdue invoices are included here too.
- overdue_payments: unpaid invoices that are marked overdue or whose due_date
  is before today, all time. This is a subset of pending_payments.
- available_cash: the settings cash balance. Not computed from invoices or
  expenses.

All SQL uses ? placeholders. Column names are fixed text in this file.
"""

import calendar
import sqlite3
from datetime import date
from decimal import Decimal

import database


def period_bounds(period: str, today: date) -> tuple[str | None, str | None]:
    """Return the inclusive (start, end) ISO dates for a dashboard period.

    - this_month: first to last day of the current month.
    - last_month: first to last day of the previous month (January goes back
      to December of the previous year).
    - all_time: (None, None), which means no date filter.
    """
    if period == "all_time":
        return None, None
    if period == "this_month":
        year, month = today.year, today.month
    elif period == "last_month":
        if today.month == 1:
            year, month = today.year - 1, 12
        else:
            year, month = today.year, today.month - 1
    else:
        raise ValueError(f"Unknown dashboard period: {period}")

    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1).isoformat(), date(year, month, last_day).isoformat()


def _cents_to_inr(cents: int) -> float:
    """Convert integer cents to INR with 2 decimal places, as a float."""
    return float((Decimal(cents) / 100).quantize(Decimal("0.01")))


def _date_filter(column: str, start: str | None, end: str | None) -> tuple[str, list]:
    """Return a SQL 'AND ... BETWEEN' clause and its params, or nothing if unbounded."""
    if start is None or end is None:
        return "", []
    return f" AND {column} BETWEEN ? AND ?", [start, end]


def _sum_income_cents(conn: sqlite3.Connection, start: str | None, end: str | None) -> int:
    """Sum of paid invoices whose paid_date falls in the period."""
    clause, params = _date_filter("paid_date", start, end)
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM invoices "
        "WHERE status = 'paid' AND paid_date IS NOT NULL" + clause,
        params,
    ).fetchone()
    return int(row[0])


def _sum_expenses_cents(conn: sqlite3.Connection, start: str | None, end: str | None) -> int:
    """Sum of all recorded expenses whose expense_date falls in the period."""
    clause, params = _date_filter("expense_date", start, end)
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM expenses WHERE 1 = 1" + clause,
        params,
    ).fetchone()
    return int(row[0])


def _sum_pending_cents(conn: sqlite3.Connection) -> int:
    """Sum of all unpaid invoices, all time (overdue ones included)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM invoices WHERE status != 'paid'"
    ).fetchone()
    return int(row[0])


def _sum_overdue_cents(conn: sqlite3.Connection, today: date) -> int:
    """Sum of unpaid invoices that are marked overdue or past their due date."""
    row = conn.execute(
        """
        SELECT COALESCE(SUM(amount_cents), 0) FROM invoices
         WHERE status != 'paid'
           AND (status = 'overdue' OR due_date < ?)
        """,
        (today.isoformat(),),
    ).fetchone()
    return int(row[0])


def _read_cash_cents(conn: sqlite3.Connection) -> int:
    """Read the stored cash balance in cents. A missing value counts as 0."""
    return int(database.get_setting(conn, "cash_balance_cents") or "0")


def compute_dashboard(conn: sqlite3.Connection, period: str, today: date) -> dict:
    """Calculate every dashboard metric for one period.

    Returns a dict that matches DashboardSummaryOut: money values are INR
    floats with 2 decimal places.
    """
    start, end = period_bounds(period, today)

    income = _sum_income_cents(conn, start, end)
    expenses = _sum_expenses_cents(conn, start, end)

    return {
        "period": period,
        "currency": database.get_setting(conn, "currency") or "INR",
        "total_income": _cents_to_inr(income),
        "total_expenses": _cents_to_inr(expenses),
        "net_profit": _cents_to_inr(income - expenses),
        "pending_payments": _cents_to_inr(_sum_pending_cents(conn)),
        "overdue_payments": _cents_to_inr(_sum_overdue_cents(conn, today)),
        "available_cash": _cents_to_inr(_read_cash_cents(conn)),
    }
