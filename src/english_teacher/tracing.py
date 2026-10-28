"""Langfuse tracing.

Tracing is opt-in: with no ``LANGFUSE_PUBLIC_KEY``/``LANGFUSE_SECRET_KEY`` in the
environment the tutor runs exactly as before, no network calls, no import cost.

When the keys are present every graph run is wrapped in a Langfuse trace through
LangChain's callback system. The thread id becomes the Langfuse session id, so one
student conversation stays grouped across reloads in the Langfuse UI.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any


def tracing_configured() -> bool:
    """True when both Langfuse keys are present."""
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def _make_handler() -> Any:
    """Build the LangChain callback handler (kept small so tests can stub it)."""
    from langfuse.langchain import CallbackHandler

    return CallbackHandler()


def trace_config(
    thread_id: str,
    *,
    user_id: str = "",
    tags: Sequence[str] = (),
) -> dict[str, Any]:
    """RunnableConfig additions for one graph run, or ``{}`` when tracing is off.

    Langfuse's handler reads ``langfuse_session_id``, ``langfuse_user_id`` and
    ``langfuse_tags`` out of the run metadata.
    """
    if not tracing_configured():
        return {}

    try:
        handler = _make_handler()
    except Exception:  # noqa: BLE001 - observability must never break a lesson
        return {}

    metadata: dict[str, Any] = {"langfuse_session_id": thread_id}
    if user_id:
        metadata["langfuse_user_id"] = user_id
    if tags:
        metadata["langfuse_tags"] = list(tags)

    return {"callbacks": [handler], "metadata": metadata}


def flush() -> None:
    """Push buffered spans. Best effort, never raises."""
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:  # noqa: BLE001 - shutdown must stay clean
        return
