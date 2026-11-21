"""
Tests for the financial dashboard summary.

Each test uses its own temporary database file, so the real sololedger.db is
never touched. The seeded sample rows are deleted first, so every number
checked here comes from rows the test inserts itself.

Test amounts are written in INR (for example 45000) and stored as cents
(4500000), the same way the API stores them.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import database
from main import app
from services.dashboard import period_bounds

TODAY = date.today()
THIS_MONTH_FIRST = TODAY.replace(day=1)
# Any day in the previous month: the first day of the month before this one.
LAST_MONTH_FIRST = (THIS_MONTH_FIRST - timedelta(days=1)).replace(day=1)
TEST_CLIENT_EMAIL = "dashboard-test@example.com"


def rupees(amount: int) -> int:
    """Convert a whole-INR test amount to integer cents."""
    return amount * 100


def _execute(sql: str, params: tuple = ()) -> None:
    """Run one write statement against the test database and commit it."""
    conn = database.get_connection()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def insert_invoice(
    status: str,
    amount_cents: int,
    due_date: str,
    paid_date: str | None,
    issue_date: str,
    number: str,
) -> None:
    """Insert one invoice for the test client, using the given dates and status."""
    _execute(
        """
        INSERT INTO invoices
            (client_id, invoice_number, description, amount_cents,
             status, issue_date, due_date, paid_date)
        VALUES ((SELECT id FROM clients WHERE email = ?), ?, 'Test invoice',
                ?, ?, ?, ?, ?)
        """,
        (TEST_CLIENT_EMAIL, number, amount_cents, status, issue_date, due_date, paid_date),
    )


def insert_expense(amount_cents: int, expense_date: str) -> None:
    """Insert one expense with the given amount and date."""
    _execute(
        """
        INSERT INTO expenses
            (title, description, amount_cents, category, expense_date, status)
        VALUES ('Test expense', '', ?, 'Other', ?, 'paid')
        """,
        (amount_cents, expense_date),
    )


def set_cash_cents(cents: int) -> None:
    """Set the cash balance setting (in cents) through the database helper."""
    conn = database.get_connection()
    try:
        database.set_setting(conn, "cash_balance_cents", str(cents))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point the app at a temporary database BEFORE the app starts.
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fresh(client):
    """Empty invoices and expenses, then add one test client to link them to."""
    _execute("DELETE FROM invoices")
    _execute("DELETE FROM expenses")
    _execute(
        "INSERT INTO clients (name, email) VALUES (?, ?)",
        ("Dashboard Test Client", TEST_CLIENT_EMAIL),
    )
    return client


def summary(client, period: str | None = None) -> dict:
    """Call GET /dashboard/summary and return the JSON body (must be 200)."""
    params = {} if period is None else {"period": period}
    response = client.get("/dashboard/summary", params=params)
    assert response.status_code == 200
    return response.json()


# ---------------------------------------------------------------------------
# Period boundaries (pure function, no database)
# ---------------------------------------------------------------------------


def test_period_bounds_this_and_last_month():
    assert period_bounds("this_month", date(2026, 2, 10)) == ("2026-02-01", "2026-02-28")
    assert period_bounds("last_month", date(2026, 2, 10)) == ("2026-01-01", "2026-01-31")


def test_period_bounds_january_goes_back_to_december():
    assert period_bounds("last_month", date(2026, 1, 15)) == ("2025-12-01", "2025-12-31")


def test_period_bounds_leap_year_february():
    assert period_bounds("this_month", date(2028, 2, 5)) == ("2028-02-01", "2028-02-29")


def test_period_bounds_all_time_has_no_limits():
    assert period_bounds("all_time", date(2026, 2, 10)) == (None, None)


# ---------------------------------------------------------------------------
# Empty database and basic metrics
# ---------------------------------------------------------------------------


def test_empty_database_returns_zeros(fresh):
    _execute("DELETE FROM settings WHERE key = 'cash_balance_cents'")
    data = summary(fresh)
    assert data == {
        "period": "this_month",
        "currency": "INR",
        "total_income": 0.0,
        "total_expenses": 0.0,
        "net_profit": 0.0,
        "pending_payments": 0.0,
        "overdue_payments": 0.0,
        "available_cash": 0.0,
    }


def test_paid_invoice_this_month_is_income(fresh):
    insert_invoice(
        "paid", rupees(45000), due_date=TODAY.isoformat(),
        paid_date=THIS_MONTH_FIRST.isoformat(), issue_date=LAST_MONTH_FIRST.isoformat(),
        number="INV-DASH-1",
    )
    data = summary(fresh, "this_month")
    assert data["total_income"] == 45000.0
    assert data["period"] == "this_month"


def test_paid_invoice_last_month_is_in_last_month_and_all_time_only(fresh):
    insert_invoice(
        "paid", rupees(10000), due_date=LAST_MONTH_FIRST.isoformat(),
        paid_date=LAST_MONTH_FIRST.isoformat(), issue_date=LAST_MONTH_FIRST.isoformat(),
        number="INV-DASH-2",
    )
    assert summary(fresh, "this_month")["total_income"] == 0.0
    assert summary(fresh, "last_month")["total_income"] == 10000.0
    assert summary(fresh, "all_time")["total_income"] == 10000.0


def test_pending_and_overdue_invoices_are_not_income(fresh):
    insert_invoice(
        "pending", rupees(18000), due_date=(TODAY + timedelta(days=30)).isoformat(),
        paid_date=None, issue_date=(TODAY - timedelta(days=5)).isoformat(),
        number="INV-DASH-3",
    )
    insert_invoice(
        "overdue", rupees(5000), due_date=(TODAY - timedelta(days=10)).isoformat(),
        paid_date=None, issue_date=(TODAY - timedelta(days=40)).isoformat(),
        number="INV-DASH-4",
    )
    for period in ("this_month", "last_month", "all_time"):
        data = summary(fresh, period)
        assert data["total_income"] == 0.0
        assert data["pending_payments"] == 23000.0
        assert data["overdue_payments"] == 5000.0


def test_pending_invoice_past_due_counts_as_overdue(fresh):
    insert_invoice(
        "pending", rupees(7000), due_date=(TODAY - timedelta(days=10)).isoformat(),
        paid_date=None, issue_date=(TODAY - timedelta(days=40)).isoformat(),
        number="INV-DASH-5",
    )
    data = summary(fresh)
    assert data["pending_payments"] == 7000.0
    assert data["overdue_payments"] == 7000.0


def test_paid_invoice_with_past_due_date_is_not_overdue(fresh):
    insert_invoice(
        "paid", rupees(9000), due_date=(TODAY - timedelta(days=10)).isoformat(),
        paid_date=THIS_MONTH_FIRST.isoformat(),
        issue_date=(TODAY - timedelta(days=40)).isoformat(),
        number="INV-DASH-6",
    )
    data = summary(fresh)
    assert data["total_income"] == 9000.0
    assert data["pending_payments"] == 0.0
    assert data["overdue_payments"] == 0.0


def test_expenses_are_filtered_by_period(fresh):
    insert_expense(rupees(12000), THIS_MONTH_FIRST.isoformat())
    insert_expense(rupees(3000), LAST_MONTH_FIRST.isoformat())
    assert summary(fresh, "this_month")["total_expenses"] == 12000.0
    assert summary(fresh, "last_month")["total_expenses"] == 3000.0


def test_net_profit_can_be_negative(fresh):
    insert_invoice(
        "paid", rupees(45000), due_date=TODAY.isoformat(),
        paid_date=THIS_MONTH_FIRST.isoformat(), issue_date=LAST_MONTH_FIRST.isoformat(),
        number="INV-DASH-7",
    )
    insert_expense(rupees(60000), THIS_MONTH_FIRST.isoformat())
    data = summary(fresh, "this_month")
    assert data["total_income"] == 45000.0
    assert data["total_expenses"] == 60000.0
    assert data["net_profit"] == -15000.0


def test_available_cash_comes_from_settings(fresh):
    set_cash_cents(6500000)
    assert summary(fresh)["available_cash"] == 65000.0


def test_changing_cash_does_not_change_other_metrics(fresh):
    insert_invoice(
        "paid", rupees(45000), due_date=TODAY.isoformat(),
        paid_date=THIS_MONTH_FIRST.isoformat(), issue_date=LAST_MONTH_FIRST.isoformat(),
        number="INV-DASH-8",
    )
    insert_expense(rupees(12000), THIS_MONTH_FIRST.isoformat())
    set_cash_cents(6500000)
    before = summary(fresh, "this_month")

    set_cash_cents(1000000)
    after = summary(fresh, "this_month")

    assert after["available_cash"] == 10000.0
    for key in ("total_income", "total_expenses", "net_profit",
                "pending_payments", "overdue_payments"):
        assert after[key] == before[key]


def test_adding_pending_invoice_does_not_change_income(fresh):
    before = summary(fresh, "this_month")
    insert_invoice(
        "pending", rupees(18000), due_date=(TODAY + timedelta(days=30)).isoformat(),
        paid_date=None, issue_date=(TODAY - timedelta(days=5)).isoformat(),
        number="INV-DASH-9",
    )
    after = summary(fresh, "this_month")
    assert after["total_income"] == before["total_income"]
    assert after["pending_payments"] == 18000.0


def test_adding_expense_changes_only_expenses_and_net_profit(fresh):
    before = summary(fresh, "this_month")
    insert_expense(rupees(500), THIS_MONTH_FIRST.isoformat())
    after = summary(fresh, "this_month")
    assert after["total_expenses"] == 500.0
    assert after["net_profit"] == -500.0
    for key in ("total_income", "pending_payments", "overdue_payments", "available_cash"):
        assert after[key] == before[key]


def test_no_double_counting(fresh):
    insert_invoice(
        "paid", rupees(45000), due_date=TODAY.isoformat(),
        paid_date=THIS_MONTH_FIRST.isoformat(), issue_date=LAST_MONTH_FIRST.isoformat(),
        number="INV-DASH-10",
    )
    insert_expense(rupees(12000), THIS_MONTH_FIRST.isoformat())
    data = summary(fresh, "this_month")
    assert data["total_income"] == 45000.0
    assert data["total_expenses"] == 12000.0
    assert data["net_profit"] == 33000.0
    assert data["pending_payments"] == 0.0
    assert data["overdue_payments"] == 0.0


def test_all_time_includes_both_months(fresh):
    insert_invoice(
        "paid", rupees(45000), due_date=TODAY.isoformat(),
        paid_date=THIS_MONTH_FIRST.isoformat(), issue_date=LAST_MONTH_FIRST.isoformat(),
        number="INV-DASH-11",
    )
    insert_invoice(
        "paid", rupees(10000), due_date=LAST_MONTH_FIRST.isoformat(),
        paid_date=LAST_MONTH_FIRST.isoformat(), issue_date=LAST_MONTH_FIRST.isoformat(),
        number="INV-DASH-12",
    )
    insert_expense(rupees(12000), THIS_MONTH_FIRST.isoformat())
    insert_expense(rupees(3000), LAST_MONTH_FIRST.isoformat())
    data = summary(fresh, "all_time")
    assert data["total_income"] == 55000.0
    assert data["total_expenses"] == 15000.0
    assert data["net_profit"] == 40000.0


# ---------------------------------------------------------------------------
# HTTP behaviour
# ---------------------------------------------------------------------------


def test_unknown_period_is_422(client):
    response = client.get("/dashboard/summary", params={"period": "next_year"})
    assert response.status_code == 422


def test_clients_endpoint_still_responds(client):
    assert client.get("/clients").status_code == 200
