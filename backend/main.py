import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.agent import run_planner
from backend.db import init_db

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
logger = logging.getLogger("le_bras")

app = FastAPI()
init_db()


class ChatRequest(BaseModel):
    message: str


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


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    try:
        result = run_planner(body.message)
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
