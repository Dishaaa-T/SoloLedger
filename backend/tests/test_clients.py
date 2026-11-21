"""
Tests for the client endpoints.

Each test uses its own temporary database file, so the real
sololedger.db is never touched.
"""

import pytest
from fastapi.testclient import TestClient

import database
from main import app

PHONE = "+1 555 010 2030"


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point the app at a temporary database BEFORE the app starts.
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as c:
        yield c


def _create(client, **fields):
    body = {"name": "Test Client"}
    body.update(fields)
    return client.post("/clients", json=body)


def test_create_client_with_all_fields(client):
    response = _create(
        client,
        name="Ada Lovelace",
        email="ada@example.com",
        phone=PHONE,
        company="Analytical Co",
        notes="Prefers email contact.",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["name"] == "Ada Lovelace"
    assert data["email"] == "ada@example.com"
    assert data["phone"] == PHONE
    assert data["company"] == "Analytical Co"
    assert data["notes"] == "Prefers email contact."
    assert data["created_at"]


def test_create_client_name_only_has_null_optionals(client):
    response = _create(client, name="Name Only")
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Name Only"
    assert data["email"] is None
    assert data["phone"] is None
    assert data["company"] is None
    assert data["notes"] is None


def test_create_client_blank_name_is_rejected(client):
    response = _create(client, name="   ")
    assert response.status_code == 422


def test_create_client_invalid_email_is_rejected(client):
    response = _create(client, name="Bad Email", email="not-an-email")
    assert response.status_code == 422


def test_create_client_duplicate_email_is_conflict(client):
    first = _create(client, name="First", email="dup@example.com")
    assert first.status_code == 201
    second = _create(client, name="Second", email="dup@example.com")
    assert second.status_code == 409


def test_list_clients_includes_created_client(client):
    created = _create(client, name="Listed Client").json()
    response = client.get("/clients")
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert created["id"] in ids


def test_get_client_by_id(client):
    created = _create(client, name="Fetch Me", phone=PHONE).json()
    response = client.get(f"/clients/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Fetch Me"
    assert response.json()["phone"] == PHONE


def test_get_missing_client_is_404(client):
    response = client.get("/clients/9999")
    assert response.status_code == 404


def test_update_name_and_phone_keeps_other_fields(client):
    created = _create(
        client,
        name="Old Name",
        email="keep@example.com",
        company="Keep Co",
        notes="Keep notes",
    ).json()
    response = client.put(
        f"/clients/{created['id']}",
        json={"name": "New Name", "phone": PHONE},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["phone"] == PHONE
    assert data["email"] == "keep@example.com"
    assert data["company"] == "Keep Co"
    assert data["notes"] == "Keep notes"


def test_update_missing_client_is_404(client):
    response = client.put("/clients/9999", json={"name": "Nobody"})
    assert response.status_code == 404


def test_update_name_to_empty_is_rejected(client):
    created = _create(client, name="Valid Name").json()
    response = client.put(f"/clients/{created['id']}", json={"name": ""})
    assert response.status_code == 422


def test_delete_client_then_get_is_404(client):
    created = _create(client, name="Delete Me").json()
    response = client.delete(f"/clients/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/clients/{created['id']}").status_code == 404


def test_delete_missing_client_is_404(client):
    response = client.delete("/clients/9999")
    assert response.status_code == 404


def test_delete_client_with_invoice_is_conflict(client):
    created = _create(client, name="Has Invoice").json()

    conn = database.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO invoices
                (client_id, invoice_number, description, amount_cents,
                 status, issue_date, due_date, paid_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created["id"],
                "TEST-001",
                "Test invoice",
                1000,
                "pending",
                "2026-01-01",
                "2026-02-01",
                None,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.delete(f"/clients/{created['id']}")
    assert response.status_code == 409


def test_fresh_database_has_seeded_clients(client):
    response = client.get("/clients")
    assert response.status_code == 200
    assert len(response.json()) >= 4
