"""A deterministic stand-in for a chat model, so the graph runs without an API key."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda


class ScriptedLLM:
    """Plays back scripted text replies and structured outputs.

    Structured values are queued per schema name, which keeps tests readable even
    though node execution order is not strictly linear.
    """

    def __init__(
        self,
        texts: list[str] | None = None,
        structured: dict[str, list[Any]] | None = None,
    ) -> None:
        self.texts = list(texts or [])
        self.structured = {name: list(values) for name, values in (structured or {}).items()}
        self.text_calls: list[list[Any]] = []
        self.structured_calls: list[tuple[str, list[Any]]] = []

    def invoke(self, messages: Any, config: Any = None, **kwargs: Any) -> AIMessage:
        self.text_calls.append(list(messages))
        text = self.texts.pop(0) if self.texts else "..."
        return AIMessage(content=text)

    def with_structured_output(self, schema: Any, **kwargs: Any):
        name = schema.__name__

        def run(messages: Any, config: Any = None) -> Any:
            self.structured_calls.append((name, list(messages)))
            queue = self.structured.get(name)
            if not queue:
                raise AssertionError(f"no scripted response for {name}")
            value = queue.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        return RunnableLambda(run)
