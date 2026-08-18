import json
import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from backend.db import WORK_END_HOUR, WORK_START_HOUR, get_connection

OUTBOX_DIR = Path(__file__).parent.parent / "outbox"


# ---------------------------------------------------------------------------
# Outils exposés au modèle (lecture + propose_action) — voir DOCS/AGENTS.md
# ---------------------------------------------------------------------------

def get_employee_availability(
    employee_ids: list[str],
    date_range: tuple[date, date],
    duration_minutes: int = 15,
) -> dict[str, list[tuple[datetime, datetime]]]:
    conn = get_connection()
    result: dict[str, list[tuple[datetime, datetime]]] = {}

    for employee_id in employee_ids:
        rows = conn.execute(
            "SELECT start, end FROM calendar_events WHERE employee_id = ? ORDER BY start",
            (employee_id,),
        ).fetchall()
        busy = [(datetime.fromisoformat(r["start"]), datetime.fromisoformat(r["end"])) for r in rows]
        result[employee_id] = _free_slots(busy, date_range, duration_minutes)

    conn.close()
    return result


def find_common_slot(
    employee_ids: list[str],
    date_range: tuple[date, date],
    duration_minutes: int = 30,
    max_candidates: int = 3,
) -> list[tuple[datetime, datetime]] | None:
    start_date, end_date = date_range

    for widen_days in (0, 7, 14, 21):
        current_range = (start_date, end_date + timedelta(days=widen_days))
        availability = get_employee_availability(employee_ids, current_range, duration_minutes)

        common = list(availability.values())[0]
        for slots in list(availability.values())[1:]:
            common = _intersect(common, slots)

        common = [s for s in common if (s[1] - s[0]) >= timedelta(minutes=duration_minutes)]
        if common:
            return common[:max_candidates]

    return None


def propose_action(
    tool: str,
    args: dict,
    reason: str,
    depends_on: int | None = None,
) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO actions (tool, args, reason, depends_on, status) VALUES (?, ?, ?, ?, 'PROPOSEE')",
        (tool, json.dumps(args, default=str), reason, depends_on),
    )
    conn.commit()
    action_id = cursor.lastrowid
    conn.close()
    return action_id


# ---------------------------------------------------------------------------
# Actions à effet de bord (exécuteur uniquement) — jamais données au modèle
# ---------------------------------------------------------------------------

def create_calendar_event(
    action_id: str,
    employee_ids: list[str],
    start: datetime,
    end: datetime,
    title: str,
    description: str = "",
) -> str:
    cached = _journal_get(action_id)
    if cached is not None:
        return cached["event_id"]

    conn = get_connection()
    event_id = None
    for employee_id in employee_ids:
        cursor = conn.execute(
            "INSERT INTO calendar_events (employee_id, start, end, title) VALUES (?, ?, ?, ?)",
            (employee_id, start.isoformat(), end.isoformat(), title),
        )
        event_id = event_id or str(cursor.lastrowid)
    conn.commit()
    conn.close()

    _journal_record(action_id, {"event_id": event_id})
    return event_id


def send_email(
    action_id: str,
    employee_ids: list[str],
    subject: str,
    body: str,
) -> str:
    cached = _journal_get(action_id)
    if cached is not None:
        return cached["path"]

    conn = get_connection()
    recipients = []
    for employee_id in employee_ids:
        row = conn.execute("SELECT email FROM employees WHERE id = ?", (employee_id,)).fetchone()
        if row is None:
            conn.close()
            raise ValueError(f"employee_id inconnu : {employee_id}")
        recipients.append(row["email"])
    conn.close()

    OUTBOX_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")
    filename = f"{date.today().isoformat()}_{slug}.txt"
    path = OUTBOX_DIR / filename
    path.write_text(f"to: {', '.join(recipients)}\nsubject: {subject}\n\n{body}\n", encoding="utf-8")

    _journal_record(action_id, {"path": str(path)})
    return str(path)


def register_employee(
    action_id: str,
    name: str,
    email: str,
    role: str,
    department: str,
    manager_id: str,
    start_date: date,
) -> str:
    cached = _journal_get(action_id)
    if cached is not None:
        return cached["employee_id"]

    employee_id = f"{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}-{uuid.uuid4().hex[:4]}"

    conn = get_connection()
    conn.execute(
        "INSERT INTO employees (id, name, email, role, department, manager_id, start_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (employee_id, name, email, role, department, manager_id, start_date.isoformat()),
    )
    conn.commit()
    conn.close()

    _journal_record(action_id, {"employee_id": employee_id})
    return employee_id


# ---------------------------------------------------------------------------
# Aides internes
# ---------------------------------------------------------------------------

def _free_slots(
    busy: list[tuple[datetime, datetime]],
    date_range: tuple[date, date],
    duration_minutes: int,
) -> list[tuple[datetime, datetime]]:
    start_date, end_date = date_range
    free: list[tuple[datetime, datetime]] = []
    min_gap = timedelta(minutes=duration_minutes)

    day = start_date
    while day <= end_date:
        if day.weekday() < 5:  # jours ouvrés uniquement
            cursor = datetime.combine(day, datetime.min.time()).replace(hour=WORK_START_HOUR)
            day_end = datetime.combine(day, datetime.min.time()).replace(hour=WORK_END_HOUR)

            for b_start, b_end in busy:
                if b_end <= cursor or b_start >= day_end:
                    continue
                if b_start > cursor and (b_start - cursor) >= min_gap:
                    free.append((cursor, b_start))
                cursor = max(cursor, b_end)

            if day_end > cursor and (day_end - cursor) >= min_gap:
                free.append((cursor, day_end))

        day += timedelta(days=1)

    return free


def _intersect(
    a: list[tuple[datetime, datetime]],
    b: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    result = []
    for a_start, a_end in a:
        for b_start, b_end in b:
            start, end = max(a_start, b_start), min(a_end, b_end)
            if start < end:
                result.append((start, end))
    return result


def _journal_get(action_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT result FROM journal WHERE action_id = ?", (action_id,)).fetchone()
    conn.close()
    return json.loads(row["result"]) if row else None


def _journal_record(action_id: str, result: dict) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO journal (action_id, result, executed_at) VALUES (?, ?, ?)",
        (action_id, json.dumps(result), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
