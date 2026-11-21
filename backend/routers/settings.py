"""
Settings endpoints: read the freelancer's settings and the cash balance.

The cash balance is stored in the existing key-value settings table:
- cash_balance_cents: the balance as an integer number of cents (string).
- currency:           fixed to 'INR'. It cannot be changed through the API.
- balance_updated_at: ISO 8601 UTC time of the last manual balance update.

The balance is entered by hand. Invoices and expenses do not change it.

All SQL uses ? placeholders. Values are never placed into the SQL text.
"""

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status

import database
from schemas import BalanceOut, BalanceUpdate, SettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])


def get_db():
    """Yield one database connection per request and always close it."""
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _read_settings(conn: sqlite3.Connection) -> dict:
    """Read the settings, using defaults for any key that is missing."""
    cents_text = database.get_setting(conn, "cash_balance_cents") or "0"
    currency = database.get_setting(conn, "currency") or "INR"
    updated_at = database.get_setting(conn, "balance_updated_at")
    return {
        "current_cash": (Decimal(int(cents_text)) / 100).quantize(Decimal("0.01")),
        "currency": currency,
        "updated_at": updated_at,
    }


@router.get("", response_model=SettingsOut)
def get_settings(db: sqlite3.Connection = Depends(get_db)):
    return _read_settings(db)


@router.get("/balance", response_model=BalanceOut)
def get_balance(db: sqlite3.Connection = Depends(get_db)):
    return _read_settings(db)


@router.put("/balance", response_model=BalanceOut)
def update_balance(payload: BalanceUpdate, db: sqlite3.Connection = Depends(get_db)):
    # INR amount (2 decimal places) to integer cents, for example 65000.50 -> 6500050.
    cents = int((payload.current_cash * 100).to_integral_value())
    updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        # Both keys are written in one transaction: either both change or neither.
        database.set_setting(db, "cash_balance_cents", str(cents))
        database.set_setting(db, "balance_updated_at", updated_at)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update the cash balance.",
        )
    return _read_settings(db)
