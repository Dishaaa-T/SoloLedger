"""
Payment-risk prediction for one client and one invoice amount.

This module answers the question: "How likely is this client to pay late?"

How it works, in plain steps:
1. Load the client's PAID invoices that were paid BEFORE the prediction date.
2. If the client has fewer than 3 such invoices, stop and return "Unknown".
   The model is not even loaded in this case.
3. Otherwise, turn the history into a feature vector and ask the saved
   model for the chance the invoice will be paid late.
4. Map that chance to a category: Low, Medium or High.

Rules in this file:
- The model is ONLY loaded here. It is never trained here. If the model file
  is missing, ModelNotTrainedError is raised with a message that shows the
  training command. Train the model from the backend folder with:
      python -m services.payment_training
- Money: the API gives amounts in rupees (INR). Internally, the features use
  integer cents (the same unit as invoices.amount_cents). This module converts
  rupees to cents on the way in, and cents back to rupees on the way out.
- All database reads go through load_paid_history(), which uses ? placeholders.
"""

import os
import sqlite3
from datetime import date
from typing import Any

from services.payment_features import (
    MIN_HISTORY_FOR_PREDICTION,
    compute_features,
    feature_vector,
    has_sufficient_history,
    load_paid_history,
)
from services.payment_training import DEFAULT_MODEL_PATH, load_model

# --- Settings ----------------------------------------------------------------

# Risk thresholds on the predicted probability (0.0 to 1.0).
# This dict is configurable: change the numbers here to tune the categories.
#   probability <  low_max                -> "Low"
#   low_max <= probability < high_min     -> "Medium"
#   probability >= high_min               -> "High"
RISK_THRESHOLDS: dict[str, float] = {"low_max": 0.30, "high_min": 0.60}

# Where the saved model lives. This is the same default path that
# services/payment_training.py writes to: backend/models/payment_risk.joblib.
MODEL_PATH: str = DEFAULT_MODEL_PATH

# The message shown when the model file has not been created yet.
MODEL_NOT_FOUND_MESSAGE = (
    "Payment-risk model not found. Train it first with: "
    "python -m services.payment_training"
)


class ModelNotTrainedError(Exception):
    """Raised when the saved payment-risk model file does not exist yet."""


# Loaded bundles, keyed by file path. The file is read once, then reused.
_BUNDLE_CACHE: dict[str, dict] = {}


# --- 1. Risk category ----------------------------------------------------------

def get_risk_category(probability: float) -> str:
    """Turn a probability (0.0 to 1.0) into "Low", "Medium" or "High".

    Boundaries (using the default thresholds):
    - below 0.30 is "Low"
    - 0.30 up to but not including 0.60 is "Medium"
    - 0.60 and above is "High"
    """
    if probability < RISK_THRESHOLDS["low_max"]:
        return "Low"
    if probability < RISK_THRESHOLDS["high_min"]:
        return "Medium"
    return "High"


# --- 2. Loading the model ------------------------------------------------------

def load_cached_bundle(path: str = MODEL_PATH) -> dict:
    """Return the saved bundle {"model": ..., "metadata": ...}.

    The first call reads the file with load_model() and stores it in
    _BUNDLE_CACHE. Later calls return the stored copy.

    Raises ModelNotTrainedError if the file does not exist. This function
    never trains a model.
    """
    if path in _BUNDLE_CACHE:
        return _BUNDLE_CACHE[path]

    if not os.path.exists(path):
        raise ModelNotTrainedError(MODEL_NOT_FOUND_MESSAGE)

    bundle = load_model(path)
    _BUNDLE_CACHE[path] = bundle
    return bundle


# --- 3. Prediction ---------------------------------------------------------------

def _to_cents(rupees: float) -> int:
    """Convert rupees (for example 25000.5) to integer cents (2500050)."""
    return int(round(rupees * 100))


def _stats_for_output(stats: dict[str, Any]) -> dict[str, Any]:
    """Shape the historical statistics for the API.

    avg_prior_amount is converted from cents to rupees (INR) here, at the
    output layer, as documented in services/payment_features.py.
    """
    return {
        "prior_invoice_count": int(stats["prior_invoice_count"]),
        "prior_late_count": int(stats["prior_late_count"]),
        "prior_late_pct": round(float(stats["prior_late_pct"]), 2),
        "avg_delay_days": round(float(stats["avg_delay_days"]), 2),
        "max_delay_days": round(float(stats["max_delay_days"]), 2),
        "avg_prior_amount": round(float(stats["avg_prior_amount"]) / 100, 2),
    }


def predict_client_risk(
    conn: sqlite3.Connection,
    client_id: int,
    invoice_amount: float | None,
    prediction_date: date,
) -> dict[str, Any]:
    """Estimate how likely a client is to pay one invoice late.

    - conn: an open database connection (read only).
    - client_id: the client to check.
    - invoice_amount: the invoice amount in rupees, or None. If None, the
      client's average prior invoice amount is used, and the explanation says so.
    - prediction_date: only paid invoices strictly before this date are used.

    Returns a dict with: client_id, invoice_amount (rupees, or None when there
    is no amount to report), probability_delayed (0 to 1, or None),
    risk_category ("Low", "Medium", "High" or "Unknown"), sufficient_history,
    explanation, historical_stats, training_data_source (or None) and
    synthetic_data_warning (or None).
    """
    # Step 1: leakage-safe history (paid, and paid before the prediction date).
    history = load_paid_history(conn, client_id, before_date=prediction_date)

    # Step 2: work out the amount to use, in cents.
    prior_amounts = [amount for amount, _due, _paid in history]
    avg_prior_cents = (
        round(sum(prior_amounts) / len(prior_amounts)) if prior_amounts else 0
    )

    amount_was_averaged = invoice_amount is None and bool(prior_amounts)
    if invoice_amount is None:
        current_cents = avg_prior_cents
    else:
        current_cents = _to_cents(invoice_amount)

    # Step 3: features for the history and the amount.
    stats = compute_features(history, current_amount=current_cents)
    prior_count = len(history)

    # Rupee value of the amount actually used (None when there is no amount).
    amount_inr: float | None = None
    if invoice_amount is not None or prior_amounts:
        amount_inr = round(current_cents / 100, 2)

    amount_note = ""
    if amount_was_averaged:
        amount_note = (
            " No invoice amount was given, so the client's average prior "
            f"invoice amount (INR {amount_inr:,.2f}) was used."
        )

    # Step 4: too little history. Return Unknown without loading the model.
    if not has_sufficient_history(history):
        return {
            "client_id": client_id,
            "invoice_amount": amount_inr,
            "probability_delayed": None,
            "risk_category": "Unknown",
            "sufficient_history": False,
            "explanation": (
                f"Only {prior_count} prior paid invoice(s) found before "
                f"{prediction_date.isoformat()}. At least "
                f"{MIN_HISTORY_FOR_PREDICTION} are needed to estimate payment risk."
            ),
            "historical_stats": _stats_for_output(stats),
            "training_data_source": None,
            "synthetic_data_warning": None,
        }

    # Step 5: enough history. Load the model and predict.
    bundle = load_cached_bundle(MODEL_PATH)
    model = bundle["model"]
    metadata = bundle.get("metadata", {})

    # predict_proba returns one column per class. We want the column for
    # class 1 ("paid late"). Looking it up by name is safer than assuming 1.
    class_index = list(model.classes_).index(1)
    probability = round(float(model.predict_proba([feature_vector(stats)])[0][class_index]), 4)
    category = get_risk_category(probability)

    # Step 6: source and warning from the saved metadata.
    source = metadata.get("training_data_source")
    warning = metadata.get("warning") if source == "synthetic" else None
    source_text = "synthetic" if source == "synthetic" else (source or "unknown")

    explanation = (
        f"Based on {prior_count} prior paid invoices, "
        f"{stats['prior_late_pct']:.1f}% were paid late "
        f"(average delay {stats['avg_delay_days']:.1f} days). "
        f"The model, trained on {source_text} data, estimates a "
        f"{probability * 100:.1f}% chance this invoice is paid late."
        f"{amount_note}"
    )

    return {
        "client_id": client_id,
        "invoice_amount": amount_inr,
        "probability_delayed": probability,
        "risk_category": category,
        "sufficient_history": True,
        "explanation": explanation,
        "historical_stats": _stats_for_output(stats),
        "training_data_source": source,
        "synthetic_data_warning": warning,
    }
