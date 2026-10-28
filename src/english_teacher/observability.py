"""Local logs, traces and token accounting.

Langfuse is the shared, long-term view. This module keeps a copy in SQLite so the
teacher app can show its own dashboard without a round trip to another service:
one row per graph turn, one row per model call, one row per error.

No prompt or student answer text is stored here, only sizes, tokens, timings and
short labels. Set ``ENGLISH_TEACHER_LOG_PROMPTS=1`` if you want the detail column
to carry the message text (off by default, it is student data).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    thread_id TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ok',
    latency_ms INTEGER NOT NULL DEFAULT 0,
    model TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS events_ts ON events(ts);
CREATE TABLE IF NOT EXISTS alerts_sent (
    key TEXT PRIMARY KEY,
    last_sent TEXT NOT NULL
);
"""

DEFAULT_PRICE_INPUT_PER_M = 0.10
DEFAULT_PRICE_OUTPUT_PER_M = 0.40


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat()


def price_per_million() -> tuple[float, float]:
    """USD per million tokens, overridable for whatever model you point at."""
    return (
        float(os.getenv("ENGLISH_TEACHER_PRICE_INPUT_PER_M", DEFAULT_PRICE_INPUT_PER_M)),
        float(os.getenv("ENGLISH_TEACHER_PRICE_OUTPUT_PER_M", DEFAULT_PRICE_OUTPUT_PER_M)),
    )


def cost_of(input_tokens: int, output_tokens: int) -> float:
    """Estimated USD for one call. Rounded to 8 decimals for stable storage."""
    price_in, price_out = price_per_million()
    cost = (input_tokens / 1_000_000) * price_in + (output_tokens / 1_000_000) * price_out
    return round(cost, 8)


def _prompts_enabled() -> bool:
    return os.getenv("ENGLISH_TEACHER_LOG_PROMPTS", "").strip() in {"1", "true", "yes"}


class EventStore:
    """Tiny SQLite log. One connection per write, the volume is tiny."""

    def __init__(self, path: str | Path = "events.sqlite") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

    # ------------------------------------------------------------------ writes
    def record(
        self,
        kind: str,
        name: str,
        *,
        thread_id: str = "",
        user_id: str = "",
        status: str = "ok",
        latency_ms: int = 0,
        model: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        detail: str = "",
        cost_usd: float | None = None,
    ) -> None:
        cost = cost_of(input_tokens, output_tokens) if cost_usd is None else cost_usd
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO events (ts, kind, name, thread_id, user_id, status,"
                " latency_ms, model, input_tokens, output_tokens, cost_usd, detail)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _iso(_now()),
                    kind,
                    name[:80],
                    thread_id[:64],
                    user_id[:80],
                    status,
                    int(latency_ms),
                    model[:80],
                    int(input_tokens),
                    int(output_tokens),
                    float(cost),
                    detail[:2000],
                ),
            )

    # ------------------------------------------------------------------- reads
    def totals(self, since: datetime | None = None) -> dict[str, Any]:
        since = since or datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT"
                " COUNT(*) FILTER (WHERE kind = 'turn'),"
                " COUNT(*) FILTER (WHERE kind = 'llm'),"
                " COUNT(*) FILTER (WHERE status = 'error'),"
                " COALESCE(SUM(input_tokens), 0),"
                " COALESCE(SUM(output_tokens), 0),"
                " COALESCE(SUM(cost_usd), 0)"
                " FROM events WHERE ts >= ?",
                (_iso(since),),
            ).fetchone()
        return {
            "since": _iso(since),
            "turns": int(row[0]),
            "llm_calls": int(row[1]),
            "errors": int(row[2]),
            "input_tokens": int(row[3]),
            "output_tokens": int(row[4]),
            "cost_usd": round(float(row[5]), 6),
        }

    def recent(self, limit: int = 50, kind: str = "") -> list[dict[str, Any]]:
        query = "SELECT ts, kind, name, thread_id, user_id, status, latency_ms, model,"
        query += " input_tokens, output_tokens, cost_usd, detail FROM events"
        params: list[Any] = []
        if kind:
            query += " WHERE kind = ?"
            params.append(kind)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))

        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(query, params).fetchall()
        keys = (
            "ts",
            "kind",
            "name",
            "thread_id",
            "user_id",
            "status",
            "latency_ms",
            "model",
            "input_tokens",
            "output_tokens",
            "cost_usd",
            "detail",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def tokens_today(self) -> int:
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) FROM events WHERE ts >= ?",
                (_iso(today),),
            ).fetchone()
        return int(row[0])

    def last_alert(self, key: str) -> datetime | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT last_sent FROM alerts_sent WHERE key = ?", (key,)
            ).fetchone()
        if not row:
            return None
        try:
            return datetime.fromisoformat(row[0])
        except ValueError:
            return None

    def mark_alert(self, key: str) -> None:
        now = _iso(_now())
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT INTO alerts_sent (key, last_sent) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET last_sent = excluded.last_sent",
                (key[:120], now),
            )

    def alert_cooldown_over(self, key: str, minutes: int) -> bool:
        last = self.last_alert(key)
        if last is None:
            return True
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        return _now() - last >= timedelta(minutes=minutes)


def _usage_from_result(response: Any) -> tuple[int, int, str]:
    """Pull token counts and model name out of an LLMResult, tolerating variants."""
    for generation_list in getattr(response, "generations", []) or []:
        for generation in generation_list:
            message = getattr(generation, "message", None)
            usage = getattr(message, "usage_metadata", None)
            if usage:
                meta = getattr(message, "response_metadata", {}) or {}
                model = str(meta.get("model_name") or meta.get("model") or "")
                return (
                    int(usage.get("input_tokens", 0) or 0),
                    int(usage.get("output_tokens", 0) or 0),
                    model,
                )
    raw = (getattr(response, "llm_output", None) or {}).get("token_usage") or {}
    return (
        int(raw.get("prompt_tokens", 0) or 0),
        int(raw.get("completion_tokens", 0) or 0),
        str(raw.get("model_name", "") or ""),
    )


class TokenMeter(BaseCallbackHandler):
    """One event row per model call: tokens, latency, cost, failures."""

    def __init__(
        self,
        store: EventStore,
        *,
        thread_id: str = "",
        user_id: str = "",
        model_hint: str = "",
    ) -> None:
        super().__init__()
        self.store = store
        self.thread_id = thread_id
        self.user_id = user_id
        self.model_hint = model_hint
        self._started: dict[str, float] = {}

    def on_llm_start(self, serialized: Any, prompts: Any, *, run_id: Any = None, **_: Any) -> None:
        import time

        self._started[str(run_id)] = time.perf_counter()

    def on_chat_model_start(
        self, serialized: Any, messages: Any, *, run_id: Any = None, **_: Any
    ) -> None:
        self.on_llm_start(serialized, messages, run_id=run_id)

    def on_llm_end(self, response: Any, *, run_id: Any = None, **_: Any) -> None:
        import time

        elapsed = self._started.pop(str(run_id), None)
        latency_ms = int((time.perf_counter() - elapsed) * 1000) if elapsed else 0
        input_tokens, output_tokens, model = _usage_from_result(response)
        self.store.record(
            "llm",
            "chat",
            thread_id=self.thread_id,
            user_id=self.user_id,
            latency_ms=latency_ms,
            model=model or self.model_hint,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status="ok",
        )

    def on_llm_error(self, error: BaseException, *, run_id: Any = None, **_: Any) -> None:
        import time

        elapsed = self._started.pop(str(run_id), None)
        latency_ms = int((time.perf_counter() - elapsed) * 1000) if elapsed else 0
        self.store.record(
            "error",
            "llm",
            thread_id=self.thread_id,
            user_id=self.user_id,
            status="error",
            latency_ms=latency_ms,
            model=self.model_hint,
            detail=f"{type(error).__name__}: {error}",
        )


def detail_for(text: str) -> str:
    """Keep student text out of the log unless explicitly enabled."""
    if not text:
        return ""
    return f"msg={text[:300]}" if _prompts_enabled() else ""
