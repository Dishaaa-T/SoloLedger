"""
Tests for the expense endpoints.

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


def _body(**fields):
    body = {
        "title": "Figma subscription",
        "description": "Monthly design tool plan",
        "amount": 1250.00,
        "category": "Software & Subscriptions",
        "expense_date": "2026-05-02",
        "payment_method": "card",
        "notes": "Business card ending 4411",
    }
    body.update(fields)
    return body


def _create(client, **fields):
    return client.post("/expenses", json=_body(**fields))


def test_create_full_expense_returns_201(client):
    response = _create(client, payment_method="upi")
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["title"] == "Figma subscription"
    assert data["description"] == "Monthly design tool plan"
    assert data["amount"] == 1250.0
    assert data["category"] == "Software & Subscriptions"
    assert data["expense_date"] == "2026-05-02"
    assert data["payment_method"] == "upi"
    assert data["notes"] == "Business card ending 4411"
    assert data["created_at"]


def test_create_minimal_expense_has_null_optional_fields(client):
    response = client.post(
        "/expenses",
        json={
            "title": "Bus fare",
            "amount": 40,
            "category": "Travel",
            "expense_date": "2025-06-01",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["description"] is None
    assert data["payment_method"] is None
    assert data["notes"] is None


def test_blank_title_is_rejected(client):
    assert _create(client, title="   ").status_code == 422


@pytest.mark.parametrize("amount", [0, -5, "1.234"])
def test_invalid_amount_is_rejected(client, amount):
    assert _create(client, amount=amount).status_code == 422


def test_blank_category_is_rejected(client):
    assert _create(client, category="").status_code == 422


def test_impossible_date_is_rejected(client):
    assert _create(client, expense_date="2026-02-30").status_code == 422


def test_unknown_payment_method_is_rejected(client):
    assert _create(client, payment_method="bitcoin").status_code == 422


def test_list_is_newest_first(client):
    _create(client, title="Old", expense_date="2025-01-05")
    _create(client, title="Newest", expense_date="2025-03-05")
    _create(client, title="Middle", expense_date="2025-02-05")
    response = client.get("/expenses")
    assert response.status_code == 200
    dates = [item["expense_date"] for item in response.json()]
    assert dates == sorted(dates, reverse=True)


def test_category_filter_is_case_insensitive(client):
    travel = _create(client, title="Train", category="Travel",
                     expense_date="2025-04-10").json()
    _create(client, title="Ads", category="Marketing")

    exact = client.get("/expenses", params={"category": "Travel"})
    lower = client.get("/expenses", params={"category": "travel"})
    assert exact.status_code == 200
    assert lower.status_code == 200
    assert [i["id"] for i in exact.json()] == [i["id"] for i in lower.json()]
    assert travel["id"] in [i["id"] for i in exact.json()]
    assert all(i["category"].lower() == "travel" for i in exact.json())


def test_blank_category_filter_is_422(client):
    response = client.get("/expenses", params={"category": "  "})
    assert response.status_code == 422


def test_date_range_filter_returns_only_window(client):
    inside = _create(client, title="Inside", expense_date="2025-02-15").json()
    _create(client, title="Before", expense_date="2025-01-31")
    _create(client, title="After", expense_date="2025-03-01")

    response = client.get(
        "/expenses",
        params={"start_date": "2025-02-01", "end_date": "2025-02-28"},
    )
    assert response.status_code == 200
    items = response.json()
    assert inside["id"] in [i["id"] for i in items]
    assert all("2025-02-01" <= i["expense_date"] <= "2025-02-28" for i in items)


def test_start_date_after_end_date_is_422(client):
    response = client.get(
        "/expenses",
        params={"start_date": "2025-03-01", "end_date": "2025-02-01"},
    )
    assert response.status_code == 422


def test_get_expense_by_id(client):
    created = _create(client, title="Lookup").json()
    response = client.get(f"/expenses/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "Lookup"


def test_get_missing_expense_is_404(client):
    assert client.get("/expenses/9999").status_code == 404


def test_put_amount_only_keeps_other_fields(client):
    created = _create(client, title="Keep me", category="Equipment",
                      expense_date="2025-07-07").json()
    response = client.put(f"/expenses/{created['id']}", json={"amount": 999.5})
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == 999.5
    assert data["title"] == "Keep me"
    assert data["category"] == "Equipment"
    assert data["expense_date"] == "2025-07-07"


def test_put_missing_expense_is_404(client):
    response = client.put("/expenses/9999", json={"amount": 10})
    assert response.status_code == 404


def test_put_blank_title_is_422(client):
    created = _create(client).json()
    response = client.put(f"/expenses/{created['id']}", json={"title": ""})
    assert response.status_code == 422


def test_delete_expense_then_get_is_404(client):
    created = _create(client).json()
    assert client.delete(f"/expenses/{created['id']}").status_code == 204
    assert client.get(f"/expenses/{created['id']}").status_code == 404


def test_delete_missing_expense_is_404(client):
    assert client.delete("/expenses/9999").status_code == 404


def test_create_then_delete_restores_count(client):
    before = len(client.get("/expenses").json())
    created = _create(client).json()
    assert len(client.get("/expenses").json()) == before + 1
    client.delete(f"/expenses/{created['id']}")
    assert len(client.get("/expenses").json()) == before


def test_fresh_database_has_six_seeded_expenses_with_titles(client):
    response = client.get("/expenses")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 6
    assert all(item["title"] for item in items)
