import json
import sqlite3
from datetime import date, datetime

from backend.agent import DISABLED_TOOLS
from backend.db import get_connection
from backend.tools import (
    create_calendar_event,
    delete_calendar_event,
    delete_employee,
    register_employee,
    send_email,
)


def _run_create_calendar_event(action_id: int, args: dict):
    return create_calendar_event(
        action_id=str(action_id),
        employee_ids=args["employee_ids"],
        start=datetime.fromisoformat(args["start"]),
        end=datetime.fromisoformat(args["end"]),
        title=args["title"],
        description=args.get("description", ""),
    )


def _run_send_email(action_id: int, args: dict):
    return send_email(
        action_id=str(action_id),
        employee_ids=args["employee_ids"],
        subject=args["subject"],
        body=args["body"],
    )


def _run_register_employee(action_id: int, args: dict):
    return register_employee(
        action_id=str(action_id),
        name=args["name"],
        email=args["email"],
        role=args["role"],
        department=args["department"],
        manager_id=args.get("manager_id"),
        start_date=date.fromisoformat(args["start_date"]),
    )


def _run_delete_employee(action_id: int, args: dict):
    return delete_employee(action_id=str(action_id), employee_id=args["employee_id"])


def _run_delete_calendar_event(action_id: int, args: dict):
    return delete_calendar_event(action_id=str(action_id), event_id=args["event_id"])


EXECUTORS = {
    "create_calendar_event": _run_create_calendar_event,
    "send_email": _run_send_email,
    "register_employee": _run_register_employee,
    "delete_employee": _run_delete_employee,
    "delete_calendar_event": _run_delete_calendar_event,
}


def _confirmation_message(tool: str, args: dict, result) -> str:
    if tool == "register_employee":
        return f"{args['name']} a bien été ajouté·e au système (id : {result})."
    if tool == "create_calendar_event":
        who = ", ".join(args.get("employee_ids", []))
        return f"Événement « {args['title']} » ajouté au calendrier pour {who} ({args['start']} → {args['end']})."
    if tool == "send_email":
        who = ", ".join(args.get("employee_ids", []))
        return f"Email « {args['subject']} » envoyé à {who}."
    if tool == "delete_employee":
        return f"{result['name']} a été supprimé·e du système, ainsi que ses événements de calendrier."
    if tool == "delete_calendar_event":
        return f"Événement « {result['title']} » supprimé du calendrier."
    return f"Action {tool} exécutée."


def _get_action(conn: sqlite3.Connection, action_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()


def approve_action(action_id: int) -> dict:
    conn = get_connection()
    try:
        action = _get_action(conn, action_id)
        if action is None:
            raise ValueError(f"action inconnue : {action_id}")
        if action["status"] != "PROPOSEE":
            raise ValueError(f"action {action_id} n'est pas en attente (status actuel : {action['status']})")

        if action["depends_on"] is not None:
            dependency = _get_action(conn, action["depends_on"])
            if dependency is None or dependency["status"] != "EXECUTEE":
                raise ValueError(
                    f"l'action #{action['depends_on']} dont celle-ci dépend n'est pas encore exécutée"
                )

        if action["tool"] in DISABLED_TOOLS:
            raise ValueError(
                f"l'outil '{action['tool']}' est actuellement désactivé — réactive-le dans "
                "« Outils de l'agent » avant d'approuver cette action."
            )

        conn.execute("UPDATE actions SET status = 'APPROUVEE' WHERE id = ?", (action_id,))
        conn.commit()

        args = json.loads(action["args"])
        result = EXECUTORS[action["tool"]](action_id, args)

        conn.execute("UPDATE actions SET status = 'EXECUTEE' WHERE id = ?", (action_id,))
        conn.commit()

        return {
            "status": "EXECUTEE",
            "result": result,
            "message": _confirmation_message(action["tool"], args, result),
        }
    finally:
        conn.close()


def reject_action(action_id: int) -> dict:
    conn = get_connection()
    try:
        action = _get_action(conn, action_id)
        if action is None:
            raise ValueError(f"action inconnue : {action_id}")
        if action["status"] not in ("PROPOSEE",):
            raise ValueError(f"action {action_id} n'est pas en attente (status actuel : {action['status']})")

        conn.execute("UPDATE actions SET status = 'REFUSEE' WHERE id = ?", (action_id,))
        blocked = _cascade_block(conn, action_id)
        conn.commit()

        return {"status": "REFUSEE", "blocked": blocked}
    finally:
        conn.close()


def _cascade_block(conn: sqlite3.Connection, action_id: int) -> list[int]:
    """Une action REFUSEE ou BLOQUEE bloque tout ce qui en dépend, en cascade."""
    dependents = conn.execute("SELECT id FROM actions WHERE depends_on = ?", (action_id,)).fetchall()
    blocked = []
    for dependent in dependents:
        conn.execute("UPDATE actions SET status = 'BLOQUEE' WHERE id = ?", (dependent["id"],))
        blocked.append(dependent["id"])
        blocked.extend(_cascade_block(conn, dependent["id"]))
    return blocked
