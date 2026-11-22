"""
Expense endpoints: create, list, get, update and delete.

All SQL uses ? placeholders. Values are never placed into the SQL text.
Status ('paid' or 'upcoming') may be sent on create and update. On create,
when it is omitted, it is computed from expense_date: a date today or earlier
is 'paid', a later date is 'upcoming'. On update, an omitted status keeps the
stored value.
"""

import sqlite3
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status

import database
from schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate

router = APIRouter(prefix="/expenses", tags=["expenses"])

# Maps each updatable request field to its database column. Only these
# column names can ever appear in an UPDATE statement.
_UPDATABLE_COLUMNS = {
    "title": "title",
    "description": "description",
    "amount": "amount_cents",
    "category": "category",
    "expense_date": "expense_date",
    "payment_method": "payment_method",
    "notes": "notes",
    "status": "status",
}

_SELECT_EXPENSE = """
    SELECT id, title, description, amount_cents, category, expense_date,
           payment_method, notes, status, created_at
    FROM expenses
"""


def get_db():
    """Yield one database connection per request and always close it."""
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _to_cents(amount: Decimal) -> int:
    """Convert an INR amount (2 decimal places) to integer cents."""
    return int(round(amount * 100))


def _status_for(expense_day: date) -> str:
    return "paid" if expense_day <= date.today() else "upcoming"


def _fetch_expense(db: sqlite3.Connection, expense_id: int):
    return db.execute(_SELECT_EXPENSE + " WHERE id = ?", (expense_id,)).fetchone()


def _row_to_expense(row) -> ExpenseOut:
    return ExpenseOut(
        id=row["id"],
        title=row["title"],
        # A blank description is stored as '' (the column is NOT NULL) and
        # returned as null.
        description=row["description"] or None,
        amount=(Decimal(row["amount_cents"]) / 100).quantize(Decimal("0.01")),
        category=row["category"],
        expense_date=row["expense_date"],
        payment_method=row["payment_method"],
        notes=row["notes"],
        status=row["status"],
        created_at=row["created_at"],
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ExpenseOut)
def create_expense(payload: ExpenseCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.execute(
        """
        INSERT INTO expenses
            (title, description, amount_cents, category, expense_date,
             payment_method, notes, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.title,
            payload.description or "",
            _to_cents(payload.amount),
            payload.category,
            payload.expense_date.isoformat(),
            payload.payment_method,
            payload.notes,
            payload.status or _status_for(payload.expense_date),
        ),
    )
    db.commit()
    return _row_to_expense(_fetch_expense(db, cursor.lastrowid))


@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    category: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: sqlite3.Connection = Depends(get_db),
):
    # The WHERE clause is built from fixed text; the values use ? placeholders.
    clauses: list[str] = []
    params: list = []

    if category is not None:
        category = category.strip()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Category filter cannot be empty.",
            )
        clauses.append("category COLLATE NOCASE = ?")
        params.append(category)

    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date cannot be after end_date.",
        )
    if start_date is not None:
        clauses.append("expense_date >= ?")
        params.append(start_date.isoformat())
    if end_date is not None:
        clauses.append("expense_date <= ?")
        params.append(end_date.isoformat())

    sql = _SELECT_EXPENSE
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY expense_date DESC, id DESC"

    rows = db.execute(sql, params).fetchall()
    return [_row_to_expense(row) for row in rows]


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(expense_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = _fetch_expense(db, expense_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found.",
        )
    return _row_to_expense(row)


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    existing = _fetch_expense(db, expense_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found.",
        )

    # Only fields the client actually sent are updated. Omitted fields keep
    # their current values.
    sent = payload.model_dump(exclude_unset=True)
    if not sent:
        return _row_to_expense(existing)

    assignments: list[str] = []
    values: list = []
    for field, column in _UPDATABLE_COLUMNS.items():
        if field not in sent:
            continue
        value = sent[field]
        if field == "amount":
            value = _to_cents(value)
        elif field == "expense_date":
            value = value.isoformat()
        elif field == "description" and value is None:
            value = ""
        assignments.append(f"{column} = ?")
        values.append(value)

    values.append(expense_id)
    sql = f"UPDATE expenses SET {', '.join(assignments)} WHERE id = ?"
    db.execute(sql, values)
    db.commit()

    return _row_to_expense(_fetch_expense(db, expense_id))


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: sqlite3.Connection = Depends(get_db)):
    if _fetch_expense(db, expense_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense {expense_id} not found.",
        )
    db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
