"""
What-if simulator endpoint.

POST /simulator/what-if
The simulation is calculated by services/simulator.py from the database. This
router only converts the request body and maps errors to HTTP responses.
"""

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

import database
from schemas import WhatIfOut, WhatIfRequest
from services.simulator import SimulationError, run_what_if

router = APIRouter(prefix="/simulator", tags=["simulator"])


def get_db():
    """Yield one database connection per request and always close it."""
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _to_cents(amount) -> int:
    """Convert a validated 2-decimal INR amount to whole cents."""
    return int((amount * 100).to_integral_value())


@router.post("/what-if", response_model=WhatIfOut)
def post_what_if(
    payload: WhatIfRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    expense = payload.unexpected_expense
    income = payload.additional_income
    try:
        return run_what_if(
            db,
            today=date.today(),
            forecast_days=payload.forecast_days,
            delay_invoice_id=payload.delay_invoice_id,
            delay_days=payload.delay_days,
            expense_amount_cents=None if expense is None else _to_cents(expense.amount),
            expense_date=None if expense is None else expense.date,
            income_amount_cents=None if income is None else _to_cents(income.amount),
            income_date=None if income is None else income.date,
        )
    except SimulationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except sqlite3.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not run the what-if simulation.",
        )
