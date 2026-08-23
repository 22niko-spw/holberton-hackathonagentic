import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.agent import DISABLED_TOOLS, MAX_HISTORY_MESSAGES, TOGGLEABLE_TOOLS, run_planner
from backend.conversations import (
    append_message,
    conversation_exists,
    create_conversation,
    find_conversation_for_action,
    get_conversation,
    get_history_messages,
)
from backend.db import get_connection, init_db
from backend.executor import approve_action, reject_action

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
logger = logging.getLogger("le_bras")

app = FastAPI()
init_db()


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    conversation_id: int
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
    continuation: dict | None = None


# Outils dont l'approbation débloque mécaniquement la suite d'un plan
# (l'employee_id de register_employee n'existe qu'après son exécution) :
# on relance le planner tout de suite plutôt que d'attendre que le RH
# retape "continue" lui-même.
AUTO_CONTINUE_TOOLS = {"register_employee"}


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


@app.get("/tools")
def tools() -> list[dict]:
    return [{"name": name, "enabled": name not in DISABLED_TOOLS} for name in TOGGLEABLE_TOOLS]


@app.post("/tools/{name}/enable")
def enable_tool(name: str) -> dict:
    if name not in TOGGLEABLE_TOOLS:
        raise HTTPException(status_code=404, detail=f"outil inconnu : {name}")
    DISABLED_TOOLS.discard(name)
    return {"name": name, "enabled": True}


@app.post("/tools/{name}/disable")
def disable_tool(name: str) -> dict:
    if name not in TOGGLEABLE_TOOLS:
        raise HTTPException(status_code=404, detail=f"outil inconnu : {name}")
    DISABLED_TOOLS.add(name)
    return {"name": name, "enabled": False}


@app.get("/conversations/{conversation_id}")
def read_conversation(conversation_id: int) -> dict:
    """Palier 4 — persistance : reprend une conversation précise au
    chargement de la page (le navigateur indique laquelle), plans en attente
    compris — leur statut est relu en direct depuis /actions, jamais figé
    dans le message stocké."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"conversation inconnue : {conversation_id}")
    return conversation


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

    continuation = None
    if outcome["status"] == "EXECUTEE" and outcome.get("tool") in AUTO_CONTINUE_TOOLS:
        conversation_id = find_conversation_for_action(action_id)
        if conversation_id is not None:
            continuation = _continue_conversation(conversation_id)

    return ActionResultResponse(
        id=action_id, status=outcome["status"], message=outcome["message"], continuation=continuation
    )


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


def _save_turn(conversation_id: int, user_message: str, assistant_message: str, **assistant_extra) -> None:
    """La persistance ne doit jamais faire échouer la réponse au RH : si
    l'écriture en base rate pour une raison quelconque, on le journalise et
    on continue plutôt que de renvoyer une erreur 500 brute (déjà arrivé une
    fois avec un conversation_id périmé côté navigateur)."""
    try:
        append_message(conversation_id, "user", user_message)
        append_message(conversation_id, "assistant", assistant_message, **assistant_extra)
    except Exception:
        logger.exception("échec de sauvegarde de la conversation %s", conversation_id)


def _continue_conversation(conversation_id: int) -> dict:
    """Relance le planner juste après l'approbation d'une action qui
    débloque la suite d'un plan (ex: register_employee -> le reste de
    l'arrivée), pour que le RH n'ait pas à retaper "continue" lui-même.
    ok=False si ça échoue (quota, réseau, etc.) : l'approbation elle-même
    reste réussie, mais le RH doit être prévenu que la relance automatique
    a raté plutôt que de ne rien voir apparaître (un plan qui n'avance
    plus sans explication est aussi trompeur qu'une fausse réponse)."""
    history = get_history_messages(conversation_id, MAX_HISTORY_MESSAGES)
    try:
        result = run_planner("Continue.", history)
    except Exception:
        logger.exception("relance automatique échouée pour la conversation %s", conversation_id)
        return {"ok": False}

    _save_turn(
        conversation_id,
        "Continue.",
        result["message"],
        action_ids=result.get("action_ids", []),
        trace=result.get("trace", []),
        usage=result.get("usage", {}),
    )
    return {
        "ok": True,
        "conversation_id": conversation_id,
        "message": result["message"],
        "plan": result["plan"],
        "trace": result.get("trace", []),
        "usage": result.get("usage", {}),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    # conversation_id fourni par le navigateur mais qui ne correspond plus à
    # rien en base (ex: base réinitialisée entre-temps) : on en ouvre une
    # nouvelle plutôt que de planter sur la contrainte de clé étrangère.
    conversation_id = body.conversation_id
    if conversation_id is None or not conversation_exists(conversation_id):
        conversation_id = create_conversation()

    history = get_history_messages(conversation_id, MAX_HISTORY_MESSAGES)

    try:
        result = run_planner(body.message, history)
    except Exception:
        logger.exception("run_planner a échoué pour le message : %s", body.message)
        error_message = "Une erreur inattendue m'a empêché de traiter cette demande. Réessaie, ou reformule."
        _save_turn(conversation_id, body.message, error_message)
        return ChatResponse(
            conversation_id=conversation_id,
            message=error_message,
            plan=[],
            trace=[],
        )

    _save_turn(
        conversation_id,
        body.message,
        result["message"],
        action_ids=result.get("action_ids", []),
        trace=result.get("trace", []),
        usage=result.get("usage", {}),
    )

    return ChatResponse(
        conversation_id=conversation_id,
        message=result["message"],
        plan=result["plan"],
        trace=result.get("trace", []),
        llm_calls=result.get("llm_calls", []),
        usage=result.get("usage", {}),
    )
