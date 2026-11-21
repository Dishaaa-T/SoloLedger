"""
Action Centre endpoint.

GET /action-centre
The alerts are built by services/action_centre.py from the database. This
router only reads the optional filters and maps database errors to HTTP responses.
"""

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

import database
from schemas import ActionCategory, ActionCentreOut, ActionPriority
from services.action_centre import build_action_centre

router = APIRouter(prefix="/action-centre", tags=["action-centre"])


def get_db():
    """Yield one database connection per request and always close it."""
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("", response_model=ActionCentreOut)
def get_action_centre(
    priority: ActionPriority | None = Query(default=None),
    category: ActionCategory | None = Query(default=None),
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        return build_action_centre(
            db,
            today=date.today(),
            priority=priority,
            category=category,
        )
    except sqlite3.Error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not build the action centre.",
        )
