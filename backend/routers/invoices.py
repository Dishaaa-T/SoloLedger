"""
Invoice endpoints: create, list, get, update, delete and mark as paid.

All SQL uses ? placeholders. Values are never placed into the SQL text.
Overdue status is refreshed on every read and write, so a pending invoice
whose due date has passed shows as 'overdue' without a background job.
"""

import sqlite3
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

import database
from schemas import (
    ClientSummary,
    InvoiceCreate,
    InvoiceOut,
    InvoiceUpdate,
    MarkPaidRequest,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])

# Maps each updatable request field to its database column. Only these
# column names can ever appear in an UPDATE statement.
_UPDATABLE_COLUMNS = {
    "client_id": "client_id",
    "invoice_number": "invoice_number",
    "description": "description",
    "amount": "amount_cents",
    "issue_date": "issue_date",
    "due_date": "due_date",
}

# Joins each invoice with its client, so one row carries everything
# the InvoiceOut response needs.
_SELECT_INVOICE = """
    SELECT i.id, i.client_id, i.invoice_number, i.description, i.amount_cents,
           i.status, i.issue_date, i.due_date, i.paid_date, i.created_at,
           c.name AS client_name, c.email AS client_email,
           c.company AS client_company
    FROM invoices AS i
    JOIN clients AS c ON c.id = i.client_id
"""


def get_db():
    """Yield one database connection per request and always close it."""
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _refresh_overdue(db: sqlite3.Connection) -> None:
    """Mark pending invoices whose due date has passed as overdue.

    Paid invoices are never changed. Commits right away, so the change is
    saved even if the calling request fails later.
    """
    db.execute(
        """
        UPDATE invoices
           SET status = 'overdue'
         WHERE status = 'pending'
           AND due_date < date('now', 'localtime')
        """
    )
    db.commit()


def _fetch_invoice(db: sqlite3.Connection, invoice_id: int):
    return db.execute(_SELECT_INVOICE + " WHERE i.id = ?", (invoice_id,)).fetchone()


def _client_exists(db: sqlite3.Connection, client_id: int) -> bool:
    row = db.execute("SELECT 1 FROM clients WHERE id = ?", (client_id,)).fetchone()
    return row is not None


def _to_cents(amount: Decimal) -> int:
    """Convert an INR amount (2 decimal places) to integer cents."""
    return int(round(amount * 100))


def _row_to_invoice(row) -> InvoiceOut:
    return InvoiceOut(
        id=row["id"],
        client_id=row["client_id"],
        invoice_number=row["invoice_number"],
        description=row["description"],
        amount=(Decimal(row["amount_cents"]) / 100).quantize(Decimal("0.01")),
        status=row["status"],
        issue_date=row["issue_date"],
        due_date=row["due_date"],
        paid_date=row["paid_date"],
        created_at=row["created_at"],
        client=ClientSummary(
            id=row["client_id"],
            name=row["client_name"],
            email=row["client_email"],
            company=row["client_company"],
        ),
    )


def _integrity_error_to_http(
    exc: sqlite3.IntegrityError, invoice_number: str
) -> HTTPException:
    if "invoices.invoice_number" in str(exc):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An invoice with number '{invoice_number}' already exists.",
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="This invoice conflicts with existing data and could not be saved.",
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=InvoiceOut)
def create_invoice(payload: InvoiceCreate, db: sqlite3.Connection = Depends(get_db)):
    _refresh_overdue(db)

    if not _client_exists(db, payload.client_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {payload.client_id} not found.",
        )

    # An invoice created after its due date starts out overdue.
    invoice_status = "overdue" if payload.due_date < date.today() else "pending"

    try:
        cursor = db.execute(
            """
            INSERT INTO invoices
                (client_id, invoice_number, description, amount_cents,
                 status, issue_date, due_date, paid_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                payload.client_id,
                payload.invoice_number,
                payload.description,
                _to_cents(payload.amount),
                invoice_status,
                payload.issue_date.isoformat(),
                payload.due_date.isoformat(),
            ),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise _integrity_error_to_http(exc, payload.invoice_number)

    return _row_to_invoice(_fetch_invoice(db, cursor.lastrowid))


@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    status_filter: Literal["pending", "paid", "overdue"] | None = Query(
        default=None, alias="status"
    ),
    client_id: int | None = None,
    db: sqlite3.Connection = Depends(get_db),
):
    _refresh_overdue(db)

    # The WHERE clause is built from fixed text; the values use ? placeholders.
    clauses: list[str] = []
    params: list = []
    if status_filter is not None:
        clauses.append("i.status = ?")
        params.append(status_filter)
    if client_id is not None:
        clauses.append("i.client_id = ?")
        params.append(client_id)

    sql = _SELECT_INVOICE
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY i.id"

    rows = db.execute(sql, params).fetchall()
    return [_row_to_invoice(row) for row in rows]


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: sqlite3.Connection = Depends(get_db)):
    _refresh_overdue(db)
    row = _fetch_invoice(db, invoice_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found.",
        )
    return _row_to_invoice(row)


@router.put("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    _refresh_overdue(db)

    existing = _fetch_invoice(db, invoice_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found.",
        )

    # Only fields the client actually sent are updated. Omitted fields keep
    # their current values.
    sent = payload.model_dump(exclude_unset=True)

    if "client_id" in sent and not _client_exists(db, sent["client_id"]):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {sent['client_id']} not found.",
        )

    # The request may change only one date, so check the merged pair
    # against the stored invoice.
    issue = (
        payload.issue_date
        if "issue_date" in sent
        else date.fromisoformat(existing["issue_date"])
    )
    due = (
        payload.due_date
        if "due_date" in sent
        else date.fromisoformat(existing["due_date"])
    )
    if due < issue:
        raise HTTPException(
            status_code=422,
            detail="Due date cannot be earlier than issue date.",
        )

    assignments: list[str] = []
    values: list = []
    for field, column in _UPDATABLE_COLUMNS.items():
        if field not in sent:
            continue
        value = sent[field]
        if field == "amount":
            value = _to_cents(value)
        elif field in ("issue_date", "due_date"):
            value = value.isoformat()
        assignments.append(f"{column} = ?")
        values.append(value)

    if not assignments:
        return _row_to_invoice(existing)

    values.append(invoice_id)
    sql = f"UPDATE invoices SET {', '.join(assignments)} WHERE id = ?"
    try:
        db.execute(sql, values)
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise _integrity_error_to_http(
            exc, sent.get("invoice_number", existing["invoice_number"])
        )

    return _row_to_invoice(_fetch_invoice(db, invoice_id))


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(invoice_id: int, db: sqlite3.Connection = Depends(get_db)):
    _refresh_overdue(db)
    if _fetch_invoice(db, invoice_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found.",
        )
    db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{invoice_id}/mark-paid", response_model=InvoiceOut)
def mark_invoice_paid(
    invoice_id: int,
    payload: MarkPaidRequest | None = None,
    db: sqlite3.Connection = Depends(get_db),
):
    _refresh_overdue(db)

    existing = _fetch_invoice(db, invoice_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found.",
        )
    if existing["status"] == "paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice {invoice_id} is already paid.",
        )

    # No body, or no paid_date in the body, means "paid today".
    paid_on = (
        payload.paid_date
        if payload is not None and payload.paid_date is not None
        else date.today()
    )
    if paid_on < date.fromisoformat(existing["issue_date"]):
        raise HTTPException(
            status_code=422,
            detail="Payment date cannot be earlier than issue date.",
        )

    db.execute(
        "UPDATE invoices SET status = 'paid', paid_date = ? WHERE id = ?",
        (paid_on.isoformat(), invoice_id),
    )
    db.commit()
    return _row_to_invoice(_fetch_invoice(db, invoice_id))
