SoloLedger
SoloLedger is a small-business finance management web application
that brings client, invoice, expense, and cash-flow information
together. It also provides a What-If Simulator and an Action Centre to
help users identify financial situations that may need attention.
This README is based on the project features and setup confirmed
during development. Please verify dependency files and final team
contributions before publishing.

Table of Contents
- Overview
- Key Features
- Technology Stack
- Project Structure
- Getting Started
- Running the Application
- API Endpoints
- Typical Workflow
- Team Contributions
- Contributing
- License
Overview
Managing business finances across separate tools can make it difficult
to track unpaid invoices, upcoming expenses, and future cash
availability. SoloLedger provides a single interface for reviewing these
records and exploring projected cash-flow scenarios.

The application uses a React frontend, a Python FastAPI backend, and an
SQLite database.
Key Features
- Dashboard: Central overview of business and financial
  information.
- Client Management: View client records retrieved from the
  backend.
- Invoice Management: Review invoices and their payment statuses,
  including paid, pending, and overdue.
- Expense Management: Review expenses and distinguish paid from
  upcoming expenses.
- Cash Flow Forecast: View expected income, expected expenses,
  projected closing balance, and the lowest projected balance over a
  forecast period.
- What-If Simulator: Explore scenarios such as delaying an unpaid
  invoice, adding an unexpected expense, or including additional
  income.
- Action Centre: View alerts such as overdue invoice payments,
  projected low cash balance, and upcoming expenses.
Technology Stack
  Layer               Technology
  Frontend            React
Frontend tooling    Vite
HTTP client         Axios
Backend             Python, FastAPI
Database            SQLite
API documentation   FastAPI Swagger UI
Project Structure
SoloLedger/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── schemas.py
│   ├── routers/
│   │   ├── action_centre.py
│   │   ├── clients.py
│   │   ├── dashboard.py
│   │   ├── expenses.py
│   │   ├── forecast.py
│   │   ├── invoices.py
│   │   ├── settings.py
│   │   └── simulator.py
│   └── services/
│       ├── action_centre.py
│       ├── dashboard.py
│       ├── forecast.py
│       └── simulator.py
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── pages/
    │   ├── services/
    │   │   └── api.js
    │   ├── App.jsx
    │   └── App.css
    ├── package.json
    └── vite.config.js
Getting Started
Prerequisites
- Python 3
- Node.js and npm
- Git
1. Clone the repository
git clone https://github.com/Dishaaa-T/SoloLedger.git
cd SoloLedger
2. Set up and run the backend
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
py -m uvicorn main:app --reload
The backend runs at http://127.0.0.1:8000.

Interactive API documentation is available at
http://127.0.0.1:8000/docs.

If the repository does not include requirements.txt, install the
backend dependencies listed by the project before starting the server.
Do not assume the fallback package list is complete.
3. Set up and run the frontend
Open a second terminal from the project root:
cd frontend
npm install
npm run dev
Open the local URL printed by Vite in your browser. The default is
commonly http://localhost:5173; Vite may select another port if that
one is busy.
Running the Application
Keep both processes running in separate terminals.

Backend:
cd backend
py -m uvicorn main:app --reload
Frontend:
cd frontend
npm run dev
API Endpoints
The frontend calls the backend through the Axios service module at
frontend/src/services/api.js.

  Purpose                Method   Endpoint
  Dashboard summary      GET      /dashboard/summary
Clients                GET      /clients
Invoices               GET      /invoices
Expenses               GET      /expenses
Create expense         POST     /expenses
Delete expense         DELETE   /expenses/{id}
Current balance        GET      /settings/balance
Cash-flow forecast     GET      /forecast/cashflow
Action Centre alerts   GET      /action-centre
What-If simulation     POST     /simulator/what-if

Use http://127.0.0.1:8000/docs for the current request parameters,
response schemas, and interactive API testing.
Typical Workflow
1. Open the dashboard to review the financial overview.
2. Check clients and invoices to identify outstanding payments.
3. Review expenses, including upcoming payments.
4. Open Cash Flow to inspect the projected balance.
5. Use the What-If Simulator to test a possible payment delay,
   unexpected expense, or additional income.
6. Review the Action Centre for alerts that may need attention.
Team Contributions
The project is developed collaboratively.
- Disha (Dishaaa-T): Repository owner and project collaborator.
- Gunjan (GunjanTathed): Frontend development, API integration,
  and updates to application pages and the Action Centre.
Update this section to reflect the final contribution split agreed by
the team.
Contributing
1. Create a feature branch.
2. Make focused changes.
3. Test the frontend and backend locally.
4. Commit with a descriptive commit message.
5. Open a Pull Request for review.
Avoid committing local database files, Python cache files, virtual
environments, or node_modules.
License
Add the license selected by the project maintainers before distributing
or reusing this project.