"""
Tests for the cash-flow forecast (30, 60 or 90 days).

Each test uses its own temporary database file, so the real sololedger.db is
never touched. The seeded sample rows are deleted first, so every number
checked here comes from rows the test inserts itself.

API tests use date.today(). Arithmetic tests call the service with a FIXED
today (FIXED_TODAY), so their results do not depend on the real date.
Test amounts are written in INR (for example 18000) and stored as cents.
"""

import itertools
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import database
from main import app
from services.forecast import build_cashflow_forecast

TODAY = date.today()
FIXED_TODAY = date(2030, 1, 1)
TEST_CLIENT_EMAIL = "forecast-test@example.com"
_invoice_numbers = (f"INV-FC-{n}" for n in itertools.count(1))


def rupees(amount: int) -> int:
    """Convert a whole-INR test amount to integer cents."""
    return amount * 100


def day(offset: int, base: date = TODAY) -> str:
    """Return the ISO date `offset` days after `base` (default: today)."""
    return (base + timedelta(days=offset)).isoformat()


def _execute(sql: str, params: tuple = ()) -> None:
    """Run one write statement against the test database and commit it."""
    conn = database.get_connection()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def add_invoice(
    status: str,
    amount_cents: int,
    due_date: str,
    paid_date: str | None = None,
    issue_date: str | None = None,
) -> None:
    """Insert one invoice for the test client. Issue date defaults to 30 days before due."""
    if issue_date is None:
        issue_date = (date.fromisoformat(due_date) - timedelta(days=30)).isoformat()
    _execute(
        """
        INSERT INTO invoices
            (client_id, invoice_number, description, amount_cents,
             status, issue_date, due_date, paid_date)
        VALUES ((SELECT id FROM clients WHERE email = ?), ?, 'Forecast test invoice',
                ?, ?, ?, ?, ?)
        """,
        (TEST_CLIENT_EMAIL, next(_invoice_numbers), amount_cents, status,
         issue_date, due_date, paid_date),
    )


def add_expense(amount_cents: int, expense_date: str, status: str = "upcoming") -> None:
    """Insert one expense with the given amount, date and status."""
    _execute(
        """
        INSERT INTO expenses
            (title, description, amount_cents, category, expense_date, status)
        VALUES ('Forecast test expense', '', ?, 'Other', ?, ?)
        """,
        (amount_cents, expense_date, status),
    )


def set_cash_cents(cents: int) -> None:
    """Set the cash balance setting (in cents) through the database helper."""
    conn = database.get_connection()
    try:
        database.set_setting(conn, "cash_balance_cents", str(cents))
        conn.commit()
    finally:
        conn.close()


def forecast_fixed(days: int) -> dict:
    """Run the service with the fixed test date against the test database."""
    conn = database.get_connection()
    try:
        return build_cashflow_forecast(conn, days, FIXED_TODAY)
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
    """Empty invoices and expenses, then one test client, and cash set to 0."""
    _execute("DELETE FROM invoices")
    _execute("DELETE FROM expenses")
    _execute(
        "INSERT INTO clients (name, email) VALUES (?, ?)",
        ("Forecast Test Client", TEST_CLIENT_EMAIL),
    )
    set_cash_cents(0)
    return client


def forecast(client, days: int | None = None) -> dict:
    """Call GET /forecast/cashflow and return the JSON body (must be 200)."""
    params = {} if days is None else {"days": days}
    response = client.get("/forecast/cashflow", params=params)
    assert response.status_code == 200
    return response.json()


def daily_on(data: dict, iso: str) -> dict:
    """Return the daily_forecast entry for one ISO date."""
    matches = [entry for entry in data["daily_forecast"] if entry["date"] == iso]
    assert len(matches) == 1
    return matches[0]


# ---------------------------------------------------------------------------
# Income rules
# ---------------------------------------------------------------------------


def test_pending_invoice_is_collected_on_due_date(fresh):
    set_cash_cents(rupees(65000))
    add_invoice("pending", rupees(18000), due_date=day(10), issue_date=day(-5))
    data = forecast(fresh, 30)
    assert data["expected_income"] == 18000.0
    assert data["lowest_projected_balance"] == 65000.0
    assert data["lowest_balance_date"] == day(0)
    assert data["projected_closing_balance"] == 83000.0
    assert daily_on(data, day(10))["expected_income"] == 18000.0
    assert daily_on(data, day(9))["expected_income"] == 0.0


def test_overdue_invoice_is_collected_seven_days_from_today(fresh):
    add_invoice("overdue", rupees(5000), due_date=day(-5), issue_date=day(-40))
    data = forecast(fresh, 30)
    assert daily_on(data, day(7))["expected_income"] == 5000.0
    assert daily_on(data, day(0))["expected_income"] == 0.0


def test_pending_invoice_past_due_is_treated_as_overdue(fresh):
    add_invoice("pending", rupees(5000), due_date=day(-3), issue_date=day(-33))
    data = forecast(fresh, 30)
    assert daily_on(data, day(7))["expected_income"] == 5000.0
    assert daily_on(data, day(0))["expected_income"] == 0.0


def test_paid_invoice_is_never_counted(fresh):
    add_invoice("paid", rupees(30000), due_date=day(5), paid_date=day(-1))
    data = forecast(fresh, 30)
    assert data["expected_income"] == 0.0
    assert all(entry["expected_income"] == 0.0 for entry in data["daily_forecast"])


def test_two_invoices_due_same_day_are_summed(fresh):
    add_invoice("pending", rupees(4000), due_date=day(3), issue_date=day(-20))
    add_invoice("pending", rupees(6000), due_date=day(3), issue_date=day(-10))
    data = forecast(fresh, 30)
    assert daily_on(data, day(3))["expected_income"] == 10000.0
    assert data["expected_income"] == 10000.0


# ---------------------------------------------------------------------------
# Expense rules
# ---------------------------------------------------------------------------


def test_upcoming_expense_reduces_balance_on_its_day(fresh):
    set_cash_cents(rupees(50000))
    add_expense(rupees(12000), day(5))
    data = forecast(fresh, 30)
    assert data["expected_expenses"] == 12000.0
    assert daily_on(data, day(4))["projected_balance"] == 50000.0
    assert daily_on(data, day(5))["expected_expenses"] == 12000.0
    assert daily_on(data, day(5))["projected_balance"] == 38000.0


def test_paid_expense_is_not_counted(fresh):
    add_expense(rupees(12000), day(5), status="paid")
    data = forecast(fresh, 30)
    assert data["expected_expenses"] == 0.0


def test_upcoming_expense_dated_yesterday_is_not_counted(fresh):
    add_expense(rupees(12000), day(-1), status="upcoming")
    data = forecast(fresh, 30)
    assert data["expected_expenses"] == 0.0
    assert data["projected_closing_balance"] == 0.0


# ---------------------------------------------------------------------------
# Window length (30, 60, 90)
# ---------------------------------------------------------------------------


def test_invoice_due_in_45_days_counts_only_in_60_and_90_day_windows(fresh):
    add_invoice("pending", rupees(10000), due_date=day(45), issue_date=day(10))
    assert forecast(fresh, 30)["expected_income"] == 0.0
    assert forecast(fresh, 60)["expected_income"] == 10000.0
    assert forecast(fresh, 90)["expected_income"] == 10000.0


@pytest.mark.parametrize("days", [30, 60, 90])
def test_daily_forecast_length_matches_window(fresh, days):
    data = forecast(fresh, days)
    assert len(data["daily_forecast"]) == days
    assert data["forecast_days"] == days
    assert data["daily_forecast"][0]["date"] == day(0)
    assert data["daily_forecast"][-1]["date"] == day(days - 1)


# ---------------------------------------------------------------------------
# Balance metrics
# ---------------------------------------------------------------------------


def test_negative_balance_is_detected(fresh):
    set_cash_cents(rupees(1000))
    add_expense(rupees(5000), day(2))
    data = forecast(fresh, 30)
    assert data["risk_of_negative_balance"] is True
    assert data["lowest_projected_balance"] == -4000.0
    assert data["lowest_balance_date"] == day(2)


def test_lowest_balance_date_is_first_occurrence_on_tie(fresh):
    set_cash_cents(rupees(10000))
    add_expense(rupees(3000), day(2))   # balance 7000 from day 2
    add_invoice("pending", rupees(3000), due_date=day(4), issue_date=day(-10))  # 10000
    add_expense(rupees(3000), day(6))   # balance 7000 again on day 6
    data = forecast(fresh, 30)
    assert data["lowest_projected_balance"] == 7000.0
    assert data["lowest_balance_date"] == day(2)
    assert data["risk_of_negative_balance"] is False


def test_empty_database_gives_zeros_and_flat_balance(fresh):
    set_cash_cents(rupees(65000))
    data = forecast(fresh, 30)
    assert data["expected_income"] == 0.0
    assert data["expected_expenses"] == 0.0
    assert data["starting_balance"] == 65000.0
    assert data["projected_closing_balance"] == 65000.0
    assert data["lowest_projected_balance"] == 65000.0
    assert data["risk_of_negative_balance"] is False
    assert len(data["daily_forecast"]) == 30


def test_missing_cash_setting_gives_zero_start(fresh):
    _execute("DELETE FROM settings WHERE key = 'cash_balance_cents'")
    data = forecast(fresh, 30)
    assert data["starting_balance"] == 0.0
    assert data["currency"] == "INR"


# ---------------------------------------------------------------------------
# Service-level checks with a fixed "today"
# ---------------------------------------------------------------------------


def test_fixed_today_pending_collection_arithmetic(fresh):
    set_cash_cents(rupees(65000))
    add_invoice("pending", rupees(18000),
                due_date=day(10, FIXED_TODAY), issue_date=day(-5, FIXED_TODAY))
    data = forecast_fixed(30)
    assert data["starting_balance"] == 65000.0
    assert data["expected_income"] == 18000.0
    assert data["projected_closing_balance"] == 83000.0
    assert data["daily_forecast"][0]["date"] == "2030-01-01"


def test_fixed_today_is_deterministic(fresh):
    set_cash_cents(rupees(20000))
    add_invoice("overdue", rupees(5000),
                due_date=day(-5, FIXED_TODAY), issue_date=day(-40, FIXED_TODAY))
    add_expense(rupees(2500), day(3, FIXED_TODAY))
    assert forecast_fixed(60) == forecast_fixed(60)


def test_invalid_days_raise_value_error(fresh):
    with pytest.raises(ValueError):
        forecast_fixed(45)


# ---------------------------------------------------------------------------
# HTTP behaviour
# ---------------------------------------------------------------------------


def test_default_window_is_30_days(fresh):
    data = forecast(fresh)
    assert data["forecast_days"] == 30
    assert len(data["daily_forecast"]) == 30


@pytest.mark.parametrize("days", [30, 60, 90])
def test_allowed_windows_return_200(fresh, days):
    assert fresh.get("/forecast/cashflow", params={"days": days}).status_code == 200


def test_unsupported_days_value_is_422(fresh):
    assert fresh.get("/forecast/cashflow", params={"days": 45}).status_code == 422


def test_non_numeric_days_is_422(fresh):
    assert fresh.get("/forecast/cashflow", params={"days": "abc"}).status_code == 422


def test_dashboard_and_clients_still_respond(fresh):
    assert fresh.get("/dashboard/summary").status_code == 200
    assert fresh.get("/clients").status_code == 200
