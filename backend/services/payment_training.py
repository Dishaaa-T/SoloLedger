"""
Training for the payment-risk model, using SYNTHETIC invoice data.

This module creates fake invoices for many simulated clients, builds
training rows with the shared feature code in services/payment_features.py,
trains a RandomForest classifier, and saves it to backend/models/.

THE TRAINING COMMAND (run from the backend folder):

    python -m services.payment_training

This is the ONLY place where the model file is written. The API never
trains a model during a request. If the model file is missing, the API
returns an error that points to the command above.

Rules in this file:
- No database access. The data is generated in memory.
- Nothing runs at import time. Training only happens when you call a
  function or run this file directly.
- All randomness comes from numpy.random.default_rng(seed), so the same
  seed always gives the same invoices and the same metrics.
- Amounts are integer cents (the same unit as invoices.amount_cents).

Leakage rule: when building training rows, the history for an invoice
only uses that client's OTHER paid invoices whose paid_date is strictly
before the target invoice's issue_date. The target's own outcome is
never used as history.
"""

import os
from datetime import date, timedelta

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit

from services.payment_features import (
    FEATURE_NAMES,
    compute_features,
    feature_vector,
    has_sufficient_history,
)

# --- Settings -------------------------------------------------------------

# The fixed "today" for synthetic data. Using a fixed date keeps output
# the same every time, no matter when the code runs.
ANCHOR_DATE = date(2025, 12, 31)

# Issue dates are spread over this many days before the anchor (about 2 years).
HISTORY_DAYS = 730

# Each client behaves in one of three ways.
# Each value is (mean delay in days, standard deviation). A delay of
# 0 or less means the client paid on time or early.
BEHAVIOUR_PROFILES: dict[str, tuple[float, float]] = {
    "prompt": (-2.0, 3.0),
    "mixed": (4.0, 6.0),
    "late": (14.0, 8.0),
}
BEHAVIOUR_TYPES: tuple[str, ...] = ("prompt", "mixed", "late")
BEHAVIOUR_WEIGHTS: tuple[float, ...] = (0.3, 0.4, 0.3)

# Share of invoices that are still unpaid at the anchor date.
UNPAID_SHARE = 0.15

# Default training size and seed.
DEFAULT_N_CLIENTS = 80
DEFAULT_N_INVOICES = 3600
DEFAULT_SEED = 42

# Model file location: backend/models/payment_risk.joblib.
# __file__ is backend/services/payment_training.py, so go up two folders.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL_PATH = os.path.join(_BACKEND_DIR, "models", "payment_risk.joblib")

SYNTHETIC_WARNING = (
    "Trained on SYNTHETIC data. These metrics do not represent real-world "
    "prediction accuracy."
)


# --- 1. Synthetic data -----------------------------------------------------

def generate_synthetic_invoices(
    n_clients: int = DEFAULT_N_CLIENTS,
    n_invoices: int = DEFAULT_N_INVOICES,
    seed: int = DEFAULT_SEED,
) -> list[dict]:
    """Create fake invoices for several simulated clients.

    Each client gets one behaviour type ("prompt", "mixed" or "late") and a
    typical invoice size. Invoices are shared out evenly across clients.

    Each invoice is a dict with these keys:
    - client_id (int), invoice_number (str, e.g. "SYN-000001")
    - amount (int, integer CENTS, always a whole number of rupees)
    - issue_date, due_date, paid_date (ISO 'YYYY-MM-DD' strings, or None)
    - status ("paid", "pending" or "overdue"), source ("synthetic")

    Status is judged as of ANCHOR_DATE. A payment dated after the anchor
    counts as not yet paid, so it becomes "pending" or "overdue".
    """
    if n_clients < 1 or n_invoices < 1:
        raise ValueError("n_clients and n_invoices must both be at least 1.")

    rng = np.random.default_rng(seed)

    # Build one profile per client.
    profiles: list[dict] = []
    for index in range(n_clients):
        behaviour_index = int(rng.choice(len(BEHAVIOUR_TYPES), p=BEHAVIOUR_WEIGHTS))
        behaviour = BEHAVIOUR_TYPES[behaviour_index]
        typical_rupees = int(rng.integers(5_000, 300_001))  # Rs 5,000 to Rs 3,00,000
        profiles.append(
            {
                "client_id": index + 1,
                "behaviour": behaviour,
                "typical_rupees": typical_rupees,
            }
        )

    invoices: list[dict] = []
    for i in range(n_invoices):
        # Share invoices evenly: invoice i goes to client i % n_clients.
        profile = profiles[i % n_clients]
        delay_mean, delay_sd = BEHAVIOUR_PROFILES[profile["behaviour"]]

        # Amount: the client's typical size, varied by up to 30%, in whole rupees.
        factor = rng.uniform(0.7, 1.3)
        rupees = max(1, int(round(profile["typical_rupees"] * factor)))
        amount_cents = rupees * 100

        # Issue date: between 1 and 730 days before the anchor.
        days_before_anchor = int(rng.integers(1, HISTORY_DAYS + 1))
        issue = ANCHOR_DATE - timedelta(days=days_before_anchor)

        # Payment terms: 7 to 45 days after issue.
        term_days = int(rng.integers(7, 46))
        due = issue + timedelta(days=term_days)

        # Payment delay in days, drawn from the client's behaviour.
        is_unpaid = rng.random() < UNPAID_SHARE
        delay = int(round(rng.normal(delay_mean, delay_sd)))
        paid = due + timedelta(days=delay)
        if paid < issue:
            paid = issue  # a payment cannot come before the invoice was issued

        # Decide the status as of the anchor date.
        if is_unpaid or paid > ANCHOR_DATE:
            paid_date = None
            status = "overdue" if due < ANCHOR_DATE else "pending"
        else:
            paid_date = paid
            status = "paid"

        invoices.append(
            {
                "client_id": profile["client_id"],
                "invoice_number": f"SYN-{i + 1:06d}",
                "amount": amount_cents,
                "issue_date": issue.isoformat(),
                "due_date": due.isoformat(),
                "paid_date": paid_date.isoformat() if paid_date else None,
                "status": status,
                "source": "synthetic",
            }
        )

    return invoices


# --- 2. Training rows --------------------------------------------------------

def build_training_rows(
    invoices: list[dict],
) -> tuple[list[list[float]], list[int], list[int]]:
    """Turn invoices into (X, y, groups) for model training.

    Only PAID invoices with a paid_date become training rows. For each one:
    - The history is the same client's OTHER paid invoices whose paid_date
      is strictly before this invoice's issue_date (no future information).
    - The row is kept only if has_sufficient_history() is True.
    - The label y is 1 if the invoice was paid late (paid_date > due_date),
      otherwise 0.
    - groups holds the client_id, so the train/test split can keep each
      client on one side only.

    Returns three parallel lists: feature rows, labels and group ids.
    """
    # Group the paid invoices by client so the history lookup is quick.
    paid_by_client: dict[int, list[dict]] = {}
    for inv in invoices:
        if inv["status"] == "paid" and inv["paid_date"] is not None:
            paid_by_client.setdefault(inv["client_id"], []).append(inv)

    X: list[list[float]] = []
    y: list[int] = []
    groups: list[int] = []

    for inv in invoices:
        # Only paid invoices can be labelled. Unpaid ones are never used.
        if inv["status"] != "paid" or inv["paid_date"] is None:
            continue

        issue = date.fromisoformat(inv["issue_date"])
        due = date.fromisoformat(inv["due_date"])
        paid = date.fromisoformat(inv["paid_date"])

        # Build the leakage-safe history for this invoice.
        history: list[tuple[int, date, date]] = []
        for other in paid_by_client.get(inv["client_id"], []):
            if other["invoice_number"] == inv["invoice_number"]:
                continue  # never use the target invoice as its own history
            other_paid = date.fromisoformat(other["paid_date"])
            if other_paid < issue:  # strictly before this invoice's issue date
                history.append(
                    (
                        int(other["amount"]),
                        date.fromisoformat(other["due_date"]),
                        other_paid,
                    )
                )

        if not has_sufficient_history(history):
            continue

        features = compute_features(history, current_amount=int(inv["amount"]))
        X.append(feature_vector(features))
        y.append(1 if paid > due else 0)  # 1 = paid late
        groups.append(inv["client_id"])

    return X, y, groups


# --- 3. Training and evaluation ----------------------------------------------

def _train(
    invoices: list[dict], seed: int
) -> tuple[RandomForestClassifier, dict, int]:
    """Train the model and return (model, metrics, number_of_rows).

    This is shared by train_and_evaluate() and train_default_model().
    """
    X, y, groups = build_training_rows(invoices)
    if len(X) == 0:
        raise ValueError("No training rows were produced. Check the invoice data.")

    X_arr = np.asarray(X, dtype=float)
    y_arr = np.asarray(y, dtype=int)
    groups_arr = np.asarray(groups)

    # Split by client: no client appears in both the training and test sets.
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_idx, test_idx = next(splitter.split(X_arr, y_arr, groups=groups_arr))

    X_train, y_train = X_arr[train_idx], y_arr[train_idx]
    X_test, y_test = X_arr[test_idx], y_arr[test_idx]

    if len(np.unique(y_test)) < 2:
        raise ValueError(
            "The test split has only one outcome class, so ROC AUC cannot be "
            "computed. Use more invoices or more clients."
        )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=seed,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_prob)), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=[0, 1]).tolist(),
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
        "positive_rate_train": round(float(y_train.mean()), 4),
        "positive_rate_test": round(float(y_test.mean()), 4),
    }
    return model, metrics, len(X)


def train_and_evaluate(invoices: list[dict], seed: int = DEFAULT_SEED) -> dict:
    """Train on a client-grouped split and return the test-set metrics.

    The returned dict has: accuracy, precision, recall, f1, roc_auc,
    confusion_matrix (list of lists), train_rows, test_rows,
    positive_rate_train and positive_rate_test. Floats are rounded to 4 places.
    """
    _model, metrics, _n_rows = _train(invoices, seed)
    return metrics


# --- 4. Saving and loading -----------------------------------------------------

def save_model(model: object, metadata: dict, path: str) -> None:
    """Save the model and its metadata to one joblib file.

    The file holds {"model": model, "metadata": metadata}. The folder is
    created if it does not exist yet.
    """
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    joblib.dump({"model": model, "metadata": metadata}, path)


def load_model(path: str) -> dict:
    """Load the bundle saved by save_model().

    Returns the dict {"model": ..., "metadata": ...}. This only reads the
    file. It never trains anything.
    """
    return joblib.load(path)


# --- 5. Full default training run ----------------------------------------------

def train_default_model() -> dict:
    """Generate data, train, save to DEFAULT_MODEL_PATH, and return metadata.

    This is the only function that writes the model file.
    """
    invoices = generate_synthetic_invoices(
        n_clients=DEFAULT_N_CLIENTS,
        n_invoices=DEFAULT_N_INVOICES,
        seed=DEFAULT_SEED,
    )
    model, metrics, n_rows = _train(invoices, DEFAULT_SEED)

    metadata = {
        "training_data_source": "synthetic",
        "feature_names": list(FEATURE_NAMES),
        "seed": DEFAULT_SEED,
        "n_invoices": len(invoices),
        "n_training_rows": n_rows,
        "metrics": metrics,
        "trained_on_anchor_date": ANCHOR_DATE.isoformat(),
        "warning": SYNTHETIC_WARNING,
    }
    save_model(model, metadata, DEFAULT_MODEL_PATH)
    return metadata


# --- Command-line entry point ----------------------------------------------------

# Run with:  python -m services.payment_training   (from the backend folder)
if __name__ == "__main__":
    result = train_default_model()
    metrics = result["metrics"]

    print("Payment-risk model trained (synthetic data)")
    print("-" * 44)
    for key in (
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "train_rows",
        "test_rows",
        "positive_rate_train",
        "positive_rate_test",
    ):
        print(f"{key:<22}{metrics[key]}")
    print(f"{'confusion_matrix':<22}{metrics['confusion_matrix']}")
    print("-" * 44)
    print(f"Saved to: {DEFAULT_MODEL_PATH}")
    print(f"WARNING: {result['warning']}")
