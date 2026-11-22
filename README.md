# SoloLedger

**A personal finance and cash-flow tool for solo freelancers.**

---

## Introduction

Freelancing is rewarding, but the money side is often messy. You juggle invoices, clients who pay late, irregular income, and recurring expenses, and it's hard to know whether next month's cash will cover your costs.

SoloLedger puts all of that in one place. It helps you see who owes you money, where your money goes, and what your cash position is likely to look like in the coming weeks, so you can act before problems show up.

---

## How it helps freelancers

- **Know who owes you money.** See every client's invoices at a glance and which ones are overdue. An invoice is marked overdue automatically once its due date passes.
- **Understand where your money goes.** Track expenses by category and payment method (cash, UPI, card, bank transfer, or other), so your business costs are visible instead of scattered.
- **See trouble coming.** A 30/60/90-day cash forecast flags negative-balance risk before it happens.
- **Plan for the unexpected.** Run "what if" scenarios: an invoice paid late, an unexpected expense, or some extra income.
- **Judge client payment risk.** Each client gets a payment-risk score to help you decide how much to trust their payment timing.
- **Focus on what matters.** A prioritised Action Centre collects alerts so you know what to handle first.

---

## Features

### Clients and invoices
- Manage clients and their invoices.
- Invoices have clear statuses: **pending**, **paid**, and **overdue**.
- Mark an invoice as paid with a single action.

### Expenses
- Record business expenses by **category**.
- Choose a **payment method** for each expense.
- Mark expenses as **paid** or **upcoming**.

### Cash position
- Enter your current balance manually.
- View a **30/60/90-day cash forecast** based on your balance, invoices, and expenses.

### What-if simulator
- Test scenarios such as **delayed invoices**, **unexpected expenses**, and **extra income**.
- See how each scenario would change your projected cash position.

### Payment risk
- Get a **per-client payment-risk prediction** powered by a RandomForest model.
- The model is trained on **synthetic data**, so treat its output as **indicative**, not authoritative.

### Action Centre
- Rule-based alerts highlight issues that need attention.
- Alerts are **sorted by priority**, so the most important items come first.

### Dashboard summary
- A quick overview of your key numbers in one view.

---

## Tech stack

**Backend**
- Python
- FastAPI
- Uvicorn
- SQLite (the database file is created automatically)
- scikit-learn
- joblib
- Money is stored as **integer cents** to avoid floating-point rounding errors.

**Frontend**
- React 19
- Vite
- react-router-dom
- Tailwind CSS
- recharts
- axios

---

## Getting started (Windows)

### Prerequisites

- [Python 3](https://www.python.org/downloads/)
- [Node.js](https://nodejs.org/) (includes npm)

### 1. Start the backend

Open a terminal (Command Prompt or PowerShell) in the project folder and run:

```bat
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at **http://127.0.0.1:8000**.

*Optional:* To initialise the database without starting the server, run:

```bat
python database.py
```

### 2. Start the frontend

Open a **second** terminal in the project folder and run:

```bat
cd frontend
npm install
npm run dev
```

The app will usually be available at **http://localhost:5173**.

*Optional:* If your API runs somewhere other than the default, create a `.env` file in the `frontend` folder and set:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

If `VITE_API_BASE_URL` is not set, the frontend uses `http://127.0.0.1:8000`.

### API documentation

With the backend running, interactive API docs are available at **http://127.0.0.1:8000/docs**.

### Other frontend scripts

The frontend also includes `build`, `lint`, and `preview` scripts, run with `npm run build`, `npm run lint`, and `npm run preview`.

---

## API overview

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/` | Root / health check |
| GET | `/clients` | List clients |
| POST | `/clients` | Create a client |
| GET | `/clients/{id}` | Get a client |
| PUT | `/clients/{id}` | Update a client |
| DELETE | `/clients/{id}` | Delete a client |
| GET | `/clients/{id}/payment-risk` | Get a client's payment-risk prediction |
| GET | `/invoices` | List invoices (filters: `status`, `client_id`) |
| POST | `/invoices` | Create an invoice |
| GET | `/invoices/{id}` | Get an invoice |
| PUT | `/invoices/{id}` | Update an invoice |
| DELETE | `/invoices/{id}` | Delete an invoice |
| POST | `/invoices/{id}/mark-paid` | Mark an invoice as paid |
| GET | `/expenses` | List expenses (filters: `category`, `start_date`, `end_date`) |
| POST | `/expenses` | Create an expense |
| GET | `/expenses/{id}` | Get an expense |
| PUT | `/expenses/{id}` | Update an expense |
| DELETE | `/expenses/{id}` | Delete an expense |
| GET | `/settings` | Get settings |
| GET | `/settings/balance` | Get the current balance |
| PUT | `/settings/balance` | Set the current balance |
| GET | `/dashboard/summary` | Get the dashboard summary |
| GET | `/forecast/cashflow` | Get the 30/60/90-day cash forecast |
| POST | `/simulator/what-if` | Run a what-if scenario |
| GET | `/action-centre` | Get prioritised alerts |

---

## Sample data

SoloLedger seeds a few example clients so you can explore the app right away:

- Brightwave Labs
- Northpine Creative
- Maple & Thread
- Sam Okafor

**All data in the project is fictional.**

---

## Project structure

- `backend/` - The FastAPI app: API routes, database setup, and the payment-risk model.
- `frontend/` - The React app (built with Vite) that provides the user interface.

---

## Notes / limitations

- The payment-risk model is trained on **synthetic data**, so its predictions are indicative only.
- The balance is currently set through the API (`PUT /settings/balance`); there is no dedicated settings page yet.
- This is an early-stage project and may change significantly.

---


