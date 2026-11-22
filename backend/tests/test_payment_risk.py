"""
Tests for the payment-risk prediction (ML) feature.

Each test uses its own temporary database file, so the real sololedger.db is
never touched. The real saved model (backend/models/payment_risk.joblib) is
used by the API tests. The training test writes to a temporary folder.
"""

import itertools
import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import database
import services.payment_prediction as prediction
import services.payment_training as training
from main import app
from services.payment_features import FEATURE_NAMES, load_paid_history
from services.payment_prediction import (
    ModelNotTrainedError,
    get_risk_category,
    predict_client_risk,
)

# A fixed prediction date for the service-level tests.
PREDICTION_DATE = date(2025, 6, 1)

# Unique invoice numbers for the test rows.
_counter = itertools.count(1)


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point the app at a temporary database BEFORE the app starts.
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def conn(client):
    # A direct connection to the same temporary database, for inserting rows.
    connection = database.get_connection()
    yield connection
    connection.close()


def _new_client(conn, name="Test Client") -> int:
    cursor = conn.execute("INSERT INTO clients (name) VALUES (?)", (name,))
    conn.commit()
    return cursor.lastrowid


def _add_invoice(conn, client_id, status, issue, due, paid=None, amount_cents=10_000_000):
    number = f"PR-TEST-{next(_counter):05d}"
    cursor = conn.execute(
        """
        INSERT INTO invoices
            (client_id, invoice_number, amount_cents, status,
             issue_date, due_date, paid_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            client_id,
            number,
            amount_cents,
            status,
            issue.isoformat(),
            due.isoformat(),
            paid.isoformat() if paid else None,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def _add_paid(conn, client_id, paid_date, days_late, amount_cents=10_000_000):
    """Add a paid invoice. Its delay (paid minus due) is days_late."""
    due = paid_date - timedelta(days=days_late)
    issue = due - timedelta(days=30)
    return _add_invoice(conn, client_id, "paid", issue, due, paid_date, amount_cents)


# --- Training -----------------------------------------------------------------

def test_training_writes_and_reloads_model_with_synthetic_metadata(tmp_path, monkeypatch):
    model_path = tmp_path / "models" / "payment_risk.joblib"
    # train_default_model() reads these module settings at call time, so
    # patching them makes a small, fast run that writes to the temp folder.
    monkeypatch.setattr(training, "DEFAULT_N_CLIENTS", 20)
    monkeypatch.setattr(training, "DEFAULT_N_INVOICES", 400)
    monkeypatch.setattr(training, "DEFAULT_MODEL_PATH", str(model_path))

    metadata = training.train_default_model()

    assert model_path.exists()
    bundle = training.load_model(str(model_path))
    assert set(bundle) == {"model", "metadata"}
    assert bundle["metadata"]["training_data_source"] == "synthetic"
    assert bundle["metadata"]["n_invoices"] == 400
    assert list(bundle["metadata"]["feature_names"]) == list(FEATURE_NAMES)
    assert metadata["training_data_source"] == "synthetic"

    # The reloaded model can score a feature vector of the right length.
    probabilities = bundle["model"].predict_proba([[0.0] * len(FEATURE_NAMES)])
    assert probabilities.shape[1] == 2


def test_train_and_evaluate_returns_metrics_on_small_dataset():
    invoices = training.generate_synthetic_invoices(n_clients=20, n_invoices=400)
    metrics = training.train_and_evaluate(invoices)
    assert 0.0 <= metrics["roc_auc"] <= 1.0
    assert metrics["train_rows"] > 0


# --- Risk categories ------------------------------------------------------------

@pytest.mark.parametrize(
    "probability, expected",
    [
        (0.0, "Low"),
        (0.29, "Low"),
        (0.30, "Medium"),
        (0.59, "Medium"),
        (0.60, "High"),
        (1.0, "High"),
    ],
)
def test_get_risk_category_boundaries(probability, expected):
    assert get_risk_category(probability) == expected


# --- Insufficient history ---------------------------------------------------------

def test_client_with_no_paid_history_is_unknown(client, conn):
    cid = _new_client(conn)
    response = client.get(f"/clients/{cid}/payment-risk")
    assert response.status_code == 200
    data = response.json()
    assert data["probability_delayed"] is None
    assert data["risk_category"] == "Unknown"
    assert data["sufficient_history"] is False
    assert data["historical_stats"]["prior_invoice_count"] == 0


def test_insufficient_history_does_not_load_the_model(conn, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("The model must not be loaded with too little history.")

    monkeypatch.setattr(prediction, "load_cached_bundle", fail_if_called)
    cid = _new_client(conn)
    _add_paid(conn, cid, date(2025, 1, 10), 2)

    result = predict_client_risk(conn, cid, 1000.0, PREDICTION_DATE)

    assert result["risk_category"] == "Unknown"
    assert result["probability_delayed"] is None
    assert "1 prior paid invoice" in result["explanation"]
    assert "At least 3" in result["explanation"]


# --- Client and amount validation -------------------------------------------------

def test_nonexistent_client_is_404(client):
    response = client.get("/clients/9999/payment-risk")
    assert response.status_code == 404


@pytest.mark.parametrize("amount", [0, -5])
def test_invoice_amount_must_be_positive(client, conn, amount):
    cid = _new_client(conn)
    response = client.get(f"/clients/{cid}/payment-risk", params={"invoice_amount": amount})
    assert response.status_code == 422


# --- Leakage guards ---------------------------------------------------------------

def test_invoices_paid_on_or_after_prediction_date_are_not_counted(conn):
    cid = _new_client(conn)
    for day in (date(2025, 1, 10), date(2025, 2, 10), date(2025, 3, 10)):
        _add_paid(conn, cid, day, 3)
    _add_paid(conn, cid, PREDICTION_DATE, 5)  # paid ON the prediction date
    _add_paid(conn, cid, PREDICTION_DATE + timedelta(days=10), 5)  # paid after it

    result = predict_client_risk(conn, cid, 1000.0, PREDICTION_DATE)

    assert result["historical_stats"]["prior_invoice_count"] == 3


def test_target_invoice_is_excluded_from_its_own_history(conn):
    cid = _new_client(conn)
    for day in (date(2025, 1, 10), date(2025, 2, 10), date(2025, 3, 10)):
        _add_paid(conn, cid, day, 3)
    target = _add_paid(conn, cid, date(2025, 4, 10), 4)

    with_target_excluded = load_paid_history(
        conn, cid, before_date=PREDICTION_DATE, exclude_invoice_id=target
    )
    without_exclusion = load_paid_history(conn, cid, before_date=PREDICTION_DATE)

    assert len(with_target_excluded) == 3
    assert len(without_exclusion) == 4


def test_unpaid_and_overdue_invoices_are_not_counted(conn):
    cid = _new_client(conn)
    for day in (date(2025, 1, 10), date(2025, 2, 10), date(2025, 3, 10)):
        _add_paid(conn, cid, day, 3)
    _add_invoice(conn, cid, "pending", date(2025, 5, 1), date(2025, 5, 31))
    _add_invoice(conn, cid, "overdue", date(2025, 1, 1), date(2025, 1, 31))

    result = predict_client_risk(conn, cid, 1000.0, PREDICTION_DATE)

    assert result["historical_stats"]["prior_invoice_count"] == 3
    assert result["historical_stats"]["prior_late_count"] == 3


# --- API response and missing model -------------------------------------------------

def test_response_structure_with_enough_history(client, conn):
    assert os.path.exists(prediction.MODEL_PATH)
    cid = _new_client(conn)
    today = date.today()
    for days_ago, late in [(200, 2), (150, 0), (100, 10), (50, -1)]:
        _add_paid(conn, cid, today - timedelta(days=days_ago), late)

    response = client.get(
        f"/clients/{cid}/payment-risk", params={"invoice_amount": 25000}
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "client_id",
        "invoice_amount",
        "probability_delayed",
        "risk_category",
        "sufficient_history",
        "explanation",
        "historical_stats",
        "training_data_source",
        "synthetic_data_warning",
    }
    assert 0.0 <= data["probability_delayed"] <= 1.0
    assert data["risk_category"] in ("Low", "Medium", "High")
    assert data["sufficient_history"] is True
    assert data["invoice_amount"] == 25000.0
    assert data["training_data_source"] == "synthetic"
    assert data["synthetic_data_warning"]
    stats = data["historical_stats"]
    assert stats["prior_invoice_count"] == 4
    assert stats["prior_late_count"] == 2
    assert stats["avg_prior_amount"] == 100000.0
    assert "4 prior paid invoices" in data["explanation"]


def test_missing_model_file_returns_503(client, conn, tmp_path, monkeypatch):
    monkeypatch.setattr(
        prediction, "MODEL_PATH", str(tmp_path / "does_not_exist.joblib")
    )
    cid = _new_client(conn)
    today = date.today()
    for days_ago in (200, 150, 100):
        _add_paid(conn, cid, today - timedelta(days=days_ago), 3)

    response = client.get(f"/clients/{cid}/payment-risk")

    assert response.status_code == 503
    assert "python -m services.payment_training" in response.json()["detail"]


def test_load_cached_bundle_raises_clear_error_for_missing_file(tmp_path):
    with pytest.raises(ModelNotTrainedError) as excinfo:
        prediction.load_cached_bundle(str(tmp_path / "missing.joblib"))
    assert str(excinfo.value) == (
        "Payment-risk model not found. Train it first with: "
        "python -m services.payment_training"
    )
