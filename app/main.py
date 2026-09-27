"""FastAPI app: chat, pantry view, one-tap 'Used' buttons, demo cleanup, and the web page.

PantryPal is a personal app. On Cloud Run it's deployed private
(--no-allow-unauthenticated), so only you can open it.
"""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app import agent
from app.config import settings
from app.db import close_engine, get_engine
from app.store import AlloyStore
from app.tools import ToolBox
from app.util import clean_history, today_in

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pantrypal")
ROOT = Path(__file__).resolve().parent.parent
_client = None


def get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(vertexai=True, project=settings.project_id, location=settings.gemini_location)
    return _client


def make_store(conn):
    """Swapped for an in-memory store in tests."""
    return AlloyStore(conn)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_engine()


app = FastAPI(title="PantryPal", version="1.0.0", lifespan=lifespan)


class Message(BaseModel):
    role: str
    text: str = Field(..., max_length=6000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1, max_length=60)
    tz: str | None = Field(None, max_length=64)


class DietRequest(BaseModel):
    diets: list[str] = Field(default_factory=list, max_length=10)
    avoid: list[str] = Field(default_factory=list, max_length=20)


class UseRequest(BaseModel):
    item_id: int
    tz: str | None = Field(None, max_length=64)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(ROOT / "frontend" / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/healthz")
def healthz() -> dict:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/pantry")
def pantry(tz: str | None = Query(None, max_length=64)) -> dict:
    day, zone = today_in(tz, settings.default_timezone)
    with get_engine().begin() as conn:
        store = make_store(conn)
        box = ToolBox(store, day)
        return {"card": box.pantry_card(), "status": store.status(), "diet": box.diet_card(), "tz": zone}


@app.get("/api/diet")
def get_diet() -> dict:
    with get_engine().begin() as conn:
        return ToolBox(make_store(conn), None).diet_card()


@app.post("/api/diet")
def set_diet(req: DietRequest) -> dict:
    """Diet picker in the header: saves without a round trip to Gemini."""
    with get_engine().begin() as conn:
        box = ToolBox(make_store(conn), None)
        try:
            box.set_diet(req.diets, req.avoid)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return box.diet_card()


@app.post("/api/pantry/used")
def mark_used(req: UseRequest) -> dict:
    """One-tap 'Used' button: marks an item used up without a round trip to Gemini."""
    day, _ = today_in(req.tz, settings.default_timezone)
    with get_engine().begin() as conn:
        store = make_store(conn)
        box = ToolBox(store, day)
        if not any(i["item_id"] == req.item_id for i in box.items()):
            raise HTTPException(status_code=404, detail="That item isn't in the pantry.")
        store.use_item(req.item_id, True, None, day)
        box._items = None
        return {"card": box.pantry_card(), "status": store.status()}


@app.post("/api/demo/clear")
def clear_demo(tz: str | None = Query(None, max_length=64)) -> dict:
    day, _ = today_in(tz, settings.default_timezone)
    with get_engine().begin() as conn:
        store = make_store(conn)
        removed = store.clear_demo()
        return {"removed": removed, "card": ToolBox(store, day).pantry_card(), "status": store.status()}


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    try:
        history = clean_history([m.model_dump() for m in req.messages])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    day, _ = today_in(req.tz, settings.default_timezone)
    started = time.perf_counter()
    try:
        with get_engine().begin() as conn:
            store = make_store(conn)
            has_demo = bool(store.status().get("demo_items"))
            result = agent.run_chat(get_client(), settings.gemini_model, history, ToolBox(store, day), has_demo)
    except Exception as e:
        log.exception("Chat failed")
        raise HTTPException(status_code=502, detail=f"PantryPal hit an error ({type(e).__name__}). Please try again.")
    result["total_ms"] = round((time.perf_counter() - started) * 1000)
    return result
