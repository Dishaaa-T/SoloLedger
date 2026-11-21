"""
Tests for the invoice endpoints.

Each test uses its own temporary database file, so the real
sololedger.db is never touched.
"""

from datetime import date, timedelta

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


def _create_client(client, name="Invoice Client"):
    response = client.post("/clients", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _body(client_id, number="INV-T-001", **fields):
    body = {
        "client_id": client_id,
        "invoice_number": number,
        "description": "Test work",
        "amount": 1000.00,
        "issue_date": (TODAY - timedelta(days=5)).isoformat(),
        "due_date": (TODAY + timedelta(days=25)).isoformat(),
    }
    body.update(fields)
    return body


def _create(client, client_id, number="INV-T-001", **fields):
    return client.post("/invoices", json=_body(client_id, number, **fields))


def _past_invoice_body(client_id, number):
    return _body(
        client_id,
        number,
        issue_date=(TODAY - timedelta(days=60)).isoformat(),
        due_date=(TODAY - timedelta(days=30)).isoformat(),
    )


def test_create_invoice_returns_201_with_nested_client(client):
    client_id = _create_client(client, name="Nested Name")
    response = _create(client, client_id, amount=25000.00)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["client_id"] == client_id
    assert data["amount"] == 25000.0
    assert data["status"] == "pending"
    assert data["paid_date"] is None
    assert data["client"]["id"] == client_id
    assert data["client"]["name"] == "Nested Name"
    assert data["created_at"]


def test_amount_zero_is_rejected(client):
    client_id = _create_client(client)
    assert _create(client, client_id, amount=0).status_code == 422


def test_amount_negative_is_rejected(client):
    client_id = _create_client(client)
    assert _create(client, client_id, amount=-5).status_code == 422


def test_amount_with_three_decimals_is_rejected(client):
    client_id = _create_client(client)
    assert _create(client, client_id, amount="10.123").status_code == 422


def test_due_date_before_issue_date_is_rejected(client):
    client_id = _create_client(client)
    response = _create(
        client,
        client_id,
        issue_date="2026-05-10",
        due_date="2026-05-01",
    )
    assert response.status_code == 422


def test_nonexistent_client_is_404(client):
    response = _create(client, 9999)
    assert response.status_code == 404


def test_duplicate_invoice_number_is_conflict(client):
    client_id = _create_client(client)
    assert _create(client, client_id, number="DUP-1").status_code == 201
    assert _create(client, client_id, number="DUP-1").status_code == 409


def test_list_includes_created_invoice(client):
    client_id = _create_client(client)
    created = _create(client, client_id, number="LIST-1").json()
    response = client.get("/invoices")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert created["id"] in ids


def test_get_invoice_by_id(client):
    client_id = _create_client(client)
    created = _create(client, client_id, number="GET-1").json()
    response = client.get(f"/invoices/{created['id']}")
    assert response.status_code == 200
    assert response.json()["invoice_number"] == "GET-1"


def test_get_missing_invoice_is_404(client):
    assert client.get("/invoices/9999").status_code == 404


def test_filter_by_status_returns_only_matching(client):
    client_id = _create_client(client)
    pending = _create(client, client_id, number="F-PENDING").json()
    paid = _create(client, client_id, number="F-PAID").json()
    client.post(f"/invoices/{paid['id']}/mark-paid", json={})

    response = client.get("/invoices", params={"status": "pending"})
    assert response.status_code == 200
    items = response.json()
    assert items, "expected at least one pending invoice"
    assert all(item["status"] == "pending" for item in items)
    ids = [item["id"] for item in items]
    assert pending["id"] in ids
    assert paid["id"] not in ids


def test_filter_by_client_id(client):
    first_client = _create_client(client, name="First")
    second_client = _create_client(client, name="Second")
    mine = _create(client, first_client, number="CL-1").json()
    _create(client, second_client, number="CL-2")

    response = client.get("/invoices", params={"client_id": first_client})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert mine["id"] in ids
    assert all(item["client_id"] == first_client for item in response.json())


def test_put_description_keeps_other_fields(client):
    client_id = _create_client(client)
    created = _create(client, client_id, number="PUT-1", amount=500.50).json()
    response = client.put(
        f"/invoices/{created['id']}",
        json={"description": "Updated description"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated description"
    assert data["invoice_number"] == "PUT-1"
    assert data["amount"] == 500.5
    assert data["issue_date"] == created["issue_date"]
    assert data["due_date"] == created["due_date"]
    assert data["status"] == "pending"


def test_put_missing_invoice_is_404(client):
    response = client.put("/invoices/9999", json={"description": "Nobody"})
    assert response.status_code == 404


def test_put_due_date_before_stored_issue_date_is_rejected(client):
    client_id = _create_client(client)
    created = _create(client, client_id, number="PUT-2").json()
    earlier = (date.fromisoformat(created["issue_date"]) - timedelta(days=1))
    response = client.put(
        f"/invoices/{created['id']}",
        json={"due_date": earlier.isoformat()},
    )
    assert response.status_code == 422


def test_mark_paid_without_body_uses_today(client):
    client_id = _create_client(client)
    created = _create(client, client_id, number="PAID-1").json()
    response = client.post(f"/invoices/{created['id']}/mark-paid")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "paid"
    assert data["paid_date"] == TODAY.isoformat()


def test_mark_paid_twice_is_conflict(client):
    client_id = _create_client(client)
    created = _create(client, client_id, number="PAID-2").json()
    first = client.post(f"/invoices/{created['id']}/mark-paid", json={})
    assert first.status_code == 200
    second = client.post(f"/invoices/{created['id']}/mark-paid", json={})
    assert second.status_code == 409


def test_mark_paid_before_issue_date_is_rejected(client):
    client_id = _create_client(client)
    created = _create(client, client_id, number="PAID-3").json()
    too_early = (date.fromisoformat(created["issue_date"]) - timedelta(days=1))
    response = client.post(
        f"/invoices/{created['id']}/mark-paid",
        json={"paid_date": too_early.isoformat()},
    )
    assert response.status_code == 422


def test_mark_paid_missing_invoice_is_404(client):
    assert client.post("/invoices/9999/mark-paid").status_code == 404


def test_past_due_pending_invoice_shows_overdue(client):
    client_id = _create_client(client)
    response = client.post(
        "/invoices",
        json=_past_invoice_body(client_id, "OVD-1"),
    )
    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "overdue"
    fetched = client.get(f"/invoices/{created['id']}")
    assert fetched.json()["status"] == "overdue"


def test_paid_invoice_with_past_dates_stays_paid(client):
    client_id = _create_client(client)
    body = _past_invoice_body(client_id, "OVD-2")
    created = client.post("/invoices", json=body).json()
    paid = client.post(
        f"/invoices/{created['id']}/mark-paid",
        json={"paid_date": body["issue_date"]},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"

    fetched = client.get("/invoices")
    by_id = {item["id"]: item for item in fetched.json()}
    assert by_id[created["id"]]["status"] == "paid"
    assert by_id[created["id"]]["paid_date"] == body["issue_date"]


def test_delete_invoice_then_get_is_404(client):
    client_id = _create_client(client)
    created = _create(client, client_id, number="DEL-1").json()
    response = client.delete(f"/invoices/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/invoices/{created['id']}").status_code == 404


def test_delete_missing_invoice_is_404(client):
    assert client.delete("/invoices/9999").status_code == 404


def test_fresh_database_still_has_seeded_clients(client):
    response = client.get("/clients")
    assert response.status_code == 200
    assert len(response.json()) >= 4
