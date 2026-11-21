"""
Cash-flow forecast endpoint.

GET /forecast/cashflow?days=30|60|90
The forecast is calculated by services/forecast.py from the database. Any
other days value is rejected with 422.
"""

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

import database
from schemas import FORECAST_DAYS, CashflowForecastOut
from services.forecast import build_cashflow_forecast

router = APIRouter(prefix="/forecast", tags=["forecast"])


def get_db():
    """Yield one database connection per request and always close it."""
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/cashflow", response_model=CashflowForecastOut)
def get_cashflow_forecast(
    days: int = Query(default=30),
    db: sqlite3.Connection = Depends(get_db),
):
    if days not in FORECAST_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="days must be one of 30, 60, 90.",
        )
    try:
        result = build_cashflow_forecast(db, days, date.today())
    except sqlite3.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not build the cash-flow forecast.",
        )
    return CashflowForecastOut(**result)
