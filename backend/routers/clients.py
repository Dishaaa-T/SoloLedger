"""
Client endpoints: create, list, get, update and delete clients.

All SQL uses ? placeholders. Values are never placed into the SQL text.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response, status

import database
from schemas import ClientCreate, ClientOut, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])

# Maps each updatable request field to its database column. Only these
# column names can ever appear in an UPDATE statement.
_UPDATABLE_COLUMNS = {
    "name": "name",
    "email": "email",
    "phone": "phone",
    "company": "company",
    "notes": "notes",
}


def get_db():
    """Yield one database connection per request and always close it."""
    conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _row_to_client(row) -> ClientOut:
    return ClientOut(**dict(row))


def _fetch_client(db: sqlite3.Connection, client_id: int):
    return db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()


def _integrity_error_to_http(exc: sqlite3.IntegrityError) -> HTTPException:
    if "clients.email" in str(exc):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A client with this email already exists.",
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="This client conflicts with existing data and could not be saved.",
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ClientOut)
def create_client(payload: ClientCreate, db: sqlite3.Connection = Depends(get_db)):
    try:
        cursor = db.execute(
            "INSERT INTO clients (name, email, phone, company, notes) VALUES (?, ?, ?, ?, ?)",
            (payload.name, payload.email, payload.phone, payload.company, payload.notes),
        )
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise _integrity_error_to_http(exc)

    return _row_to_client(_fetch_client(db, cursor.lastrowid))


@router.get("", response_model=list[ClientOut])
def list_clients(db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM clients ORDER BY id").fetchall()
    return [_row_to_client(row) for row in rows]


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, db: sqlite3.Connection = Depends(get_db)):
    row = _fetch_client(db, client_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found.",
        )
    return _row_to_client(row)


@router.put("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: sqlite3.Connection = Depends(get_db),
):
    existing = _fetch_client(db, client_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found.",
        )

    # Only fields the client actually sent are updated. Omitted fields keep
    # their current values. An explicit null clears an optional field.
    sent = payload.model_dump(exclude_unset=True)
    assignments: list[str] = []
    values: list = []
    for field, column in _UPDATABLE_COLUMNS.items():
        if field in sent:
            assignments.append(f"{column} = ?")
            values.append(sent[field])

    if not assignments:
        return _row_to_client(existing)

    values.append(client_id)
    sql = f"UPDATE clients SET {', '.join(assignments)} WHERE id = ?"
    try:
        db.execute(sql, values)
        db.commit()
    except sqlite3.IntegrityError as exc:
        db.rollback()
        raise _integrity_error_to_http(exc)

    return _row_to_client(_fetch_client(db, client_id))


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id: int, db: sqlite3.Connection = Depends(get_db)):
    if _fetch_client(db, client_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found.",
        )
    try:
        db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        db.commit()
    except sqlite3.IntegrityError:
        # invoices.client_id uses ON DELETE RESTRICT, so this client has invoices.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot delete this client because they have invoices. "
                "Delete or reassign those invoices first."
            ),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
