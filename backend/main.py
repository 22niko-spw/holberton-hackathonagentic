import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.agent import run_planner
from backend.db import get_connection, init_db
from backend.executor import approve_action, reject_action

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
logger = logging.getLogger("le_bras")

app = FastAPI()
init_db()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    message: str
    plan: list[dict]
    trace: list[dict] = []
    llm_calls: list[dict] = []
    usage: dict = {}


class ActionResultResponse(BaseModel):
    id: int
    status: str
    message: str
    blocked: list[int] = []


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/employees")
def employees() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, role, department FROM employees ORDER BY department, name"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/calendar")
def calendar() -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT calendar_events.id, calendar_events.employee_id, employees.name AS employee_name, "
        "calendar_events.start, calendar_events.end, calendar_events.title "
        "FROM calendar_events JOIN employees ON employees.id = calendar_events.employee_id "
        "ORDER BY calendar_events.start"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/actions")
def actions() -> list[dict]:
    """Journal d'audit consultable : toutes les actions jamais proposées,
    du plus récent au plus ancien, avec le résultat d'exécution si connu."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT actions.id, actions.tool, actions.args, actions.reason, actions.depends_on, "
        "actions.status, journal.result, journal.executed_at "
        "FROM actions LEFT JOIN journal ON journal.action_id = actions.id "
        "ORDER BY actions.id DESC"
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "tool": row["tool"],
            "args": json.loads(row["args"]),
            "reason": row["reason"],
            "depends_on": row["depends_on"],
            "status": row["status"],
            "result": json.loads(row["result"]) if row["result"] else None,
            "executed_at": row["executed_at"],
        }
        for row in rows
    ]


@app.post("/actions/{action_id}/approve", response_model=ActionResultResponse)
def approve(action_id: int) -> ActionResultResponse:
    try:
        outcome = approve_action(action_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ActionResultResponse(id=action_id, status=outcome["status"], message=outcome["message"])


@app.post("/actions/{action_id}/reject", response_model=ActionResultResponse)
def reject(action_id: int) -> ActionResultResponse:
    try:
        outcome = reject_action(action_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    message = "Action refusée."
    if outcome["blocked"]:
        message += f" {len(outcome['blocked'])} action(s) dépendante(s) bloquée(s)."
    return ActionResultResponse(id=action_id, status=outcome["status"], message=message, blocked=outcome["blocked"])


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    try:
        result = run_planner(body.message, body.history)
    except Exception:
        logger.exception("run_planner a échoué pour le message : %s", body.message)
        return ChatResponse(
            message="Une erreur inattendue m'a empêché de traiter cette demande. Réessaie, ou reformule.",
            plan=[],
            trace=[],
        )
    return ChatResponse(
        message=result["message"],
        plan=result["plan"],
        trace=result.get("trace", []),
        llm_calls=result.get("llm_calls", []),
        usage=result.get("usage", {}),
    )
