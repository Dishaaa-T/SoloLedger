"""
SoloLedger database module.

Responsibilities:
- Decide where the SQLite file lives (DB_PATH).
- Open connections with safe defaults (get_connection).
- Create tables and indexes if they do not exist yet (init_db).
- Insert sample data exactly once, so restarts never duplicate it.

Only the Python standard library is used: sqlite3, pathlib, datetime.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

# The database file sits next to this module, e.g. backend/sololedger.db.
# SQLite creates the file automatically the first time we connect.
DB_PATH = Path(__file__).resolve().parent / "sololedger.db"


def get_connection() -> sqlite3.Connection:
    """Open a new connection to the SoloLedger database.

    - row_factory = sqlite3.Row lets us read columns by name (row["email"]).
    - PRAGMA foreign_keys = ON is per-connection in SQLite, so we turn it
      on every time we connect. Without it, foreign keys are not enforced.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    """Return the value stored under `key` in the settings table, or None."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?",
        (key,),
    ).fetchone()
    return row["value"] if row is not None else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Insert or update a key-value pair in the settings table."""
    # ON CONFLICT ... DO UPDATE = "insert, but if the key already exists, update it".
    conn.execute(
        """
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    """Add columns that newer versions need, if they are missing.

    - clients: phone and notes.
    - expenses: title, payment_method and notes. Existing rows get their
      title copied from description (only where title is still NULL, so
      running this again changes nothing).

    Runs inside init_db()'s transaction. ALTER TABLE ... ADD COLUMN is
    cheap and keeps existing rows intact.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(clients)")}
    if "phone" not in existing:
        conn.execute("ALTER TABLE clients ADD COLUMN phone TEXT")
    if "notes" not in existing:
        conn.execute("ALTER TABLE clients ADD COLUMN notes TEXT")

    existing = {row["name"] for row in conn.execute("PRAGMA table_info(expenses)")}
    if "title" not in existing:
        conn.execute("ALTER TABLE expenses ADD COLUMN title TEXT")
    if "payment_method" not in existing:
        conn.execute("ALTER TABLE expenses ADD COLUMN payment_method TEXT")
    if "notes" not in existing:
        conn.execute("ALTER TABLE expenses ADD COLUMN notes TEXT")
    # One-time backfill: old expenses have no title, so use their description.
    conn.execute("UPDATE expenses SET title = description WHERE title IS NULL")


def init_db() -> None:
    """Create all tables and indexes, and seed sample data once.

    Safe to call on every server start: every statement uses
    IF NOT EXISTS, and sample data is guarded by a settings flag.
    All work happens in ONE transaction, so either everything
    succeeds or nothing is changed.
    """
    conn = get_connection()
    try:
        # Start a transaction manually. This makes table creation and
        # seeding all-or-nothing, including the CREATE TABLE statements.
        conn.execute("BEGIN")

        # --- 1. Tables -------------------------------------------------

        # settings: a simple key-value store for app-wide values.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        # clients: the people or companies that pay us.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL CHECK (length(trim(name)) > 0),
                email      TEXT UNIQUE,
                company    TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # invoices: money we are owed (or have been paid).
        # Amounts are stored in cents to avoid floating-point rounding errors.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id      INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
                invoice_number TEXT NOT NULL UNIQUE,
                description    TEXT,
                amount_cents   INTEGER NOT NULL CHECK (amount_cents > 0),
                status         TEXT NOT NULL CHECK (status IN ('pending', 'paid', 'overdue')),
                issue_date     TEXT NOT NULL,
                due_date       TEXT NOT NULL,
                paid_date      TEXT,
                created_at     TEXT NOT NULL DEFAULT (datetime('now')),
                CHECK (due_date >= issue_date),
                -- A invoice is 'paid' if and only if it has a paid_date.
                CHECK ((status = 'paid') = (paid_date IS NOT NULL))
            )
            """
        )

        # expenses: money we spend (or plan to spend).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                category     TEXT NOT NULL,
                description  TEXT NOT NULL,
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                expense_date TEXT NOT NULL,
                status       TEXT NOT NULL CHECK (status IN ('upcoming', 'paid')),
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # --- 2. Indexes (speed up common lookups) ----------------------
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_invoices_client_id ON invoices (client_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices (status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses (status)"
        )

        # --- 3. Sample data (only once) --------------------------------
        # If the flag is missing, this is the first run: seed the data.
        if get_setting(conn, "sample_data_seeded") is None:
            _seed_sample_data(conn)

        # Preferred currency. Fixed to INR for now; set only if missing.
        if get_setting(conn, "currency") is None:
            set_setting(conn, "currency", "INR")

        # --- 4. Column migrations (after seeding, so seeded expenses get titles)
        # Adds missing columns to clients and expenses, and backfills titles.
        _add_missing_columns(conn)

        # Commit everything: tables, indexes and seed data together.
        conn.commit()

    except sqlite3.Error as exc:
        # Something went wrong: undo every change made in this transaction.
        conn.rollback()
        raise RuntimeError(f"Database initialization failed: {exc}") from exc

    finally:
        # The connection is not closed automatically, so always close it.
        conn.close()


def _seed_sample_data(conn: sqlite3.Connection) -> None:
    """Insert fictional sample clients, invoices and expenses.

    Dates are computed from today so the data always looks realistic:
    some invoices are paid, some pending, some overdue, and some
    expenses are upcoming.
    """
    today = date.today()

    def days_from_today(offset: int) -> str:
        """Return an ISO 'YYYY-MM-DD' string offset days from today."""
        return (today + timedelta(days=offset)).isoformat()

    # --- Clients ---------------------------------------------------------
    # Each insert returns a new id via cursor.lastrowid. We store the ids
    # so invoices can point at the right client.
    clients = [
        ("Priya Nair", "priya@brightwavelabs.example", "Brightwave Labs"),      # startup
        ("Marco Ruiz", "billing@northpine.example", "Northpine Creative"),      # agency
        ("Elena Brooks", "accounts@mapleandthread.example", "Maple & Thread"),  # retail brand
        ("Sam Okafor", "sam.okafor@example.com", None),                         # individual consultant
    ]
    client_ids: list[int] = []
    for name, email, company in clients:
        cursor = conn.execute(
            "INSERT INTO clients (name, email, company) VALUES (?, ?, ?)",
            (name, email, company),
        )
        client_ids.append(cursor.lastrowid)

    brightwave, northpine, maple, sam = client_ids

    # --- Invoices --------------------------------------------------------
    # Columns: client_id, invoice_number, description, amount_cents,
    #          status, issue_date, due_date, paid_date
    invoices = [
        # 4 paid
        (brightwave, "INV-2026-001", "Brand identity design",
         150000, "paid", days_from_today(-90), days_from_today(-60), days_from_today(-65)),
        (northpine, "INV-2026-002", "Website development sprint",
         280000, "paid", days_from_today(-75), days_from_today(-45), days_from_today(-50)),
        (maple, "INV-2026-003", "Product packaging illustrations",
         95000, "paid", days_from_today(-60), days_from_today(-30), days_from_today(-28)),
        (sam, "INV-2026-008", "Technical consulting (hourly)",
         60000, "paid", days_from_today(-25), days_from_today(-10), days_from_today(-12)),
        # 2 overdue (due in the past, not yet paid)
        (northpine, "INV-2026-004", "Landing page redesign",
         180000, "overdue", days_from_today(-40), days_from_today(-10), None),
        (sam, "INV-2026-005", "API integration support",
         75000, "overdue", days_from_today(-35), days_from_today(-5), None),
        # 2 pending (due in the future, not yet paid)
        (brightwave, "INV-2026-006", "Mobile app UI design",
         320000, "pending", days_from_today(-3), days_from_today(27), None),
        (maple, "INV-2026-007", "Social media content kit",
         125000, "pending", days_from_today(-1), days_from_today(14), None),
    ]
    conn.executemany(
        """
        INSERT INTO invoices
            (client_id, invoice_number, description, amount_cents,
             status, issue_date, due_date, paid_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        invoices,
    )

    # --- Expenses --------------------------------------------------------
    # 'paid' = already spent (past date); 'upcoming' = future bill.
    expenses = [
        ("Software", "Design tool subscription (monthly)",
         5499, days_from_today(-20), "paid"),
        ("Hosting", "Cloud server hosting",
         1200, days_from_today(-10), "paid"),
        ("Coworking", "Coworking desk (monthly)",
         25000, days_from_today(5), "upcoming"),
        ("Equipment", "External monitor",
         42000, days_from_today(12), "upcoming"),
        ("Marketing", "Portfolio site advertising",
         8000, days_from_today(20), "upcoming"),
        ("Taxes", "Quarterly tax estimate",
         90000, days_from_today(30), "upcoming"),
    ]
    conn.executemany(
        """
        INSERT INTO expenses
            (category, description, amount_cents, expense_date, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        expenses,
    )

    # --- Mark seeding as done --------------------------------------------
    # Next startup will see this flag and skip seeding.
    set_setting(conn, "sample_data_seeded", "1")

    # Starting cash balance (in cents), set only if the user has not set one.
    if get_setting(conn, "cash_balance_cents") is None:
        set_setting(conn, "cash_balance_cents", "425000")


# Run this file directly to create the database without starting the server:
#   python database.py
if __name__ == "__main__":
    init_db()
    print("Database ready at", DB_PATH)
