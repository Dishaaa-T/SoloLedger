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

---

## Request 4: Feature 3, Invoice management

**Created:**
- `backend/routers/invoices.py`: endpoints for create, list (with filters), get, update, delete and mark-paid.
- `backend/tests/test_invoices.py`: automated tests using a temporary database (the real `sololedger.db` is not touched).

**Modified:**
- `backend/schemas.py`: added `InvoiceCreate`, `InvoiceUpdate`, `MarkPaidRequest`, `ClientSummary` and `InvoiceOut`. The existing client models are unchanged.
- `backend/main.py`: includes the invoices router next to the clients router.

**Behaviour notes:**
- `amount` is entered and returned in INR (for example `25000.00`), with at most 2 decimal places. It is stored as integer cents (`amount_cents`). It is returned as a JSON number (for example `25000.0`).
- Each invoice response includes a nested `client` object (id, name, email, company).
- Overdue status is refreshed automatically on every read and write: a `pending` invoice whose `due_date` is before today becomes `overdue`. `paid` invoices are never changed.
- Creating an invoice with a past due date sets its status to `overdue` straight away.
- `POST /invoices/{id}/mark-paid` with no body sets `paid_date` to today.
- Cash balances and the settings table are not changed by invoice endpoints.

**Endpoints:**

| Method | Path | Success | Errors |
|---|---|---|---|
| POST | `/invoices` | 201 | 404 client not found, 409 duplicate invoice number, 422 invalid input |
| GET | `/invoices` | 200 | optional `status` (pending, paid, overdue) and `client_id` filters |
| GET | `/invoices/{invoice_id}` | 200 | 404 not found |
| PUT | `/invoices/{invoice_id}` | 200 | 404 not found or client not found, 409 duplicate invoice number, 422 invalid input or due date before issue date |
| DELETE | `/invoices/{invoice_id}` | 204 | 404 not found |
| POST | `/invoices/{invoice_id}/mark-paid` | 200 | 404 not found, 409 already paid, 422 payment date before issue date |

**Example body (POST /invoices):**
```json
{
  "client_id": 1,
  "invoice_number": "INV-2026-100",
  "description": "Logo redesign",
  "amount": 25000.00,
  "issue_date": "2026-05-01",
  "due_date": "2026-05-31"
}
```

**How to test with automated tests:**
```
venv\Scripts\python.exe -m pytest tests -q
```
Expected: all tests pass, including the client tests from Request 3.

**How to test manually in Swagger UI:**
1. Start the server:
   ```
   venv\Scripts\activate
   uvicorn main:app --reload
   ```
2. Open http://127.0.0.1:8000/docs
3. Checks to run:
   - POST `/invoices` with the example body above returns 201 and `status` "pending" (use a future due date).
   - POST with `"amount": 0` returns 422. POST with `"amount": 10.123` returns 422.
   - POST with a `client_id` that does not exist (for example 9999) returns 404.
   - POST the same `invoice_number` twice returns 409 on the second call.
   - GET `/invoices?status=pending` returns only pending invoices.
   - PUT `/invoices/{id}` with `{"description": "New text"}` changes only the description.
   - POST `/invoices/{id}/mark-paid` with no body returns 200, `status` "paid", and today's `paid_date`. Repeating it returns 409.
   - POST `/invoices` with `issue_date` 60 days ago and `due_date` 30 days ago returns status "overdue" (or GET it later to confirm).
   - DELETE `/invoices/{id}` returns 204, and a following GET returns 404.

---

## Request 5: Feature 4, Expense management

**Created:**
- `backend/routers/expenses.py`: endpoints for create, list (with filters), get, update and delete.
- `backend/tests/test_expenses.py`: automated tests using a temporary database (the real `sololedger.db` is not touched).

**Modified:**
- `backend/database.py`: `expenses` gets three new columns, `title`, `payment_method` and `notes`, added only if missing. Existing expense rows get their `title` copied from `description` (only where `title` is still empty), so re-running the server changes nothing.
- `backend/schemas.py`: added `PaymentMethod`, `ExpenseCreate`, `ExpenseUpdate` and `ExpenseOut`. The client and invoice models are unchanged.
- `backend/main.py`: includes the expenses router next to the clients and invoices routers.

**Behaviour notes:**
- `amount` is entered and returned in INR (for example `1250.00`), with at most 2 decimal places. It is stored as integer cents (`amount_cents`). It is returned as a JSON number (for example `1250.0`).
- `status` ("paid" or "upcoming") is computed automatically from `expense_date`: a date today or earlier is "paid", a later date is "upcoming". It is recalculated on every create and update. It is stored in the database; the API responses do not include it.
- A blank `description` is stored as an empty string and returned as `null`.
- Category is free text (1 to 60 characters). The list below is the suggested set; the API does not reject other values, because the seeded expenses use older category names.
- Category filtering ignores case, so `travel` and `Travel` match the same expenses.
- `GET /expenses` returns newest expense date first.

**Allowed categories (suggested):** Software & Subscriptions, Internet & Utilities, Equipment, Travel, Marketing, Office Supplies, Professional Services, Other

**Payment methods (optional):** cash, upi, card, bank_transfer, other

**Endpoints:**

| Method | Path | Success | Errors |
|---|---|---|---|
| POST | `/expenses` | 201 | 422 invalid input |
| GET | `/expenses` | 200 | optional `category`, `start_date` and `end_date` filters; 422 for a blank category or `start_date` after `end_date` |
| GET | `/expenses/{expense_id}` | 200 | 404 not found |
| PUT | `/expenses/{expense_id}` | 200 | 404 not found, 422 invalid input |
| DELETE | `/expenses/{expense_id}` | 204 | 404 not found |

**Example body (POST /expenses):**
```json
{
  "title": "Figma subscription",
  "description": "Monthly design tool plan",
  "amount": 1250.00,
  "category": "Software & Subscriptions",
  "expense_date": "2026-05-02",
  "payment_method": "card",
  "notes": "Business card ending 4411"
}
```

**How to test with automated tests:**
```
venv\Scripts\python.exe -m pytest tests -q
```
Expected: all tests pass, including the client and invoice tests from earlier requests.

**How to test manually in Swagger UI:**
1. Start the server:
   ```
   venv\Scripts\activate
   uvicorn main:app --reload
   ```
2. Open http://127.0.0.1:8000/docs
3. Checks to run:
   - POST `/expenses` with the example body above returns 201.
   - POST with `"title": "   "` returns 422. POST with `"amount": 0` or `"amount": 10.123` returns 422.
   - POST with `"payment_method": "bitcoin"` returns 422.
   - GET `/expenses?category=travel` returns the same results as `category=Travel`.
   - GET `/expenses?start_date=2026-05-01&end_date=2026-05-31` returns only expenses dated in May 2026.
   - GET `/expenses?start_date=2026-06-01&end_date=2026-05-01` returns 422.
   - PUT `/expenses/{id}` with `{"amount": 900}` changes only the amount.
   - DELETE `/expenses/{id}` returns 204, and a following GET returns 404.


