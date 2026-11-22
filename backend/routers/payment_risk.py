"""
Payment-risk endpoint: GET /clients/{client_id}/payment-risk.

Returns the chance that a client pays one invoice late, based on their paid
history before today. The logic lives in services/payment_prediction.py.

All SQL uses ? placeholders. The API never trains a model. If the model file
is missing, the endpoint returns 503 with the training command.
"""

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

import database
from schemas import PaymentRiskOut
from services.payment_prediction import ModelNotTrainedError, predict_client_risk

router = APIRouter(prefix="/clients", tags=["payment-risk"])


def get_db():
    """Yield one database connection per request and always close it."""
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/{client_id}/payment-risk", response_model=PaymentRiskOut)
def get_payment_risk(
    client_id: int,
    invoice_amount: float | None = Query(default=None, gt=0),
    db: sqlite3.Connection = Depends(get_db),
):
    """Estimate the late-payment risk for this client.

    invoice_amount is in INR (rupees). If it is omitted, the client's average
    prior invoice amount is used. The prediction date is today.
    """
    client = db.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found.",
        )

    try:
        return predict_client_risk(db, client_id, invoice_amount, date.today())
    except ModelNotTrainedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
