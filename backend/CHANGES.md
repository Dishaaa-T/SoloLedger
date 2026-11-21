# SoloLedger Backend: Change Log

This file records every change made to the backend, one section per request, with instructions for testing each feature.

All commands assume you are in `D:\SoloLedger\backend` unless stated otherwise.

---

## Request 1: Backend folder structure

**Created (empty placeholders):**
- `backend/main.py`
- `backend/database.py`
- `backend/requirements.txt`
- `backend/.env`

**Created:**
- `backend/venv/`: Python virtual environment (`python -m venv venv`).

`sololedger.db` is not created here. It is created automatically when the database is first initialized (Request 2).

**How to test:**
```
dir backend
dir backend\venv\Scripts\python.exe
```
You should see the four files and `venv\Scripts\python.exe`.

---

## Request 2: Feature 1, Database setup

**Modified:**
- `backend/database.py`: full implementation.

**What it does:**
- `DB_PATH` points to `backend/sololedger.db`, created automatically on first run.
- `get_connection()` opens SQLite with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`.
- `init_db()` creates tables and indexes with `IF NOT EXISTS`, inside one transaction. It is safe to run on every server start.
- Sample data is seeded only once, guarded by the `sample_data_seeded` setting.

**Tables:**
- `settings` (key, value): stores `cash_balance_cents` (default 425000) and `sample_data_seeded`.
- `clients` (id, name, email UNIQUE, company, created_at).
- `invoices` (id, client_id FK, invoice_number UNIQUE, description, amount_cents, status in pending/paid/overdue, issue_date, due_date, paid_date, created_at). Constraints: due date not before issue date; `paid` requires a `paid_date`.
- `expenses` (id, category, description, amount_cents, expense_date, status in upcoming/paid, created_at).

**Sample data:** 4 clients, 8 invoices (4 paid, 2 overdue, 2 pending), 6 expenses (2 paid, 4 upcoming).

**How to test:**
1. Initialize the database:
   ```
   venv\Scripts\python.exe database.py
   ```
   Expected output: `Database ready at ...\backend\sololedger.db`
2. Run it a second time. The output must be the same, and the row counts below must not change.
3. Check the row counts:
   ```
   venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('sololedger.db'); [print(t, c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]) for t in ['clients','invoices','expenses','settings']]"
   ```
   Expected: clients 4, invoices 8, expenses 6, settings 2 (at least).

---

## Request 3: Feature 2, Client management

**Created:**
- `backend/schemas.py`: Pydantic models `ClientCreate`, `ClientUpdate`, `ClientOut`. Validates non-empty names, email format, phone format (7+ digits, allowed symbols only), and length limits.
- `backend/routers/__init__.py`: empty package marker.
- `backend/routers/clients.py`: endpoints for create, list, get, update, delete.
- `backend/tests/__init__.py`: empty package marker.
- `backend/tests/test_clients.py`: automated tests using a temporary database (the real `sololedger.db` is not touched).

**Modified:**
- `backend/database.py`: added `_add_missing_columns()`, which adds the `phone` and `notes` columns to `clients` if they are missing. No existing data is deleted or changed.
- `backend/main.py`: FastAPI app with a lifespan hook that runs `init_db()` on startup, CORS for `http://localhost:5173`, and a root route `GET /`.
- `backend/requirements.txt`: added `pytest` and `httpx`.

**Endpoints:**

| Method | Path | Success | Errors |
|---|---|---|---|
| POST | `/clients` | 201 | 409 duplicate email, 422 invalid input |
| GET | `/clients` | 200 | |
| GET | `/clients/{client_id}` | 200 | 404 not found |
| PUT | `/clients/{client_id}` | 200 | 404 not found, 409 duplicate email, 422 invalid input |
| DELETE | `/clients/{client_id}` | 204 | 404 not found, 409 client has invoices |

**Example body (POST):**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "phone": "+1 555 010 2030",
  "company": "Doe Studio",
  "notes": "Prefers email"
}
```
Only `name` is required.

**How to test with automated tests:**
```
venv\Scripts\python.exe -m pytest tests -q
```
Expected: all tests pass (15 passed, with one harmless deprecation warning from TestClient).

**How to test manually in Swagger UI:**
1. Start the server:
   ```
   venv\Scripts\activate
   uvicorn main:app --reload
   ```
2. Open http://127.0.0.1:8000/docs
3. For each endpoint, click "Try it out", edit the request, then click "Execute".
4. Checks to run:
   - POST with `"name": "   "` returns 422.
   - POST with `"email": "not-an-email"` returns 422.
   - POST the same email twice returns 409 on the second call.
   - PUT with `{"phone": null}` clears the phone number.
   - GET `/clients/9999` returns 404.
   - DELETE a seeded client that has invoices (for example, id 1) returns 409.
   - DELETE a newly created client with no invoices returns 204, and a following GET returns 404.

---

## Known limitations
- Live server and Swagger checks have not been run by the developer yet; the automated tests cover the same endpoints.
- Email uniqueness relies on the database `UNIQUE` constraint, so duplicates return 409.
