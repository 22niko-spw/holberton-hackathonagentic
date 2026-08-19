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
    employees = [
        ("adam", "Adam", "adam@example.com", "Manager Produit", "Produit", None, "2022-01-10"),
        ("david", "David", "david@example.com", "Développeur Backend", "Produit", "adam", "2023-03-06"),
        ("atomic-slf", "Atomic SLF", "atomic-slf@example.com", "Développeur Frontend", "Produit", "adam", "2023-09-18"),
        ("yo", "¥o", "yo@example.com", "Chargé RH", "RH", None, "2021-11-02"),
    ]
    conn.executemany(
        "INSERT INTO employees (id, name, email, role, department, manager_id, start_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        employees,
    )

    calendar_events = [
        ("adam", "2026-08-24T09:00:00", "2026-08-24T11:00:00", "Point équipe"),
        ("adam", "2026-08-24T14:00:00", "2026-08-24T17:00:00", "Comité produit"),
        ("adam", "2026-08-25T09:00:00", "2026-08-25T10:00:00", "1:1 David"),
        ("david", "2026-08-24T09:00:00", "2026-08-24T12:00:00", "Sprint planning"),
        ("david", "2026-08-25T09:00:00", "2026-08-25T10:00:00", "1:1 Adam"),
        ("david", "2026-08-26T15:00:00", "2026-08-26T17:00:00", "Revue de code"),
        ("atomic-slf", "2026-08-24T10:00:00", "2026-08-24T12:00:00", "Sprint planning"),
        ("atomic-slf", "2026-08-25T14:00:00", "2026-08-25T16:00:00", "Atelier design"),
        ("yo", "2026-08-24T09:00:00", "2026-08-24T09:30:00", "Point RH quotidien"),
    ]
    conn.executemany(
        "INSERT INTO calendar_events (employee_id, start, end, title) VALUES (?, ?, ?, ?)",
        calendar_events,
    )
    conn.commit()
