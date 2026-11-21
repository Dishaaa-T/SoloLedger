"""
Tests for the Financial Action Centre (GET /action-centre and its service).

Each test uses its own temporary database file, so the real sololedger.db is
never touched. The seeded sample rows are deleted first, so every number
checked here comes from rows the test inserts itself.

Service tests use a FIXED today (FIXED), so their results do not depend on the
real date. API tests use date.today(), with dates built from it. Amounts are
written in INR (for example 1000) and stored as integer cents.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import database
from main import app
from services.action_centre import build_action_centre

FIXED = date(2030, 1, 15)
TODAY = date.today()
TEST_CLIENT_NAME = "Client A"
TEST_CLIENT_EMAIL = "action-centre-test@example.com"


def rupees(amount: int) -> int:
    """Convert a whole-INR test amount to integer cents."""
    return amount * 100


HEALTHY_CASH_CENTS = rupees(100000)


def iso(offset: int, base: date = FIXED) -> str:
    """Return the ISO date `offset` days after `base` (default: FIXED)."""
    return (base + timedelta(days=offset)).isoformat()


def _execute(sql: str, params: tuple = ()) -> int:
    """Run one write statement against the test database, commit it, return lastrowid."""
    conn = database.get_connection()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def add_invoice(
    number: str,
    status: str,
    amount_cents: int,
    due_date: str,
    paid_date: str | None = None,
) -> int:
    """Insert one invoice for the test client and return its id.

    Issue date is 30 days before the due date.
    """
    issue_date = (date.fromisoformat(due_date) - timedelta(days=30)).isoformat()
    return _execute(
        """
        INSERT INTO invoices
            (client_id, invoice_number, description, amount_cents,
             status, issue_date, due_date, paid_date)
        VALUES ((SELECT id FROM clients WHERE email = ?), ?, 'Action centre test invoice',
                ?, ?, ?, ?, ?)
        """,
        (TEST_CLIENT_EMAIL, number, amount_cents, status, issue_date, due_date, paid_date),
    )


def add_expense(
    title: str,
    amount_cents: int,
    expense_date: str,
    status: str,
    category: str = "Other",
) -> int:
    """Insert one expense and return its id."""
    return _execute(
        """
        INSERT INTO expenses
            (title, description, amount_cents, category, expense_date, status)
        VALUES (?, '', ?, ?, ?, ?)
        """,
        (title, amount_cents, category, expense_date, status),
    )


def set_setting_value(key: str, value: str) -> None:
    """Write one settings row through the database helper."""
    conn = database.get_connection()
    try:
        database.set_setting(conn, key, value)
        conn.commit()
    finally:
        conn.close()


def set_cash_cents(cents: int) -> None:
    """Set the cash balance setting (in cents)."""
    set_setting_value("cash_balance_cents", str(cents))


def delete_cash_setting() -> None:
    """Remove the cash balance setting so it is missing."""
    _execute("DELETE FROM settings WHERE key = ?", ("cash_balance_cents",))


def stored_state() -> tuple:
    """Return (invoice count, expense count, stored cash setting) for no-write checks."""
    conn = database.get_connection()
    try:
        invoices = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        expenses = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        cash = database.get_setting(conn, "cash_balance_cents")
        return (invoices, expenses, cash)
    finally:
        conn.close()


def build(priority: str | None = None, category: str | None = None) -> dict:
    """Call the service directly against the test database, with FIXED as today."""
    conn = database.get_connection()
    try:
        return build_action_centre(conn, today=FIXED, priority=priority, category=category)
    finally:
        conn.close()


def alert_by_id(result: dict, alert_id: str) -> dict:
    """Return the single alert with this id."""
    matches = [a for a in result["alerts"] if a["id"] == alert_id]
    assert len(matches) == 1
    return matches[0]


def alerts_in_category(result: dict, category: str) -> list[dict]:
    """Return every alert in one category."""
    return [a for a in result["alerts"] if a["category"] == category]


def add_mixed_scenario() -> None:
    """One critical overdue invoice, one high upcoming expense, one medium pending summary."""
    add_invoice("INV-MIX-1", "overdue", rupees(1000), iso(-35))
    add_invoice("INV-MIX-2", "pending", rupees(20000), iso(5))
    add_expense("Hosting renewal", rupees(1200), iso(3), "upcoming")


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point the app at a temporary database BEFORE the app starts.
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fresh(client):
    """Empty invoices and expenses, one test client, and healthy cash (100000.00 INR)."""
    _execute("DELETE FROM invoices")
    _execute("DELETE FROM expenses")
    _execute(
        "INSERT INTO clients (name, email) VALUES (?, ?)",
        (TEST_CLIENT_NAME, TEST_CLIENT_EMAIL),
    )
    set_cash_cents(HEALTHY_CASH_CENTS)
    return client


# ---------------------------------------------------------------------------
# Service: overdue invoices
# ---------------------------------------------------------------------------


def test_service_overdue_alert_fields(fresh):
    invoice_id = add_invoice("INV-A", "overdue", rupees(1000), iso(-10))

    result = build()

    alert = alert_by_id(result, f"overdue_invoice_{invoice_id}")
    assert alert["category"] == "overdue_payment"
    assert alert["priority"] == "high"  # 10 days overdue, which is >= 7
    assert alert["amount"] == 1000.0
    assert alert["related_invoice_id"] == invoice_id
    assert alert["related_date"] == iso(-10)
    assert "INV-A" in alert["description"]
    assert "Client A" in alert["recommended_action"]
    assert "INV-A" in alert["recommended_action"]


def test_service_overdue_critical_at_35_days(fresh):
    invoice_id = add_invoice("INV-C", "overdue", rupees(1000), iso(-35))

    alert = alert_by_id(build(), f"overdue_invoice_{invoice_id}")

    assert alert["priority"] == "critical"
    assert alert["recommended_action"].startswith("Escalate")


def test_service_overdue_medium_two_days_small_amount(fresh):
    invoice_id = add_invoice("INV-M", "overdue", rupees(1000), iso(-2))

    alert = alert_by_id(build(), f"overdue_invoice_{invoice_id}")

    assert alert["priority"] == "medium"


def test_service_overdue_high_by_value_two_days(fresh):
    invoice_id = add_invoice("INV-V", "overdue", rupees(60000), iso(-2))

    alert = alert_by_id(build(), f"overdue_invoice_{invoice_id}")

    assert alert["priority"] == "high"


def test_service_paid_past_due_invoice_is_not_overdue(fresh):
    add_invoice("INV-PAID", "paid", rupees(1000), iso(-5), paid_date=iso(-1))

    result = build()

    assert alerts_in_category(result, "overdue_payment") == []


# ---------------------------------------------------------------------------
# Service: pending payments summary
# ---------------------------------------------------------------------------


def test_service_pending_summary_medium_when_due_within_seven_days(fresh):
    add_invoice("INV-P1", "pending", rupees(20000), iso(5))
    add_invoice("INV-P2", "pending", rupees(30000), iso(40))

    alert = alert_by_id(build(), "pending_payments_summary")

    assert alert["category"] == "pending_payment"
    assert alert["priority"] == "medium"
    assert alert["amount"] == 50000.0
    assert "2 unpaid" in alert["description"]


def test_service_pending_summary_low_when_due_later(fresh):
    add_invoice("INV-P3", "pending", rupees(30000), iso(40))

    alert = alert_by_id(build(), "pending_payments_summary")

    assert alert["priority"] == "low"


def test_service_overdue_invoice_not_counted_in_pending_summary(fresh):
    add_invoice("INV-OD", "overdue", rupees(1000), iso(-10))

    result = build()

    ids = [a["id"] for a in result["alerts"]]
    assert "pending_payments_summary" not in ids


# ---------------------------------------------------------------------------
# Service: cash-flow alerts
# ---------------------------------------------------------------------------


def test_service_negative_cash_flow_is_critical(fresh):
    set_cash_cents(rupees(1000))
    add_expense("Rent", rupees(5000), iso(2), "upcoming")

    result = build()

    alert = alert_by_id(result, "negative_cash_flow")
    assert alert["category"] == "negative_cash_flow"
    assert alert["priority"] == "critical"
    assert alert["amount"] == 4000.0
    assert alert["related_date"] == iso(2)
    assert len(alerts_in_category(result, "negative_cash_flow")) == 1
    assert alerts_in_category(result, "low_cash_flow") == []


def test_service_low_cash_flow_is_high(fresh):
    set_cash_cents(rupees(8000))
    add_expense("Rent", rupees(4000), iso(3), "upcoming")

    result = build()

    alert = alert_by_id(result, "low_cash_flow")
    assert alert["category"] == "low_cash_flow"
    assert alert["priority"] == "high"
    assert alert["amount"] == 4000.0
    assert alert["related_date"] == iso(3)
    assert alerts_in_category(result, "negative_cash_flow") == []


def test_service_custom_low_cash_threshold_is_respected(fresh):
    set_setting_value("low_cash_threshold_cents", "100000")  # 1000.00
    set_cash_cents(rupees(8000))
    add_expense("Rent", rupees(4000), iso(3), "upcoming")

    result = build()

    assert alerts_in_category(result, "low_cash_flow") == []


def test_service_healthy_cash_has_no_cash_alerts(fresh):
    set_cash_cents(rupees(100000))

    result = build()

    assert alerts_in_category(result, "negative_cash_flow") == []
    assert alerts_in_category(result, "low_cash_flow") == []


# ---------------------------------------------------------------------------
# Service: upcoming expenses
# ---------------------------------------------------------------------------


def test_service_upcoming_expense_high_within_seven_days(fresh):
    expense_id = add_expense("Hosting renewal", rupees(1200), iso(3), "upcoming")

    alert = alert_by_id(build(), f"upcoming_expense_{expense_id}")

    assert alert["category"] == "upcoming_expense"
    assert alert["priority"] == "high"
    assert alert["related_expense_id"] == expense_id
    assert alert["amount"] == 1200.0


def test_service_upcoming_expense_medium_later(fresh):
    expense_id = add_expense("Hosting renewal", rupees(1200), iso(20), "upcoming")

    alert = alert_by_id(build(), f"upcoming_expense_{expense_id}")

    assert alert["priority"] == "medium"


def test_service_paid_or_past_expenses_are_not_upcoming(fresh):
    add_expense("Paid bill", rupees(1200), iso(3), "paid")
    add_expense("Old bill", rupees(1200), iso(-3), "upcoming")

    result = build()

    assert alerts_in_category(result, "upcoming_expense") == []


# ---------------------------------------------------------------------------
# Service: expense trend
# ---------------------------------------------------------------------------


def test_service_expense_trend_alert_names_largest_increase(fresh):
    add_expense("Flight", rupees(1000), "2029-12-10", "paid", "Travel")
    add_expense("Design tool", rupees(9000), "2029-12-10", "paid", "Software")
    add_expense("Conference", rupees(9000), "2030-01-10", "paid", "Travel")
    add_expense("Design tool", rupees(6000), "2030-01-10", "paid", "Software")

    result = build()

    alert = alert_by_id(result, "expense_trend_increase")
    assert alert["category"] == "expense_trend"
    assert alert["priority"] == "medium"
    assert alert["amount"] == 15000.0
    assert "50.0%" in alert["description"]
    assert "Travel" in alert["recommended_action"]


def test_service_expense_trend_zero_base_gives_no_alert(fresh):
    add_expense("Conference", rupees(15000), "2030-01-10", "paid", "Travel")

    result = build()

    assert alerts_in_category(result, "expense_trend") == []


def test_service_expense_trend_below_twenty_percent_gives_no_alert(fresh):
    add_expense("Design tool", rupees(10000), "2029-12-10", "paid", "Software")
    add_expense("Design tool", rupees(11000), "2030-01-10", "paid", "Software")

    result = build()

    assert alerts_in_category(result, "expense_trend") == []


# ---------------------------------------------------------------------------
# Service: empty data, missing settings, sorting, filters
# ---------------------------------------------------------------------------


def test_service_empty_database_has_no_alerts(fresh):
    set_cash_cents(rupees(10000))

    result = build()

    assert result == {
        "summary": {"total_alerts": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
        "alerts": [],
    }


def test_service_missing_cash_setting_does_not_raise(fresh):
    delete_cash_setting()

    result = build()

    assert isinstance(result, dict)
    assert result["summary"]["total_alerts"] == len(result["alerts"])
    # A missing balance counts as 0, which is below the default threshold.
    assert alert_by_id(result, "low_cash_flow")["priority"] == "high"


def test_service_alerts_sorted_by_priority_rank(fresh):
    add_mixed_scenario()

    result = build()

    priorities = [a["priority"] for a in result["alerts"]]
    assert priorities == ["critical", "high", "medium"]
    assert result["summary"] == {
        "total_alerts": 3, "critical": 1, "high": 1, "medium": 1, "low": 0,
    }


def test_service_priority_filter_returns_only_that_priority(fresh):
    add_mixed_scenario()

    result = build(priority="critical")

    assert len(result["alerts"]) == 1
    assert all(a["priority"] == "critical" for a in result["alerts"])
    assert result["summary"]["total_alerts"] == 1
    assert result["summary"]["critical"] == 1


def test_service_category_filter_returns_only_that_category(fresh):
    add_mixed_scenario()

    result = build(category="upcoming_expense")

    assert len(result["alerts"]) == 1
    assert all(a["category"] == "upcoming_expense" for a in result["alerts"])
    assert result["summary"]["total_alerts"] == 1


def test_service_low_priority_filter_with_no_low_alerts_is_empty(fresh):
    add_mixed_scenario()

    result = build(priority="low")

    assert result["alerts"] == []
    assert result["summary"] == {
        "total_alerts": 0, "critical": 0, "high": 0, "medium": 0, "low": 0,
    }


def test_service_identical_calls_return_equal_results(fresh):
    add_mixed_scenario()

    assert build() == build()


def test_service_build_writes_nothing(fresh):
    add_mixed_scenario()
    before = stored_state()

    build()

    assert stored_state() == before


# ---------------------------------------------------------------------------
# API: GET /action-centre
# ---------------------------------------------------------------------------


def add_api_scenario() -> None:
    """Overdue invoice 35 days before today (critical), upcoming expense 3 days ahead (high)."""
    add_invoice("INV-API", "overdue", rupees(1000), iso(-35, TODAY))
    add_expense("Hosting renewal", rupees(1200), iso(3, TODAY), "upcoming")


def test_api_no_params_returns_summary_and_alerts(fresh):
    response = fresh.get("/action-centre")

    assert response.status_code == 200
    body = response.json()
    assert set(body["summary"]) >= {"total_alerts", "critical", "high", "medium", "low"}
    assert body["summary"]["total_alerts"] == len(body["alerts"])


def test_api_priority_filter_critical(fresh):
    add_api_scenario()

    response = fresh.get("/action-centre", params={"priority": "critical"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["alerts"]) == 1
    assert all(a["priority"] == "critical" for a in body["alerts"])
    assert body["summary"]["total_alerts"] == len(body["alerts"])


def test_api_category_filter_overdue_payment(fresh):
    add_api_scenario()

    response = fresh.get("/action-centre", params={"category": "overdue_payment"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["alerts"]) == 1
    assert all(a["category"] == "overdue_payment" for a in body["alerts"])


def test_api_invalid_priority_is_422(fresh):
    assert fresh.get("/action-centre", params={"priority": "urgent"}).status_code == 422


def test_api_invalid_category_is_422(fresh):
    assert fresh.get("/action-centre", params={"category": "unknown"}).status_code == 422


def test_api_existing_endpoints_still_respond(fresh):
    assert fresh.get("/forecast/cashflow").status_code == 200
    assert fresh.get("/dashboard/summary").status_code == 200
    assert fresh.get("/clients").status_code == 200
