"""Local trace store, token accounting and cost estimate."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from english_teacher.observability import EventStore, TokenMeter, cost_of, detail_for


def test_records_and_totals(tmp_path):
    store = EventStore(tmp_path / "events.sqlite")
    store.record("turn", "message", thread_id="t1", user_id="Nadia", latency_ms=1200)
    store.record(
        "llm",
        "chat",
        thread_id="t1",
        model="gemini-3.1-flash-lite",
        input_tokens=1000,
        output_tokens=500,
    )
    store.record("error", "message", status="error", detail="boom")

    totals = store.totals()
    assert totals["turns"] == 1
    assert totals["llm_calls"] == 1
    assert totals["errors"] == 1
    assert totals["input_tokens"] == 1000
    assert totals["output_tokens"] == 500
    assert totals["cost_usd"] > 0


def test_recent_is_newest_first_and_filterable(tmp_path):
    store = EventStore(tmp_path / "events.sqlite")
    store.record("turn", "first")
    store.record("llm", "second")
    store.record("turn", "third")

    assert [row["name"] for row in store.recent()] == ["third", "second", "first"]
    assert [row["name"] for row in store.recent(kind="turn")] == ["third", "first"]


def test_cost_uses_configured_prices(monkeypatch):
    monkeypatch.setenv("ENGLISH_TEACHER_PRICE_INPUT_PER_M", "1.0")
    monkeypatch.setenv("ENGLISH_TEACHER_PRICE_OUTPUT_PER_M", "2.0")

    assert cost_of(1_000_000, 0) == 1.0
    assert cost_of(0, 1_000_000) == 2.0
    assert cost_of(500_000, 500_000) == 1.5


def test_student_text_is_hidden_unless_opted_in(monkeypatch):
    monkeypatch.delenv("ENGLISH_TEACHER_LOG_PROMPTS", raising=False)
    assert detail_for("I visited Rome last summer") == ""

    monkeypatch.setenv("ENGLISH_TEACHER_LOG_PROMPTS", "1")
    assert detail_for("I visited Rome last summer") == "msg=I visited Rome last summer"


def test_token_meter_records_a_generation(tmp_path):
    store = EventStore(tmp_path / "events.sqlite")
    meter = TokenMeter(store, thread_id="t1", user_id="Nadia", model_hint="gemini")
    message = AIMessage(
        content="hello",
        usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150},
        response_metadata={"model_name": "gemini-3.1-flash-lite"},
    )
    result = LLMResult(generations=[[ChatGeneration(message=message)]])

    meter.on_chat_model_start({}, [], run_id="run-1")
    meter.on_llm_end(result, run_id="run-1")

    rows = store.recent(kind="llm")
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 120
    assert rows[0]["output_tokens"] == 30
    assert rows[0]["model"] == "gemini-3.1-flash-lite"
    assert rows[0]["cost_usd"] > 0


def test_token_meter_records_llm_failures(tmp_path):
    store = EventStore(tmp_path / "events.sqlite")
    meter = TokenMeter(store, thread_id="t2", model_hint="gemini")

    meter.on_chat_model_start({}, [], run_id="run-2")
    meter.on_llm_error(RuntimeError("503 unavailable"), run_id="run-2")

    rows = store.recent(kind="error")
    assert len(rows) == 1
    assert rows[0]["status"] == "error"
    assert "503 unavailable" in rows[0]["detail"]
