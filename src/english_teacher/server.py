"""FastAPI server powering the web UI.

The graph is compiled once per process. Each browser session is a LangGraph
thread; the UI holds the thread id and posts one student message at a time.
Because the graph pauses with ``interrupt()``, the server stores no conversation
state of its own: the checkpointer is the source of truth.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.types import Command
from pydantic import BaseModel, Field

from . import __version__, alerts
from .agent_card import load_agent_card
from .cefr import SKILLS
from .config import load_env_file, load_settings
from .governance import KillSwitch, admin_token, kill_switch_path, token_matches
from .graph import compile_graph, initial_state, make_checkpointer
from .languages import get_language, language_catalogue
from .observability import EventStore, TokenMeter, detail_for
from .rendering import to_text
from .tracing import flush, trace_config, tracing_configured

WEB_DIR = Path(__file__).parent / "web"

load_env_file()


class NewSession(BaseModel):
    name: str = Field(default="", max_length=60)
    level: str = Field(default="", max_length=8)
    goal: str = Field(default="", max_length=300)
    language: str = Field(default="en", max_length=20)


class StudentReply(BaseModel):
    message: str = Field(min_length=1, max_length=6000)


class KillSwitchChange(BaseModel):
    active: bool
    reason: str = Field(default="", max_length=300)
    actor: str = Field(default="operator", max_length=80)


def _payload(interrupts: Any) -> dict | None:
    for item in interrupts or ():
        value = getattr(item, "value", item)
        return value if isinstance(value, dict) else {"prompt": str(value)}
    return None


def _transcript(values: dict) -> list[dict]:
    """The conversation so far, so a reloaded page shows the same chat."""
    lines: list[dict] = []
    for message in values.get("messages") or []:
        text = to_text(message)
        if not text:
            continue
        role = "student" if getattr(message, "type", "") == "human" else "teacher"
        lines.append({"role": role, "text": text})
    return lines


def _snapshot(values: dict, interrupts: Any, thread_id: str) -> dict:
    payload = _payload(interrupts)
    mastery = values.get("mastery") or {}
    plan = values.get("plan") or []
    topic = values.get("current_topic") or (plan[0] if plan else {})
    result = values.get("exam_result")
    language = get_language(values.get("language"))
    level = values.get("level", "")

    return {
        "thread_id": thread_id,
        "awaiting": payload is not None,
        "reply": (payload or {}).get("prompt", values.get("teacher_message", "")),
        "history": _transcript(values),
        "kind": (payload or {}).get("kind", "done" if values.get("graduated") else "idle"),
        "language": language.code,
        "language_name": language.name,
        "teacher": language.teacher,
        "initials": language.initials,
        "level": level,
        "level_label": language.label(level),
        "phase": values.get("phase", ""),
        "topic": topic.get("title", ""),
        "lessons_completed": int(values.get("lessons_completed", 0)),
        "topics_total": len(values.get("plan") or []),
        "graduated": bool(values.get("graduated")),
        "mastery": {
            skill: round(float(mastery.get(skill, {}).get("score", 0.0)) * 100) for skill in SKILLS
        },
        "exam_result": (
            {
                "score": round(float(result.score) * 100),
                "passed": bool(result.passed),
                "summary": result.summary,
                "failed_points": [point.point for point in result.failed_points],
            }
            if result is not None
            else None
        ),
    }


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Flush buffered Langfuse spans when the server stops."""
    yield
    flush()


def create_app(
    llm: Any = None,
    checkpointer: Any = None,
    db_path: str | None = None,
    events_path: str | None = None,
    kill_switch: KillSwitch | None = None,
    admin_secret: str | None = None,
) -> FastAPI:
    """Build the app. Dependencies, governance state and the admin secret are injectable."""
    settings = load_settings()
    path = db_path if db_path is not None else settings.db_path
    graph = compile_graph(checkpointer or make_checkpointer(path))
    store = EventStore(
        events_path
        or os.getenv("ENGLISH_TEACHER_EVENTS_DB")
        or str(Path(path or "sessions.sqlite").with_name("events.sqlite"))
    )
    switcher = kill_switch or KillSwitch(kill_switch_path(path or store.path))
    expected_admin = admin_secret if admin_secret is not None else admin_token()
    lock = threading.Lock()

    app = FastAPI(title="Language Teacher Agent", docs_url="/api/docs", lifespan=_lifespan)

    def ensure_running() -> None:
        state = switcher.status()
        if state["active"]:
            reason = state["reason"] or "no reason given"
            raise HTTPException(
                status_code=503,
                detail=f"Kill switch active: {reason}",
                headers={"Retry-After": "60"},
            )

    def config_for(
        thread_id: str,
        *,
        user_id: str = "",
        tags: tuple[str, ...] = ("web",),
    ) -> dict:
        config: dict = {"configurable": {"thread_id": thread_id}}
        if llm is not None:
            config["configurable"]["llm"] = llm
        config.update(trace_config(thread_id, user_id=user_id, tags=tags))
        callbacks = list(config.get("callbacks") or [])
        callbacks.append(
            TokenMeter(store, thread_id=thread_id, user_id=user_id, model_hint=settings.model)
        )
        config["callbacks"] = callbacks
        return config

    def finish_turn(
        name: str,
        thread_id: str,
        user_id: str,
        started: float,
        state: dict,
        extra: str = "",
    ) -> None:
        # Phase, level and topic are routing labels, not student text, so they are
        # always kept. Message bodies only appear when ENGLISH_TEACHER_LOG_PROMPTS=1.
        topic = state.get("current_topic") or {}
        topic_id = topic.get("id", "") if isinstance(topic, dict) else str(topic)
        detail = (
            f"lang={state.get('language', 'en')} phase={state.get('phase', '')} "
            f"level={state.get('level', '')} topic={topic_id}"
        )
        if extra:
            detail = f"{detail} | {extra}"
        store.record(
            "turn",
            name,
            thread_id=thread_id,
            user_id=user_id,
            latency_ms=int((time.perf_counter() - started) * 1000),
            detail=detail,
        )
        alerts.check_token_budget(store)

    def record_failure(
        name: str, thread_id: str, user_id: str, started: float, exc: Exception
    ) -> None:
        detail = f"{type(exc).__name__}: {exc}"
        store.record(
            "error",
            name,
            thread_id=thread_id,
            user_id=user_id,
            status="error",
            latency_ms=int((time.perf_counter() - started) * 1000),
            detail=detail,
        )
        alerts.alert_error(store, name, detail)

    @app.get("/api/health")
    def health() -> dict:
        switch = switcher.status()
        return {
            "status": "ok",
            "version": __version__,
            "model": settings.model,
            "tracing": "langfuse" if tracing_configured() else "off",
            "alerts": "email" if alerts.email_configured() else "off",
            "kill_switch": "active" if switch["active"] else "off",
        }

    @app.get("/api/governance")
    def governance() -> dict:
        switch = switcher.status()
        return {
            "version": __version__,
            "status": "suspended" if switch["active"] else "active",
            "kill_switch": switch,
            "admin_api": bool(expected_admin),
            "agent_card": "/api/agent-card",
            "runbook": "docs/RUNBOOK.md",
            "changelog": "CHANGELOG.md",
        }

    def card_payload() -> dict:
        return load_agent_card(kill_switch=switcher, model=settings.model)

    @app.get("/api/agent-card")
    def agent_card() -> dict:
        return card_payload()

    @app.get("/.well-known/agent-card.json")
    def well_known_agent_card() -> dict:
        return card_payload()

    @app.post("/api/admin/kill-switch")
    def set_kill_switch(
        payload: KillSwitchChange,
        x_admin_token: str | None = Header(default=None),
    ) -> dict:
        if not expected_admin:
            raise HTTPException(
                status_code=404,
                detail="Admin API disabled; set ENGLISH_TEACHER_ADMIN_TOKEN",
            )
        if not token_matches(expected_admin, x_admin_token or ""):
            raise HTTPException(status_code=403, detail="Invalid admin token")
        status = switcher.set(payload.active, reason=payload.reason, actor=payload.actor)
        store.record(
            "governance",
            "kill_switch_on" if payload.active else "kill_switch_off",
            detail=f"actor={payload.actor} reason={payload.reason}",
        )
        return status

    @app.get("/api/levels")
    def levels(language: str = "") -> list[dict]:
        return get_language(language).levels()

    @app.get("/api/languages")
    def languages() -> list[dict]:
        return language_catalogue()

    @app.post("/api/sessions")
    def start_session(payload: NewSession) -> dict:
        ensure_running()
        thread_id = f"web-{uuid.uuid4().hex[:12]}"
        user_id = payload.name.strip()
        language = get_language(payload.language)
        config = config_for(
            thread_id,
            user_id=user_id,
            tags=("web", (payload.level.strip() or "auto").upper(), language.code),
        )
        started = time.perf_counter()
        try:
            with lock:
                state = graph.invoke(
                    initial_state(
                        payload.name.strip(),
                        payload.level.strip(),
                        payload.goal.strip(),
                        language.code,
                    ),
                    config,
                )
        except Exception as exc:
            record_failure("start_session", thread_id, user_id, started, exc)
            raise HTTPException(status_code=502, detail=f"Tutor error: {exc}") from exc
        finish_turn("start_session", thread_id, user_id, started, state, detail_for(payload.goal))
        return _snapshot(state, state.get("__interrupt__"), thread_id)

    @app.get("/api/sessions/{thread_id}")
    def get_session(thread_id: str) -> dict:
        with lock:
            snapshot = graph.get_state(config_for(thread_id))
        if not snapshot.values:
            raise HTTPException(status_code=404, detail="Unknown session")
        return _snapshot(snapshot.values, snapshot.interrupts, thread_id)

    @app.post("/api/sessions/{thread_id}/messages")
    def send_message(thread_id: str, payload: StudentReply) -> dict:
        ensure_running()
        text = payload.message.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Empty message")

        with lock:
            current = graph.get_state(config_for(thread_id))
            if not current.values:
                raise HTTPException(status_code=404, detail="Unknown session")
            if not current.interrupts:
                raise HTTPException(status_code=409, detail="This session has ended")
            user_id = str(current.values.get("student_name", ""))
            config = config_for(
                thread_id,
                user_id=user_id,
                tags=(
                    "web",
                    str(current.values.get("level", "")),
                    get_language(current.values.get("language")).code,
                ),
            )
            started = time.perf_counter()
            try:
                state = graph.invoke(Command(resume=text), config)
            except Exception as exc:
                record_failure("message", thread_id, user_id, started, exc)
                raise HTTPException(status_code=502, detail=f"Tutor error: {exc}") from exc

        finish_turn("message", thread_id, user_id, started, state, detail_for(text))
        return _snapshot(state, state.get("__interrupt__"), thread_id)

    @app.get("/api/dashboard")
    def dashboard(limit: int = 50, kind: str = "") -> dict:
        wanted = kind if kind in {"turn", "llm", "error", "alert", "governance"} else ""
        switch = switcher.status()
        return {
            "version": __version__,
            "model": settings.model,
            "tracing": "langfuse" if tracing_configured() else "off",
            "kill_switch": switch,
            "totals": store.totals(),
            "alerts": alerts.status(store),
            "events": store.recent(limit=limit, kind=wanted),
        }

    @app.get("/dashboard")
    def dashboard_page() -> FileResponse:
        return FileResponse(WEB_DIR / "dashboard.html")

    @app.get("/governance")
    def governance_page() -> FileResponse:
        return FileResponse(WEB_DIR / "governance.html")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        return response

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app


app = create_app()


def main() -> None:
    db_path = os.getenv("ENGLISH_TEACHER_DB") or "sessions.sqlite"
    host = os.getenv("ENGLISH_TEACHER_HOST", "127.0.0.1")
    port = int(os.getenv("ENGLISH_TEACHER_PORT", "8000"))
    print(
        f"Language teacher web UI v{__version__}: http://{host}:{port}  "
        f"(sessions in {db_path})"
    )
    uvicorn.run(create_app(db_path=db_path), host=host, port=port)


if __name__ == "__main__":
    main()
