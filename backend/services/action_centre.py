"""
Action Centre: rule-based alerts and recommended actions for the freelancer.

Pure logic. This module does not import FastAPI and only runs SELECT queries.
It reuses the forecast service (cash-flow risk) and the dashboard service
(month ranges). Amounts are summed as integer cents and converted to INR
(2 decimal places) at the end.

Alert categories:
- overdue_payment: unpaid invoices that are overdue (one alert per invoice).
- pending_payment: one summary alert for unpaid invoices not yet due.
- negative_cash_flow / low_cash_flow: the 90-day cash-flow forecast.
- upcoming_expense: 'upcoming' expenses scheduled in the next 90 days.
- expense_trend: this month's expenses well above last month's.
"""

import sqlite3
from datetime import date, timedelta
from decimal import Decimal

import database
from services.dashboard import period_bounds
from services.forecast import build_cashflow_forecast

# Warning level for the projected cash balance, in cents (INR 5,000). Used when
# the settings key below is missing or not an integer.
DEFAULT_LOW_CASH_THRESHOLD_CENTS = 500000

# Settings key that can override the default threshold. Read-only here: no API
# writes it.
LOW_CASH_THRESHOLD_SETTING = "low_cash_threshold_cents"

# Number of days covered by the cash-flow forecast and the upcoming-expense look-ahead.
FORECAST_HORIZON_DAYS = 90

# Month-on-month rise in expenses (percent) that triggers an expense trend alert.
SIGNIFICANT_EXPENSE_INCREASE_PERCENT = 20

# An overdue invoice is critical at this many days overdue or more.
CRITICAL_OVERDUE_DAYS = 30

# An overdue invoice is high priority at this many days overdue or more.
HIGH_OVERDUE_DAYS = 7

# An overdue invoice of this amount (in cents, INR 50,000) or more is high priority.
HIGH_VALUE_INVOICE_CENTS = 5000000

# Upcoming expenses and pending-payment summaries due within this many days are
# treated as urgent.
UPCOMING_HIGH_PRIORITY_DAYS = 7

# Sort order for priorities. A lower rank is more urgent.
PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _cents_to_inr(cents: int) -> float:
    """Convert integer cents to INR with 2 decimal places, as a float."""
    return float((Decimal(cents) / 100).quantize(Decimal("0.01")))


def get_low_cash_threshold_cents(conn: sqlite3.Connection) -> int:
    """Return the low-cash warning threshold in cents.

    Reads the settings key 'low_cash_threshold_cents'. A missing or
    non-integer value falls back to DEFAULT_LOW_CASH_THRESHOLD_CENTS.
    """
    raw = database.get_setting(conn, LOW_CASH_THRESHOLD_SETTING)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LOW_CASH_THRESHOLD_CENTS


def _overdue_priority(overdue_days: int, amount_cents: int) -> str:
    """Rank an overdue invoice by how late it is and how much it is worth."""
    if overdue_days >= CRITICAL_OVERDUE_DAYS:
        return "critical"
    if overdue_days >= HIGH_OVERDUE_DAYS or amount_cents >= HIGH_VALUE_INVOICE_CENTS:
        return "high"
    return "medium"


def collect_overdue_alerts(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Return one alert per unpaid invoice that is overdue.

    An invoice is overdue if its status is 'overdue' or its due_date is before
    today.
    """
    rows = conn.execute(
        """
        SELECT i.id, i.invoice_number, i.amount_cents, i.due_date, c.name AS client_name
          FROM invoices i
          JOIN clients c ON c.id = i.client_id
         WHERE i.paid_date IS NULL
           AND i.status != 'paid'
           AND (i.status = 'overdue' OR i.due_date < ?)
         ORDER BY i.due_date, i.id
        """,
        (today.isoformat(),),
    ).fetchall()

    alerts: list[dict] = []
    for row in rows:
        invoice_id = int(row["id"])
        number = row["invoice_number"]
        client = row["client_name"]
        cents = int(row["amount_cents"])
        due_iso = row["due_date"]
        overdue_days = max(0, (today - date.fromisoformat(due_iso)).days)
        priority = _overdue_priority(overdue_days, cents)
        amount = _cents_to_inr(cents)

        if priority == "critical":
            action = (
                f"Escalate: contact {client} today about invoice {number} "
                "and agree a payment date."
            )
        else:
            action = f"Follow up with {client} about invoice {number} today."

        alerts.append({
            "id": f"overdue_invoice_{invoice_id}",
            "title": "Invoice payment overdue",
            "description": (
                f"Invoice {number} for {client} of INR {amount:,.2f} is "
                f"{overdue_days} day(s) overdue."
            ),
            "category": "overdue_payment",
            "priority": priority,
            "amount": amount,
            "related_date": due_iso,
            "recommended_action": action,
            "related_invoice_id": invoice_id,
            "related_expense_id": None,
            "reason": f"Unpaid and due date {due_iso} is before today {today.isoformat()}.",
        })
    return alerts


def collect_pending_alert(conn: sqlite3.Connection, today: date) -> dict | None:
    """Return one summary alert for unpaid invoices not yet due, or None.

    Overdue invoices are left out here because they have their own alerts.
    """
    row = conn.execute(
        """
        SELECT COUNT(*), COALESCE(SUM(amount_cents), 0), MIN(due_date)
          FROM invoices
         WHERE paid_date IS NULL
           AND status = 'pending'
           AND due_date >= ?
        """,
        (today.isoformat(),),
    ).fetchone()

    count = int(row[0])
    if count == 0:
        return None

    total = _cents_to_inr(int(row[1]))
    earliest = row[2]
    days_until = (date.fromisoformat(earliest) - today).days
    priority = "medium" if days_until <= UPCOMING_HIGH_PRIORITY_DAYS else "low"

    return {
        "id": "pending_payments_summary",
        "title": "Payments awaiting collection",
        "description": (
            f"{count} unpaid invoice(s) worth INR {total:,.2f} are not yet due."
        ),
        "category": "pending_payment",
        "priority": priority,
        "amount": total,
        "related_date": earliest,
        "recommended_action": (
            "Monitor the due dates and follow up with clients whose invoices "
            "are approaching or past their due date."
        ),
        "related_invoice_id": None,
        "related_expense_id": None,
        "reason": "Unpaid invoices with a due date on or after today.",
    }


def collect_cashflow_alerts(
    conn: sqlite3.Connection, today: date, threshold_cents: int
) -> list[dict]:
    """Return at most one cash-flow alert from the 90-day forecast.

    A projected balance below zero gives a critical negative alert. Otherwise,
    a projected minimum below the threshold gives a high-priority low-cash
    alert. Never both.
    """
    forecast = build_cashflow_forecast(conn, FORECAST_HORIZON_DAYS, today)
    daily = forecast["daily_forecast"]
    if not daily:
        return []

    first_negative_date: str | None = None
    lowest_cents: int | None = None
    lowest_date = ""
    for entry in daily:
        balance_cents = round(entry["projected_balance"] * 100)
        if balance_cents < 0 and first_negative_date is None:
            first_negative_date = entry["date"]
        # Strict "<" keeps the first occurrence of the minimum.
        if lowest_cents is None or balance_cents < lowest_cents:
            lowest_cents = balance_cents
            lowest_date = entry["date"]

    if first_negative_date is not None:
        lowest = _cents_to_inr(lowest_cents)
        shortfall = _cents_to_inr(abs(lowest_cents))
        return [{
            "id": "negative_cash_flow",
            "title": "Negative cash balance projected",
            "description": (
                f"Projected cash balance falls below zero on {first_negative_date}. "
                f"Lowest projected balance is INR {lowest:,.2f}, a shortfall of "
                f"INR {shortfall:,.2f}."
            ),
            "category": "negative_cash_flow",
            "priority": "critical",
            "amount": shortfall,
            "related_date": first_negative_date,
            "recommended_action": (
                "Review upcoming expenses and follow up on pending or overdue "
                "payments before that date; consider delaying non-essential spending."
            ),
            "related_invoice_id": None,
            "related_expense_id": None,
            "reason": "The 90-day forecast has a projected balance below zero.",
        }]

    if lowest_cents < threshold_cents:
        lowest = _cents_to_inr(lowest_cents)
        threshold = _cents_to_inr(threshold_cents)
        return [{
            "id": "low_cash_flow",
            "title": "Low cash balance projected",
            "description": (
                f"Projected cash falls to INR {lowest:,.2f} on {lowest_date}, below "
                f"your warning threshold of INR {threshold:,.2f}."
            ),
            "category": "low_cash_flow",
            "priority": "high",
            "amount": lowest,
            "related_date": lowest_date,
            "recommended_action": (
                "Review upcoming expenses and follow up on pending payments "
                "to rebuild the buffer."
            ),
            "related_invoice_id": None,
            "related_expense_id": None,
            "reason": (
                "The 90-day forecast drops below the warning threshold of "
                f"INR {threshold:,.2f}."
            ),
        }]

    return []


def collect_upcoming_expense_alerts(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Return one alert per 'upcoming' expense scheduled from today over 90 days.

    Paid expenses and upcoming expenses dated before today are not included.
    """
    window_end = today + timedelta(days=FORECAST_HORIZON_DAYS - 1)
    rows = conn.execute(
        """
        SELECT id, title, amount_cents, expense_date FROM expenses
         WHERE status = 'upcoming'
           AND expense_date >= ? AND expense_date <= ?
         ORDER BY expense_date, id
        """,
        (today.isoformat(), window_end.isoformat()),
    ).fetchall()

    alerts: list[dict] = []
    for row in rows:
        expense_id = int(row["id"])
        title = row["title"]
        expense_date = row["expense_date"]
        amount = _cents_to_inr(int(row["amount_cents"]))
        days_away = (date.fromisoformat(expense_date) - today).days
        priority = "high" if days_away <= UPCOMING_HIGH_PRIORITY_DAYS else "medium"

        alerts.append({
            "id": f"upcoming_expense_{expense_id}",
            "title": f"Upcoming expense: {title}",
            "description": (
                f"{title} of INR {amount:,.2f} is scheduled for {expense_date}."
            ),
            "category": "upcoming_expense",
            "priority": priority,
            "amount": amount,
            "related_date": expense_date,
            "recommended_action": (
                f"Set aside INR {amount:,.2f} before {expense_date} so the payment is covered."
            ),
            "related_invoice_id": None,
            "related_expense_id": expense_id,
            "reason": "Expense is marked upcoming and scheduled after today.",
        })
    return alerts


def _expense_total_cents(conn: sqlite3.Connection, start: str, end: str) -> int:
    """Sum of all expenses dated between start and end (inclusive)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM expenses "
        "WHERE expense_date BETWEEN ? AND ?",
        (start, end),
    ).fetchone()
    return int(row[0])


def _expense_totals_by_category(
    conn: sqlite3.Connection, start: str, end: str
) -> dict[str, int]:
    """Expense totals in cents per category, for dates between start and end."""
    rows = conn.execute(
        """
        SELECT category, COALESCE(SUM(amount_cents), 0) AS total
          FROM expenses
         WHERE expense_date BETWEEN ? AND ?
         GROUP BY category
        """,
        (start, end),
    ).fetchall()
    return {row["category"]: int(row["total"]) for row in rows}


def _top_increase_category(
    current: dict[str, int], previous: dict[str, int]
) -> str | None:
    """Return the category with the largest positive rise, or None if none rose."""
    best: str | None = None
    best_diff = 0
    for category in sorted(set(current) | set(previous)):
        diff = current.get(category, 0) - previous.get(category, 0)
        if diff > best_diff:
            best, best_diff = category, diff
    return best


def collect_expense_trend_alerts(conn: sqlite3.Connection, today: date) -> list[dict]:
    """Return an alert if this month's expenses are well above last month's.

    Returns no alert when last month had no expenses, since a percentage
    cannot be worked out.
    """
    this_start, this_end = period_bounds("this_month", today)
    last_start, last_end = period_bounds("last_month", today)

    current_total = _expense_total_cents(conn, this_start, this_end)
    previous_total = _expense_total_cents(conn, last_start, last_end)
    if previous_total == 0:
        return []

    percent = (current_total - previous_total) * 100 / previous_total
    if percent < SIGNIFICANT_EXPENSE_INCREASE_PERCENT:
        return []

    top = _top_increase_category(
        _expense_totals_by_category(conn, this_start, this_end),
        _expense_totals_by_category(conn, last_start, last_end),
    )
    if top is not None:
        action = f"Review the categories with the largest increases: {top}."
    else:
        action = "Review this month's expense categories."

    current = _cents_to_inr(current_total)
    previous = _cents_to_inr(previous_total)
    return [{
        "id": "expense_trend_increase",
        "title": "Expenses rose this month",
        "description": (
            f"Expenses this month are INR {current:,.2f}, up {percent:.1f}% "
            f"from INR {previous:,.2f} last month."
        ),
        "category": "expense_trend",
        "priority": "medium",
        "amount": current,
        "related_date": this_start,
        "recommended_action": action,
        "related_invoice_id": None,
        "related_expense_id": None,
        "reason": (
            "Current-month expenses are at least "
            f"{SIGNIFICANT_EXPENSE_INCREASE_PERCENT}% higher than last month's total."
        ),
    }]


def priority_sort_key(alert: dict) -> tuple:
    """Sort by priority, then earliest related date, then id."""
    return (
        PRIORITY_RANK[alert["priority"]],
        alert["related_date"] or "9999-12-31",
        alert["id"],
    )


def build_action_centre(
    conn: sqlite3.Connection,
    today: date,
    priority: str | None = None,
    category: str | None = None,
) -> dict:
    """Gather, filter, sort and count every alert for the Action Centre.

    priority and category are exact-match filters; None means no filter. The
    summary counts come from the filtered list, so they match the returned
    alerts. Returns {"summary": {...}, "alerts": [...]}.
    """
    threshold_cents = get_low_cash_threshold_cents(conn)

    alerts: list[dict] = []
    alerts.extend(collect_overdue_alerts(conn, today))
    pending = collect_pending_alert(conn, today)
    if pending is not None:
        alerts.append(pending)
    alerts.extend(collect_cashflow_alerts(conn, today, threshold_cents))
    alerts.extend(collect_upcoming_expense_alerts(conn, today))
    alerts.extend(collect_expense_trend_alerts(conn, today))

    if priority is not None:
        alerts = [a for a in alerts if a["priority"] == priority]
    if category is not None:
        alerts = [a for a in alerts if a["category"] == category]

    alerts.sort(key=priority_sort_key)

    summary = {
        "total_alerts": len(alerts),
        "critical": sum(1 for a in alerts if a["priority"] == "critical"),
        "high": sum(1 for a in alerts if a["priority"] == "high"),
        "medium": sum(1 for a in alerts if a["priority"] == "medium"),
        "low": sum(1 for a in alerts if a["priority"] == "low"),
    }
    return {"summary": summary, "alerts": alerts}
