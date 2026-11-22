"""
Payment-risk feature calculation for client payment prediction.

Pure, deterministic calculation shared by synthetic model training and by
live prediction. The core function, compute_features(), does no database
access and does not import FastAPI. Only load_paid_history() touches the
database, and it only reads.

Units: amounts are integer cents, the same unit as invoices.amount_cents.
Conversion to INR happens only at the output layer, as in services/forecast.py.
Because of this, avg_prior_amount and current_amount are in cents.

Leakage rules (these protect the model from seeing the future):
- Only PAID invoices are used as history.
- Only invoices whose paid_date is strictly before the prediction date are used.
- The target invoice is always excluded (exclude_invoice_id).
- Unpaid or overdue invoices are never labelled late. They have no paid_date,
  so they never enter the history and never count as a late payment.

Delay rule: delay_days = (paid_date - due_date).days. An invoice is late when
delay_days > 0. Paying on the due date counts as on time.

All SQL uses ? placeholders.
"""

import sqlite3
from datetime import date

# Order of the features in the vector given to the model. Do not reorder
# this without retraining the model, because saved models depend on it.
FEATURE_NAMES = (
    "prior_invoice_count",
    "prior_late_count",
    "prior_late_pct",
    "avg_delay_days",
    "max_delay_days",
    "avg_prior_amount",
    "current_amount",
)

# A client needs at least this many prior paid invoices before we predict.
# With less history, the prediction is null and the risk category is Unknown.
MIN_HISTORY_FOR_PREDICTION = 3


def compute_features(
    history: list[tuple[int, date, date]], current_amount: int
) -> dict[str, float]:
    """Compute the feature dict for one client and one target invoice.

    history is a list of (amount_cents, due_date, paid_date) tuples for PAID
    invoices only, as returned by load_paid_history(). current_amount is the
    target invoice amount in integer cents.

    Returns a plain dict with exactly the keys in FEATURE_NAMES. An empty
    history gives 0 for every history-based feature.
    """
    count = len(history)
    delays = [(paid - due).days for _amount, due, paid in history]
    late_count = sum(1 for delay in delays if delay > 0)

    prior_late_pct = late_count / count * 100 if count > 0 else 0.0
    avg_delay_days = sum(delays) / count if count > 0 else 0.0
    max_delay_days = float(max(delays)) if count > 0 else 0.0
    avg_prior_amount = (
        sum(amount for amount, _due, _paid in history) / count if count > 0 else 0.0
    )

    return {
        "prior_invoice_count": count,
        "prior_late_count": late_count,
        "prior_late_pct": prior_late_pct,
        "avg_delay_days": avg_delay_days,
        "max_delay_days": max_delay_days,
        "avg_prior_amount": avg_prior_amount,
        "current_amount": current_amount,
    }


def feature_vector(features: dict[str, float]) -> list[float]:
    """Return the feature values as floats, in FEATURE_NAMES order."""
    return [float(features[name]) for name in FEATURE_NAMES]


def has_sufficient_history(history: list[tuple[int, date, date]]) -> bool:
    """Return True when there are enough prior paid invoices to predict."""
    return len(history) >= MIN_HISTORY_FOR_PREDICTION


def load_paid_history(
    conn: sqlite3.Connection,
    client_id: int,
    before_date: date,
    exclude_invoice_id: int | None = None,
) -> list[tuple[int, date, date]]:
    """Load the leakage-safe paid history for one client.

    Returns (amount_cents, due_date, paid_date) tuples, ordered by paid_date
    then id. Only paid invoices with paid_date strictly before before_date are
    included. The invoice whose id is exclude_invoice_id is never included.
    When exclude_invoice_id is None, the "id IS NOT NULL" test is always true,
    so nothing is excluded.

    Dates are stored as ISO 'YYYY-MM-DD' text, so comparing them as strings
    is correct.
    """
    rows = conn.execute(
        """
        SELECT amount_cents, due_date, paid_date FROM invoices
         WHERE client_id = ?
           AND status = 'paid'
           AND paid_date IS NOT NULL
           AND paid_date < ?
           AND id IS NOT ?
         ORDER BY paid_date, id
        """,
        (client_id, before_date.isoformat(), exclude_invoice_id),
    ).fetchall()

    return [
        (int(row[0]), date.fromisoformat(row[1]), date.fromisoformat(row[2]))
        for row in rows
    ]
