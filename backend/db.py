import random
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "agent.db"

RANDOM_EVENTS_END = date(2026, 12, 31)
RANDOM_EVENT_TITLES = [
    "Point 1:1",
    "Réunion d'équipe",
    "Revue de code",
    "Atelier design",
    "Point client",
    "Rétrospective sprint",
    "Formation interne",
    "Entretien annuel",
    "Brainstorm produit",
    "Démo sprint",
    "Point budget",
    "Café d'équipe",
]

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

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            role TEXT NOT NULL,
            content TEXT,
            action_ids TEXT,
            trace TEXT,
            usage TEXT,
            created_at TEXT NOT NULL
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
        ("yo", "Yo", "yo@example.com", "Chargé RH", "RH", None, "2021-11-02"),
        ("noham", "Noham", "noham@example.com", "Développeur Backend", "Produit", "adam", "2024-02-12"),
        ("sagal", "Sagal", "sagal@example.com", "Développeuse Frontend", "Produit", "adam", "2024-05-20"),
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
        ("noham", "2026-08-24T09:00:00", "2026-08-24T12:00:00", "Sprint planning"),
        ("noham", "2026-08-25T15:00:00", "2026-08-25T16:00:00", "Revue de code"),
        ("sagal", "2026-08-24T10:00:00", "2026-08-24T12:00:00", "Sprint planning"),
        ("sagal", "2026-08-26T09:00:00", "2026-08-26T10:30:00", "Atelier design"),
    ]
    conn.executemany(
        "INSERT INTO calendar_events (employee_id, start, end, title) VALUES (?, ?, ?, ?)",
        calendar_events,
    )

    employee_ids = [emp[0] for emp in employees]
    scattered = _random_events(employee_ids, date(2026, 8, 27), RANDOM_EVENTS_END)
    conn.executemany(
        "INSERT INTO calendar_events (employee_id, start, end, title) VALUES (?, ?, ?, ?)",
        scattered,
    )

    conn.commit()


def _random_events(
    employee_ids: list[str],
    start: date,
    end: date,
) -> list[tuple[str, str, str, str]]:
    """Éparpille des événements fictifs sur chaque semaine ouvrée de la
    période, pour que le calendrier ne soit pas vide au-delà de la semaine
    de démo initiale. Seed fixe (42) : les données restent stables entre
    deux reseed d'un environnement propre."""
    rng = random.Random(42)
    events: list[tuple[str, str, str, str]] = []

    day = start
    while day <= end:
        if day.weekday() < 5:
            for employee_id in employee_ids:
                if rng.random() < 0.35:
                    hour = rng.randint(WORK_START_HOUR, WORK_END_HOUR - 1)
                    duration = rng.choice([30, 45, 60, 90])
                    start_dt = datetime.combine(day, time(hour=hour))
                    end_dt = start_dt + timedelta(minutes=duration)
                    if end_dt.hour >= WORK_END_HOUR and end_dt.minute > 0:
                        end_dt = datetime.combine(day, time(hour=WORK_END_HOUR))
                    events.append(
                        (
                            employee_id,
                            start_dt.isoformat(),
                            end_dt.isoformat(),
                            rng.choice(RANDOM_EVENT_TITLES),
                        )
                    )
        day += timedelta(days=1)

    return events
