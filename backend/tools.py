import json
import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from backend.db import WORK_END_HOUR, WORK_START_HOUR, get_connection

OUTBOX_DIR = Path(__file__).parent.parent / "outbox"

MAX_RANGE_DAYS = 31  # garde-fou anti-JSON-géant : voir _check_range


# ---------------------------------------------------------------------------
# Outils exposés au modèle (lecture + propose_action) — voir DOCS/AGENTS.md
# ---------------------------------------------------------------------------

def list_employees(name_contains: str | None = None) -> list[dict]:
    """Annuaire interne : permet au modèle de retrouver un employee_id à
    partir d'un nom cité par l'utilisateur, ou de savoir que la personne
    n'existe pas encore (=> nouvel arrivant, register_employee d'abord)."""
    conn = get_connection()
    if name_contains:
        rows = conn.execute(
            "SELECT id, name, role, department, manager_id FROM employees "
            "WHERE name LIKE ? ORDER BY name",
            (f"%{name_contains}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, name, role, department, manager_id FROM employees ORDER BY name"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def list_calendar_events(
    employee_id: str | None = None,
    title_contains: str | None = None,
) -> list[dict]:
    """Liste les événements existants, pour que le modèle retrouve l'event_id
    à cibler avant de proposer une suppression (voir delete_calendar_event).
    Toujours plafonné à 20 résultats (les plus proches dans le temps) :
    affiner avec employee_id/title_contains pour une recherche précise."""
    conn = get_connection()
    query = (
        "SELECT calendar_events.id, calendar_events.employee_id, "
        "employees.name AS employee_name, calendar_events.start, "
        "calendar_events.end, calendar_events.title "
        "FROM calendar_events JOIN employees ON employees.id = calendar_events.employee_id"
    )
    clauses = []
    params: list[str] = []
    if employee_id:
        clauses.append("calendar_events.employee_id = ?")
        params.append(employee_id)
    if title_contains:
        clauses.append("calendar_events.title LIKE ?")
        params.append(f"%{title_contains}%")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY calendar_events.start LIMIT 20"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_employee_availability(
    employee_ids: list[str],
    date_range: tuple[date, date],
    duration_minutes: int = 15,
) -> dict[str, list[tuple[datetime, datetime]]]:
    _check_range(date_range)
    return _availability(employee_ids, date_range, duration_minutes)


def find_common_slot(
    employee_ids: list[str],
    date_range: tuple[date, date],
    duration_minutes: int = 30,
    max_candidates: int = 3,
) -> list[tuple[datetime, datetime]] | None:
    _check_range(date_range)
    start_date, end_date = date_range

    for widen_days in (0, 7, 14, 21):
        current_range = (start_date, end_date + timedelta(days=widen_days))
        availability = _availability(employee_ids, current_range, duration_minutes)

        common = list(availability.values())[0]
        for slots in list(availability.values())[1:]:
            common = _intersect(common, slots)

        common = [s for s in common if (s[1] - s[0]) >= timedelta(minutes=duration_minutes)]
        if common:
            return common[:max_candidates]

    return None


def _availability(
    employee_ids: list[str],
    date_range: tuple[date, date],
    duration_minutes: int,
) -> dict[str, list[tuple[datetime, datetime]]]:
    conn = get_connection()
    result: dict[str, list[tuple[datetime, datetime]]] = {}

    for employee_id in employee_ids:
        if conn.execute("SELECT 1 FROM employees WHERE id = ?", (employee_id,)).fetchone() is None:
            conn.close()
            raise ValueError(f"employee_id inconnu : {employee_id}")

        rows = conn.execute(
            "SELECT start, end FROM calendar_events WHERE employee_id = ? ORDER BY start",
            (employee_id,),
        ).fetchall()
        busy = [(datetime.fromisoformat(r["start"]), datetime.fromisoformat(r["end"])) for r in rows]
        result[employee_id] = _free_slots(busy, date_range, duration_minutes)

    conn.close()
    return result


def _check_range(date_range: tuple[date, date]) -> None:
    start_date, end_date = date_range
    span = (end_date - start_date).days
    if span < 0:
        raise ValueError("date_range invalide : la date de fin précède la date de début.")
    if span > MAX_RANGE_DAYS:
        raise ValueError(
            f"Plage de dates trop large ({span} jours) : {MAX_RANGE_DAYS} jours maximum, "
            "pour éviter de renvoyer un pavé de créneaux illisible."
        )


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


def delete_employee(action_id: str, employee_id: str) -> dict:
    """Supprime un employé et, en cascade, ses événements de calendrier —
    sinon la contrainte de clé étrangère sur calendar_events.employee_id
    bloquerait la suppression. Irréversible, comme toute action ici :
    seule l'approbation humaine en amont protège contre une erreur."""
    cached = _journal_get(action_id)
    if cached is not None:
        return cached

    conn = get_connection()
    row = conn.execute("SELECT name FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"employee_id inconnu : {employee_id}")
    name = row["name"]

    conn.execute("DELETE FROM calendar_events WHERE employee_id = ?", (employee_id,))
    conn.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
    conn.commit()
    conn.close()

    result = {"employee_id": employee_id, "name": name}
    _journal_record(action_id, result)
    return result


def delete_calendar_event(action_id: str, event_id: int) -> dict:
    cached = _journal_get(action_id)
    if cached is not None:
        return cached

    conn = get_connection()
    row = conn.execute("SELECT title FROM calendar_events WHERE id = ?", (event_id,)).fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"event_id inconnu : {event_id}")
    title = row["title"]

    conn.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

    result = {"event_id": event_id, "title": title}
    _journal_record(action_id, result)
    return result


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
