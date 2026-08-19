import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.agent import run_planner
from backend.db import get_connection, init_db

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
