from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from backend.agent import run_planner
from backend.db import init_db

app = FastAPI()
templates = Jinja2Templates(directory="backend/templates")
init_db()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    message: str
    plan: list[dict]


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    result = run_planner(body.message)
    return ChatResponse(message=result["message"], plan=result["plan"])
