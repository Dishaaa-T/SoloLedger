"""
Tests for the settings and cash balance endpoints.

Each test uses its own temporary database file, so the real
sololedger.db is never touched.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

import database
from main import app

TODAY = date.today()


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point the app at a temporary database BEFORE the app starts.
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as c:
        yield c


def test_get_settings_on_fresh_db(client):
    response = client.get("/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["current_cash"] == 4250.0
    assert data["currency"] == "INR"
    # The seed does not set balance_updated_at, so a fresh DB returns null.
    assert data["updated_at"] is None or isinstance(data["updated_at"], str)


def test_get_balance_on_fresh_db(client):
    response = client.get("/settings/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["current_cash"] == 4250.0
    assert data["currency"] == "INR"


def test_put_balance_sets_value_and_timestamp(client):
    response = client.put("/settings/balance", json={"current_cash": 65000})
    assert response.status_code == 200
    data = response.json()
    assert data["current_cash"] == 65000.0
    assert isinstance(data["updated_at"], str)

    follow_up = client.get("/settings/balance")
    assert follow_up.json()["current_cash"] == 65000.0


def test_put_balance_with_decimals(client):
    response = client.put("/settings/balance", json={"current_cash": 1234.56})
    assert response.status_code == 200
    assert response.json()["current_cash"] == 1234.56


def test_put_balance_zero_is_allowed(client):
    response = client.put("/settings/balance", json={"current_cash": 0})
    assert response.status_code == 200
    assert response.json()["current_cash"] == 0.0


@pytest.mark.parametrize(
    "body",
    [
        {"current_cash": -1},
        {"current_cash": 10.123},
        {"current_cash": None},
        {"current_cash": "abc"},
        {},
        {"current_cash": 100, "currency": "USD"},
    ],
)
def test_invalid_balance_body_is_422(client, body):
    response = client.put("/settings/balance", json=body)
    assert response.status_code == 422


def test_put_balance_keeps_one_cash_row(client):
    client.put("/settings/balance", json={"current_cash": 500})
    client.put("/settings/balance", json={"current_cash": 600})
    conn = database.get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM settings WHERE key = 'cash_balance_cents'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_creating_expense_does_not_change_balance(client):
    before = client.get("/settings/balance").json()["current_cash"]
    response = client.post(
        "/expenses",
        json={
            "title": "Test expense",
            "amount": 500,
            "category": "Other",
            "expense_date": TODAY.isoformat(),
        },
    )
    assert response.status_code == 201
    after = client.get("/settings/balance").json()["current_cash"]
    assert after == before


def test_existing_endpoints_still_respond(client):
    assert client.get("/clients").status_code == 200
    assert client.get("/expenses").status_code == 200
