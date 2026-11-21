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


---

## Request 6: Feature 5, Settings and cash balance

**Created:**
- `backend/routers/settings.py`: endpoints to read settings, read the cash balance and update the cash balance.
- `backend/tests/test_settings.py`: automated tests using a temporary database (the real `sololedger.db` is not touched).

**Modified:**
- `backend/database.py`: `init_db()` sets `currency` to `INR` if it is missing. Nothing else changed.
- `backend/schemas.py`: added `SettingsOut`, `BalanceOut` (an alias of `SettingsOut`, since both have the same fields) and `BalanceUpdate`. Other models are unchanged.
- `backend/main.py`: includes the settings router next to the other routers.

**Storage (existing `settings` table, no new table):**

| Key | Value |
|---|---|
| `cash_balance_cents` | Balance in cents as a string, for example `"425000"` (seeded as 4250.00 INR) |
| `currency` | `"INR"` |
| `balance_updated_at` | ISO 8601 UTC time of the last manual update. Not set on a fresh database, so it is `null` until the balance is updated through the API. |

**Behaviour notes:**
- The balance is entered by hand. Creating, updating or deleting invoices and expenses does not change it.
- `current_cash` is INR with 2 decimal places, returned as a JSON number (for example `4250.0`).
- Currency is fixed to INR. There is no endpoint to change it. A request body that includes `currency` (or any other extra field) is rejected with 422.
- `PUT /settings/balance` accepts integers and decimals with at most 2 places. Negative values, values above 10,000,000, more than 2 decimal places, null, and non-numbers are rejected with 422.
- A missing `cash_balance_cents` is read as 0.

**Endpoints:**

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | `/settings` | 200 | |
| GET | `/settings/balance` | 200 | |
| PUT | `/settings/balance` | 200 | 422 invalid input, 500 if the database write fails |

**Example body (PUT /settings/balance):**
```json
{
  "current_cash": 65000
}
```

**Example response:**
```json
{
  "current_cash": 65000.0,
  "currency": "INR",
  "updated_at": "2026-05-20T10:15:00+00:00"
}
```

**How to test with automated tests:**
```
venv\Scripts\python.exe -m pytest tests -q
```
Expected: all tests pass, including the client, invoice and expense tests from earlier requests.

**How to test manually in Swagger UI:**
1. Start the server:
   ```
   venv\Scripts\activate
   uvicorn main:app --reload
   ```
2. Open http://127.0.0.1:8000/docs
3. Checks to run:
   - GET `/settings/balance` returns 200 with `current_cash` 4250.0 on a fresh database.
   - PUT `/settings/balance` with the example body returns 200, and a following GET returns 65000.0.
   - PUT with `"current_cash": -1` or `"current_cash": 10.123` returns 422.
   - PUT with `"current_cash": 100, "currency": "USD"` returns 422.
   - Creating an expense does not change the balance.


---

## Request 7: Feature 6, Smart financial dashboard API

**Created:**
- `backend/routers/dashboard.py`: endpoint `GET /dashboard/summary`.
- `backend/services/__init__.py`: empty package marker.
- `backend/services/dashboard.py`: period boundaries and SQL aggregation for every metric.
- `backend/tests/test_dashboard.py`: automated tests using a temporary database (the real `sololedger.db` is not touched). Each test deletes the seeded sample rows first, then inserts its own rows.

**Modified:**
- `backend/schemas.py`: added `DashboardPeriod` (a Literal) and `DashboardSummaryOut`. Other models are unchanged.
- `backend/main.py`: includes the dashboard router next to the other routers.

**Endpoint:**

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | `/dashboard/summary?period=this_month\|last_month\|all_time` | 200 | 422 for any other period value (default `this_month`), 500 if the database read fails |

**Metric definitions (all values are INR, 2 decimal places, JSON numbers):**
- `total_income`: paid invoices, by `paid_date`, inside the period.
- `total_expenses`: all recorded expenses (both `paid` and `upcoming` statuses), by `expense_date`, inside the period.
- `net_profit`: `total_income` minus `total_expenses`. Can be negative.
- `pending_payments`: every unpaid invoice (status `pending` or `overdue`), all time, not filtered by period.
- `overdue_payments`: unpaid invoices that are marked `overdue` or whose `due_date` is before today, all time. Paid invoices never count. This is a subset of `pending_payments`.
- `available_cash`: the cash balance stored in settings. It is not computed from invoices or expenses.

**Period rules:**
- `this_month`: first to last day of the current month.
- `last_month`: first to last day of the previous month (January goes back to December of the previous year).
- `all_time`: no date filter.

**Example response (example only, not real data):**
```json
{
  "period": "this_month",
  "currency": "INR",
  "total_income": 45000.0,
  "total_expenses": 12000.0,
  "net_profit": 33000.0,
  "pending_payments": 18000.0,
  "overdue_payments": 5000.0,
  "available_cash": 65000.0
}
```

**How to test with automated tests:**
```
venv\Scripts\python.exe -m pytest tests -q
```
Expected: all tests pass, including the client, invoice, expense and settings tests from earlier requests.

**How to test manually in Swagger UI:**
1. Start the server:
   ```
   venv\Scripts\activate
   uvicorn main:app --reload
   ```
2. Open http://127.0.0.1:8000/docs
3. Checks to run:
   - GET `/dashboard/summary` with no parameters returns 200 and `period` "this_month".
   - GET `/dashboard/summary?period=last_month` and `?period=all_time` return 200.
   - GET `/dashboard/summary?period=next_year` returns 422.
   - Marking an invoice as paid changes `total_income` and `pending_payments` for the current period.
   - Creating an expense changes `total_expenses` and `net_profit` only.
   - Changing the cash balance with `PUT /settings/balance` changes `available_cash` only.

---

## Request 8: Feature 7, Cash-flow forecasting (30/60/90 days)

**Created:**
- `backend/services/forecast.py`: pure forecast logic (no FastAPI). Collects income and expense events, runs the daily balance loop in integer cents.
- `backend/routers/forecast.py`: endpoint `GET /forecast/cashflow`.
- `backend/tests/test_forecast.py`: automated tests using a temporary database (the real `sololedger.db` is not touched). Arithmetic tests use a fixed "today" (2030-01-01).

**Modified:**
- `backend/schemas.py`: added `FORECAST_DAYS`, `ForecastDayOut` and `CashflowForecastOut`. Other models are unchanged.
- `backend/main.py`: includes the forecast router next to the other routers.

**Endpoint:**

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | `/forecast/cashflow?days=30\|60\|90` | 200 | 422 for any other `days` value (default `30`), 500 if the database read fails |

`days` is validated manually in the router (not with a Literal), so the error message is exactly `days must be one of 30, 60, 90.`.

**Formula:**
- Window: today through today + days - 1.
- Projected balance(day) = balance(previous day) + income(day) - expenses(day).
- The starting balance is the `cash_balance_cents` setting (missing counts as 0).

**Assumptions:**
- Pending invoices are collected on their `due_date`.
- Overdue invoices (status `overdue`, or a pending invoice whose due date is before today) are collected on today + 7 days.
- Paid invoices are never counted.
- Only `upcoming` expenses dated today or later, inside the window, are counted. Their date is `expense_date`.
- `paid` expenses are never counted.
- No recurring expenses are invented.

**Limitation:**
- An `upcoming` expense dated before today is not counted, because it is treated as historical. If a bill is overdue but still marked `upcoming`, it will not appear in the forecast.

**Example response (illustrative only, not real data):**
```json
{
  "starting_balance": 65000.0,
  "currency": "INR",
  "forecast_days": 30,
  "expected_income": 18000.0,
  "expected_expenses": 12000.0,
  "projected_closing_balance": 71000.0,
  "lowest_projected_balance": 53000.0,
  "lowest_balance_date": "2026-06-05",
  "risk_of_negative_balance": false,
  "daily_forecast": [
    {"date": "2026-06-01", "expected_income": 0.0, "expected_expenses": 0.0, "projected_balance": 65000.0}
  ]
}
```

**How to test with automated tests:**
```
venv\Scripts\python.exe -m pytest tests -q
venv\Scripts\python.exe -m pytest tests\test_forecast.py -q
```
Expected: all tests pass, including the client, invoice, expense, settings and dashboard tests from earlier requests.

**How to test manually in Swagger UI:**
1. Start the server:
   ```
   venv\Scripts\activate
   uvicorn main:app --reload
   ```
2. Open http://127.0.0.1:8000/docs
3. Checks to run:
   - GET `/forecast/cashflow` with no parameters returns 200 and `forecast_days` 30.
   - GET `/forecast/cashflow?days=60` and `?days=90` return 200 with 60 and 90 `daily_forecast` entries.
   - GET `/forecast/cashflow?days=45` returns 422.
   - Marking an invoice as paid removes its income from the forecast.
   - Changing the cash balance with `PUT /settings/balance` changes `starting_balance` and every projected balance.

---

## Request 9: Feature 8, What-if financial simulator

**Created:**
- `backend/services/simulator.py`: rule-based what-if logic. It reads invoices, expenses and settings, builds a baseline forecast, applies scenarios to in-memory copies of the event lists, and projects both. It never writes to the database.
- `backend/routers/simulator.py`: `POST /simulator/what-if`. It converts the body and maps `SimulationError` and `ValueError` to HTTP errors.
- `backend/tests/test_simulator.py`: automated tests using a temporary database (the real `sololedger.db` is not touched).

**Modified:**
- `backend/schemas.py`: added `SimExpenseInput`, `SimIncomeInput`, `WhatIfRequest`, `ProjectionSummaryOut`, `WhatIfDayOut` and `WhatIfOut`. Existing models are unchanged.
- `backend/services/forecast.py`: the daily projection loop moved into `project_cashflow()`, so the simulator and the forecast share it. `build_cashflow_forecast()` returns the same output as before.
- `backend/main.py`: includes the simulator router.

**Scenarios:**
- A. Delayed client payment (`delay_invoice_id` + `delay_days`, 1 to 90): moves that invoice's collection date later in the simulated list only. The invoice row is not modified. A paid invoice is rejected with 422; a missing invoice with 404.
- B. Unexpected expense (`unexpected_expense`: amount, date): added to the simulated expense list only.
- C. Additional income (`additional_income`: amount, date): added to the simulated income list only.
- Dates for B and C must be between today and the last day of the window (422 otherwise).

**Rules:**
- `forecast_days` must be 30, 60 or 90.
- At least one scenario is required (422 otherwise).
- `difference` = simulated closing balance minus baseline closing balance (INR).
- `risk_of_negative_balance` refers to the simulated projection.
- Nothing is written to SQLite.

**Request example:**
```json
{
  "delay_invoice_id": 1,
  "delay_days": 15,
  "unexpected_expense": {"amount": 5000, "date": "2026-06-05"},
  "additional_income": {"amount": 10000, "date": "2026-06-10"},
  "forecast_days": 30
}
```
Use dates inside the next 30 days when you try it.

**Response shape (illustrative only, not real data):**
```json
{
  "currency": "INR",
  "forecast_days": 30,
  "baseline": {"closing_balance": 0.0, "lowest_balance": 0.0, "lowest_balance_date": "2026-06-01", "risk_of_negative_balance": false},
  "simulated": {"closing_balance": 0.0, "lowest_balance": 0.0, "lowest_balance_date": "2026-06-01", "risk_of_negative_balance": false},
  "difference": 0.0,
  "risk_of_negative_balance": false,
  "applied_scenarios": ["delay_payment", "unexpected_expense", "additional_income"],
  "daily_forecast": [
    {"date": "2026-06-01", "baseline_balance": 0.0, "simulated_balance": 0.0, "baseline_income": 0.0, "baseline_expenses": 0.0, "simulated_income": 0.0, "simulated_expenses": 0.0}
  ]
}
```

**How to test with automated tests:**
```
.\venv\Scripts\python.exe -m pytest tests -q
.\venv\Scripts\python.exe -m pytest tests\test_simulator.py -q
```
Expected: all tests pass, including the forecast and dashboard tests from earlier requests.

**How to test manually in Swagger UI:**
1. Start the server:
   ```
   .\venv\Scripts\python.exe -m uvicorn main:app --reload
   ```
2. Open http://127.0.0.1:8000/docs
3. Checks to run:
   - POST `/simulator/what-if` with only `unexpected_expense` returns 200 and `applied_scenarios` `["unexpected_expense"]`.
   - POST `{}` returns 422.
   - `delay_days` 0 or 91 returns 422.
   - `forecast_days` 45 returns 422.
   - An expense dated yesterday returns 422.
   - A `delay_invoice_id` of a paid invoice returns 422; id 9999 returns 404.
   - Running the same request twice gives the same result, and `GET /invoices` is unchanged.


---

## Request 10: Feature 9, Financial Action Centre

**Created:**
- `backend/services/action_centre.py`: rule-based alert logic. It reuses the forecast service (90-day cash-flow projection), the dashboard service (`period_bounds` for this and last month) and the settings table. It only runs SELECT queries and never writes.
- `backend/routers/action_centre.py`: endpoint `GET /action-centre`.
- `backend/tests/test_action_centre.py`: automated tests using a temporary database (the real `sololedger.db` is not touched). Service tests use a fixed today (2030-01-15).

**Modified:**
- `backend/schemas.py`: added the Action Centre response models and the priority and category literals. Other models are unchanged.
- `backend/main.py`: includes the action centre router next to the other routers.

**Endpoint:**

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | `/action-centre?priority=critical\|high\|medium\|low&category=overdue_payment\|pending_payment\|low_cash_flow\|negative_cash_flow\|upcoming_expense\|expense_trend` | 200 | 422 for any other `priority` or `category` value, 500 if the database read fails |

Both filters are optional. The summary counts are taken from the filtered alerts, so `summary.total_alerts` always equals `len(alerts)`.

**Alert fields:** `id`, `title`, `description`, `category`, `priority`, `amount` (INR, 2 decimal places), `related_date`, `recommended_action`, `related_invoice_id`, `related_expense_id`, `reason`.

**Summary fields:** `total_alerts`, `critical`, `high`, `medium`, `low`.

**Rules:**
- Overdue invoices (one alert per invoice): an unpaid invoice whose status is `overdue` or whose due date is before today. Priority is `critical` at 30 or more days overdue; `high` at 7 or more days overdue, or at INR 50,000 or more; otherwise `medium`.
- Pending payments (one summary alert): unpaid `pending` invoices not yet due. Priority is `medium` if the earliest due date is within 7 days, otherwise `low`. Overdue invoices are not included here.
- Cash flow: uses the 90-day forecast. A projected balance below zero gives a `critical` `negative_cash_flow` alert. This takes precedence over the low-cash alert, so only one of the two can appear.
- Low cash: a projected minimum below the threshold gives a `high` `low_cash_flow` alert. The threshold comes from the settings key `low_cash_threshold_cents` (default INR 5,000). This key is read-only here; no API writes it.
- Upcoming expenses (one alert per expense): `upcoming` expenses dated today through today + 89. Priority is `high` if due within 7 days, otherwise `medium`. Paid expenses and past-dated upcoming expenses are not included.
- Expense trend: an alert only when last month's total is non-zero and this month's total is at least 20% higher. Priority is `medium`. The recommended action names the category with the largest increase.
- Sorting: priority (critical, high, medium, low), then earliest related date, then id.

**Example response (illustrative only, not real data):**
```json
{
  "summary": {"total_alerts": 2, "critical": 1, "high": 1, "medium": 0, "low": 0},
  "alerts": [
    {
      "id": "overdue_invoice_3",
      "title": "Invoice payment overdue",
      "description": "Invoice INV-2026-004 for Acme Ltd of INR 18,000.00 is 35 day(s) overdue.",
      "category": "overdue_payment",
      "priority": "critical",
      "amount": 18000.0,
      "related_date": "2026-04-01",
      "recommended_action": "Escalate: contact Acme Ltd today about invoice INV-2026-004 and agree a payment date.",
      "related_invoice_id": 3,
      "related_expense_id": null,
      "reason": "Unpaid and due date 2026-04-01 is before today 2026-05-06."
    }
  ]
}
```

**How to test with automated tests:**
```
.\venv\Scripts\python.exe -m pytest tests -q
.\venv\Scripts\python.exe -m pytest tests\test_action_centre.py -q
```
Expected: all tests pass, including the simulator, forecast, dashboard and earlier tests.

**How to test manually in Swagger UI:**
1. Start the server:
   ```
   .\venv\Scripts\python.exe -m uvicorn main:app --reload
   ```
2. Open http://127.0.0.1:8000/docs
3. Checks to run:
   - GET `/action-centre` with no parameters returns 200 with `summary` and `alerts`.
   - GET `/action-centre?priority=critical` returns only critical alerts, and `summary.total_alerts` equals the number of alerts returned.
   - GET `/action-centre?category=overdue_payment` returns only overdue payment alerts.
   - GET `/action-centre?priority=urgent` and `?category=unknown` return 422.
   - Marking an overdue invoice as paid removes its overdue alert.



