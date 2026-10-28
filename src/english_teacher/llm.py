"""LLM resolution.

Every node asks for the model through :func:`resolve_llm` instead of creating one
itself. Passing ``{"configurable": {"llm": fake}}`` swaps in a scripted model,
which is how the graph is tested without an API key.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from .config import load_settings


@lru_cache(maxsize=8)
def _default_model(model: str, temperature: float) -> BaseChatModel:
    return init_chat_model(model, temperature=temperature)


def resolve_llm(config: Any = None) -> BaseChatModel:
    """Return the model for this run: injected fake first, else the configured one."""
    configurable = {}
    if isinstance(config, dict):
        configurable = config.get("configurable") or {}
    injected = configurable.get("llm")
    if injected is not None:
        return injected

    settings = load_settings()
    return _default_model(settings.model, settings.temperature)
