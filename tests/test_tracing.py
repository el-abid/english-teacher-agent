"""Tracing stays out of the way until Langfuse keys exist."""

from __future__ import annotations

from english_teacher import tracing


class FakeHandler:
    pass


def test_no_keys_means_no_callbacks(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    assert tracing.tracing_configured() is False
    assert tracing.trace_config("thread-1") == {}


def test_one_missing_key_keeps_tracing_off(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    assert tracing.trace_config("thread-1") == {}


def test_keys_wire_a_handler_and_session_metadata(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setattr(tracing, "_make_handler", lambda: FakeHandler())

    config = tracing.trace_config("web-abc", user_id="Nadia", tags=("web", "B1"))

    assert isinstance(config["callbacks"][0], FakeHandler)
    assert config["metadata"]["langfuse_session_id"] == "web-abc"
    assert config["metadata"]["langfuse_user_id"] == "Nadia"
    assert config["metadata"]["langfuse_tags"] == ["web", "B1"]


def test_a_broken_handler_never_breaks_the_lesson(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")

    def boom():
        raise RuntimeError("langfuse unavailable")

    monkeypatch.setattr(tracing, "_make_handler", boom)

    assert tracing.trace_config("web-abc") == {}
