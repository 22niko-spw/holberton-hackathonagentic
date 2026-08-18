import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "agent.db"

WORK_START_HOUR = 9
WORK_END_HOUR = 18


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            department TEXT NOT NULL,
            manager_id TEXT,
            start_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL REFERENCES employees(id),
            start TEXT NOT NULL,
            end TEXT NOT NULL,
            title TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tool TEXT NOT NULL,
            args TEXT NOT NULL,
            reason TEXT NOT NULL,
            depends_on INTEGER REFERENCES actions(id),
            status TEXT NOT NULL DEFAULT 'PROPOSEE'
        );

        CREATE TABLE IF NOT EXISTS journal (
            action_id INTEGER PRIMARY KEY REFERENCES actions(id),
            result TEXT NOT NULL,
            executed_at TEXT NOT NULL
        );
        """
    )
    conn.commit()

    if conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
        _seed(conn)

    conn.close()


def _seed(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO employees (id, name, email, role, department, manager_id, start_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("fatou", "Fatou Diop", "fatou@example.com", "Manager Produit", "Produit", None, "2022-01-10"),
    )
    conn.execute(
        "INSERT INTO calendar_events (employee_id, start, end, title) VALUES (?, ?, ?, ?)",
        ("fatou", "2026-08-24T09:00:00", "2026-08-24T11:00:00", "Point équipe"),
    )
    conn.execute(
        "INSERT INTO calendar_events (employee_id, start, end, title) VALUES (?, ?, ?, ?)",
        ("fatou", "2026-08-24T14:00:00", "2026-08-24T17:00:00", "Comité produit"),
    )
    conn.commit()
