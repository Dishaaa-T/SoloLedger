"""
Tests for the what-if financial simulator (POST /simulator/what-if).

Each test uses its own temporary database file, so the real sololedger.db is
never touched. The seeded sample rows are deleted first, so every number
checked here comes from rows the test inserts itself.

Service tests use a FIXED today (FIXED_TODAY), so their results do not depend
on the real date. API tests use date.today(). Amounts are written in INR
(for example 18000) and stored as cents.
"""

import itertools
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import database
from main import app
from services.simulator import SimulationError, run_what_if

TODAY = date.today()
FIXED_TODAY = date(2030, 1, 1)
TEST_CLIENT_EMAIL = "simulator-test@example.com"
_invoice_numbers = (f"INV-SIM-{n}" for n in itertools.count(1))


def rupees(amount: int) -> int:
    """Convert a whole-INR test amount to integer cents."""
    return amount * 100


def day(offset: int, base: date = TODAY) -> str:
    """Return the ISO date `offset` days after `base` (default: today)."""
    return (base + timedelta(days=offset)).isoformat()


def fdate(offset: int) -> date:
    """Return the date object `offset` days after FIXED_TODAY."""
    return FIXED_TODAY + timedelta(days=offset)


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
    status: str,
    amount_cents: int,
    due_date: str,
    paid_date: str | None = None,
    issue_date: str | None = None,
) -> int:
    """Insert one invoice for the test client and return its id.

    Issue date defaults to 30 days before the due date.
    """
    if issue_date is None:
        issue_date = (date.fromisoformat(due_date) - timedelta(days=30)).isoformat()
    return _execute(
        """
        INSERT INTO invoices
            (client_id, invoice_number, description, amount_cents,
             status, issue_date, due_date, paid_date)
        VALUES ((SELECT id FROM clients WHERE email = ?), ?, 'Simulator test invoice',
                ?, ?, ?, ?, ?)
        """,
        (TEST_CLIENT_EMAIL, next(_invoice_numbers), amount_cents, status,
         issue_date, due_date, paid_date),
    )


def add_expense(amount_cents: int, expense_date: str, status: str = "upcoming") -> int:
    """Insert one expense and return its id."""
    return _execute(
        """
        INSERT INTO expenses
            (title, description, amount_cents, category, expense_date, status)
        VALUES ('Simulator test expense', '', ?, 'Other', ?, ?)
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


def invoice_row(invoice_id: int) -> tuple:
    """Return (status, due_date, paid_date) for one invoice."""
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT status, due_date, paid_date FROM invoices WHERE id = ?",
            (invoice_id,),
        ).fetchone()
        return (row["status"], row["due_date"], row["paid_date"])
    finally:
        conn.close()


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


def simulate(
    today: date = FIXED_TODAY,
    forecast_days: int = 30,
    delay_invoice_id: int | None = None,
    delay_days: int | None = None,
    expense_amount_cents: int | None = None,
    expense_date: date | None = None,
    income_amount_cents: int | None = None,
    income_date: date | None = None,
) -> dict:
    """Call the service directly against the test database."""
    conn = database.get_connection()
    try:
        return run_what_if(
            conn,
            today=today,
            forecast_days=forecast_days,
            delay_invoice_id=delay_invoice_id,
            delay_days=delay_days,
            expense_amount_cents=expense_amount_cents,
            expense_date=expense_date,
            income_amount_cents=income_amount_cents,
            income_date=income_date,
        )
    finally:
        conn.close()


def daily_on(result: dict, iso: str) -> dict:
    """Return the daily_forecast entry for one ISO date."""
    matches = [entry for entry in result["daily_forecast"] if entry["date"] == iso]
    assert len(matches) == 1
    return matches[0]


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
        ("Simulator Test Client", TEST_CLIENT_EMAIL),
    )
    set_cash_cents(0)
    return client


def post_what_if(client, body: dict):
    """POST to /simulator/what-if and return the raw response."""
    return client.post("/simulator/what-if", json=body)


# ---------------------------------------------------------------------------
# Service: scenario A, delayed client payment
# ---------------------------------------------------------------------------


def test_service_delay_moves_collection_date_only(fresh):
    set_cash_cents(rupees(1000))
    invoice_id = add_invoice("pending", rupees(18000),
                             due_date=day(10, FIXED_TODAY),
                             issue_date=day(-5, FIXED_TODAY))
    before = invoice_row(invoice_id)

    result = simulate(delay_invoice_id=invoice_id, delay_days=15)

    assert result["applied_scenarios"] == ["delay_payment"]
    assert daily_on(result, day(10, FIXED_TODAY))["baseline_income"] == 18000.0
    assert daily_on(result, day(10, FIXED_TODAY))["simulated_income"] == 0.0
    assert daily_on(result, day(25, FIXED_TODAY))["baseline_income"] == 0.0
    assert daily_on(result, day(25, FIXED_TODAY))["simulated_income"] == 18000.0
    assert daily_on(result, day(10, FIXED_TODAY))["baseline_balance"] == 19000.0
    assert daily_on(result, day(10, FIXED_TODAY))["simulated_balance"] == 1000.0
    assert result["baseline"]["closing_balance"] == 19000.0
    assert result["simulated"]["closing_balance"] == 19000.0
    assert result["baseline"]["lowest_balance"] == 1000.0
    assert result["simulated"]["lowest_balance"] == 1000.0
    assert result["difference"] == 0.0
    assert invoice_row(invoice_id) == before


def test_service_delay_missing_invoice_is_404(fresh):
    with pytest.raises(SimulationError) as exc:
        simulate(delay_invoice_id=9999, delay_days=5)
    assert exc.value.status_code == 404


def test_service_delay_paid_invoice_is_422(fresh):
    invoice_id = add_invoice("paid", rupees(18000),
                             due_date=day(5, FIXED_TODAY),
                             paid_date=day(-1, FIXED_TODAY))
    with pytest.raises(SimulationError) as exc:
        simulate(delay_invoice_id=invoice_id, delay_days=5)
    assert exc.value.status_code == 422


def test_service_overdue_invoice_delay_shifts_from_day_seven(fresh):
    invoice_id = add_invoice("overdue", rupees(5000),
                             due_date=day(-5, FIXED_TODAY),
                             issue_date=day(-40, FIXED_TODAY))

    result = simulate(delay_invoice_id=invoice_id, delay_days=10)

    assert daily_on(result, day(7, FIXED_TODAY))["baseline_income"] == 5000.0
    assert daily_on(result, day(7, FIXED_TODAY))["simulated_income"] == 0.0
    assert daily_on(result, day(17, FIXED_TODAY))["baseline_income"] == 0.0
    assert daily_on(result, day(17, FIXED_TODAY))["simulated_income"] == 5000.0


# ---------------------------------------------------------------------------
# Service: scenario B, unexpected expense
# ---------------------------------------------------------------------------


def test_service_unexpected_expense_lowers_closing_by_amount(fresh):
    set_cash_cents(rupees(20000))
    before = stored_state()

    result = simulate(expense_amount_cents=rupees(5000), expense_date=fdate(3))

    assert result["applied_scenarios"] == ["unexpected_expense"]
    assert daily_on(result, day(3, FIXED_TODAY))["baseline_expenses"] == 0.0
    assert daily_on(result, day(3, FIXED_TODAY))["simulated_expenses"] == 5000.0
    assert result["baseline"]["closing_balance"] == 20000.0
    assert result["simulated"]["closing_balance"] == 15000.0
    assert result["difference"] == -5000.0
    assert stored_state() == before


def test_service_expense_dated_yesterday_is_422(fresh):
    with pytest.raises(SimulationError) as exc:
        simulate(expense_amount_cents=rupees(5000), expense_date=fdate(-1))
    assert exc.value.status_code == 422


def test_service_expense_beyond_window_is_422(fresh):
    with pytest.raises(SimulationError) as exc:
        simulate(forecast_days=30, expense_amount_cents=rupees(5000), expense_date=fdate(30))
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# Service: scenario C, additional income
# ---------------------------------------------------------------------------


def test_service_additional_income_raises_closing_by_amount(fresh):
    set_cash_cents(rupees(20000))
    before = stored_state()

    result = simulate(income_amount_cents=rupees(10000), income_date=fdate(5))

    assert result["applied_scenarios"] == ["additional_income"]
    assert daily_on(result, day(5, FIXED_TODAY))["simulated_income"] == 10000.0
    assert result["baseline"]["closing_balance"] == 20000.0
    assert result["simulated"]["closing_balance"] == 30000.0
    assert result["difference"] == 10000.0
    assert stored_state() == before


# ---------------------------------------------------------------------------
# Service: combined scenarios and balance metrics
# ---------------------------------------------------------------------------


def test_service_all_three_scenarios_combined(fresh):
    invoice_id = add_invoice("pending", rupees(18000),
                             due_date=day(10, FIXED_TODAY),
                             issue_date=day(-5, FIXED_TODAY))

    result = simulate(
        delay_invoice_id=invoice_id, delay_days=15,
        expense_amount_cents=rupees(5000), expense_date=fdate(3),
        income_amount_cents=rupees(10000), income_date=fdate(5),
    )

    assert result["applied_scenarios"] == [
        "delay_payment", "unexpected_expense", "additional_income",
    ]
    # Baseline closing 18000 (invoice inside the window). Simulated closing
    # 18000 + 10000 - 5000 = 23000; the delayed invoice still lands on day 25.
    assert result["baseline"]["closing_balance"] == 18000.0
    assert result["simulated"]["closing_balance"] == 23000.0
    assert result["difference"] == 5000.0


def test_service_negative_balance_detected_in_simulation_only(fresh):
    set_cash_cents(rupees(1000))
    result = simulate(expense_amount_cents=rupees(5000), expense_date=fdate(2))

    assert result["baseline"]["risk_of_negative_balance"] is False
    assert result["simulated"]["risk_of_negative_balance"] is True
    assert result["risk_of_negative_balance"] is True
    assert result["simulated"]["lowest_balance"] == -4000.0
    assert result["simulated"]["lowest_balance_date"] == day(2, FIXED_TODAY)


def test_service_forecast_days_sets_window_length(fresh):
    for days in (30, 60, 90):
        result = simulate(forecast_days=days, income_amount_cents=rupees(1000),
                          income_date=fdate(1))
        assert len(result["daily_forecast"]) == days
        assert result["forecast_days"] == days


def test_service_forecast_days_45_is_value_error(fresh):
    with pytest.raises(ValueError):
        simulate(forecast_days=45, income_amount_cents=rupees(1000), income_date=fdate(1))


def test_service_empty_database_with_only_extra_income(fresh):
    result = simulate(income_amount_cents=rupees(10000), income_date=fdate(4))
    assert result["baseline"]["closing_balance"] == 0.0
    assert result["simulated"]["closing_balance"] == 10000.0


def test_service_identical_calls_return_equal_results(fresh):
    set_cash_cents(rupees(20000))
    first = simulate(expense_amount_cents=rupees(5000), expense_date=fdate(3),
                     income_amount_cents=rupees(10000), income_date=fdate(5))
    second = simulate(expense_amount_cents=rupees(5000), expense_date=fdate(3),
                      income_amount_cents=rupees(10000), income_date=fdate(5))
    assert first == second


def test_service_simulation_writes_nothing(fresh):
    set_cash_cents(rupees(20000))
    invoice_id = add_invoice("pending", rupees(18000), due_date=day(10, FIXED_TODAY),
                             issue_date=day(-5, FIXED_TODAY))
    invoice_before = invoice_row(invoice_id)
    before = stored_state()

    simulate(delay_invoice_id=invoice_id, delay_days=15,
             expense_amount_cents=rupees(5000), expense_date=fdate(3),
             income_amount_cents=rupees(10000), income_date=fdate(5))

    assert stored_state() == before
    assert invoice_row(invoice_id) == invoice_before


# ---------------------------------------------------------------------------
# API: POST /simulator/what-if
# ---------------------------------------------------------------------------


def test_api_expense_only_returns_200(fresh):
    response = post_what_if(fresh, {
        "unexpected_expense": {"amount": 5000, "date": day(3)},
    })
    assert response.status_code == 200
    body = response.json()
    assert body["applied_scenarios"] == ["unexpected_expense"]
    assert "baseline" in body
    assert "simulated" in body
    assert "daily_forecast" in body


def test_api_empty_body_is_422(fresh):
    assert post_what_if(fresh, {}).status_code == 422


def test_api_delay_id_without_days_is_422(fresh):
    assert post_what_if(fresh, {"delay_invoice_id": 1}).status_code == 422


def test_api_delay_days_without_id_is_422(fresh):
    assert post_what_if(fresh, {"delay_days": 5}).status_code == 422


def test_api_delay_days_zero_is_422(fresh):
    body = {"delay_invoice_id": 1, "delay_days": 0}
    assert post_what_if(fresh, body).status_code == 422


def test_api_delay_days_91_is_422(fresh):
    body = {"delay_invoice_id": 1, "delay_days": 91}
    assert post_what_if(fresh, body).status_code == 422


@pytest.mark.parametrize("amount", [0, -5, 1.234])
def test_api_bad_expense_amount_is_422(fresh, amount):
    body = {"unexpected_expense": {"amount": amount, "date": day(3)}}
    assert post_what_if(fresh, body).status_code == 422


def test_api_unknown_top_level_key_is_422(fresh):
    body = {"foo": 1, "unexpected_expense": {"amount": 5000, "date": day(3)}}
    assert post_what_if(fresh, body).status_code == 422


def test_api_forecast_days_45_is_422(fresh):
    body = {"forecast_days": 45, "unexpected_expense": {"amount": 5000, "date": day(3)}}
    assert post_what_if(fresh, body).status_code == 422


def test_api_expense_dated_yesterday_is_422(fresh):
    body = {"unexpected_expense": {"amount": 5000, "date": day(-1)}}
    assert post_what_if(fresh, body).status_code == 422


def test_api_delay_of_paid_invoice_is_422(fresh):
    invoice_id = add_invoice("paid", rupees(18000), due_date=day(5),
                             paid_date=day(-1))
    body = {"delay_invoice_id": invoice_id, "delay_days": 5}
    assert post_what_if(fresh, body).status_code == 422


def test_api_delay_of_missing_invoice_is_404(fresh):
    body = {"delay_invoice_id": 9999, "delay_days": 5}
    assert post_what_if(fresh, body).status_code == 404


def test_api_all_scenarios_with_future_invoice_returns_200(fresh):
    invoice_id = add_invoice("pending", rupees(18000), due_date=day(10),
                             issue_date=day(-5))
    body = {
        "delay_invoice_id": invoice_id,
        "delay_days": 15,
        "unexpected_expense": {"amount": 5000, "date": day(3)},
        "additional_income": {"amount": 10000, "date": day(5)},
        "forecast_days": 30,
    }
    response = post_what_if(fresh, body)
    assert response.status_code == 200
    assert response.json()["applied_scenarios"] == [
        "delay_payment", "unexpected_expense", "additional_income",
    ]


def test_api_forecast_endpoint_still_responds(fresh):
    assert fresh.get("/forecast/cashflow").status_code == 200


def test_api_dashboard_endpoint_still_responds(fresh):
    assert fresh.get("/dashboard/summary").status_code == 200
