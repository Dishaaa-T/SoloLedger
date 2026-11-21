"""
Dashboard endpoints: a financial summary calculated from the database.

GET /dashboard/summary?period=this_month|last_month|all_time
All numbers come from the invoices, expenses and settings tables. The
calculation lives in services/dashboard.py.
"""

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

import database
from schemas import DashboardPeriod, DashboardSummaryOut
from services.dashboard import compute_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_db():
    """Yield one database connection per request and always close it."""
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/summary", response_model=DashboardSummaryOut)
def get_dashboard_summary(
    period: DashboardPeriod = Query(default="this_month"),
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        result = compute_dashboard(db, period, date.today())
    except sqlite3.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not calculate the dashboard summary.",
        )
    return DashboardSummaryOut(**result)
