from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.agent import run_planner
from backend.db import init_db

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app = FastAPI()
init_db()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    message: str
    plan: list[dict]


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    result = run_planner(body.message)
    return ChatResponse(message=result["message"], plan=result["plan"])
