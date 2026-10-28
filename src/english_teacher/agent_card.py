"""Load and enrich the Agent Card shown to operators and integrations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .governance import KillSwitch
from .languages import language_catalogue

AGENT_CARD_PATH = Path(__file__).with_name("agent_card.json")


def load_agent_card(
    *,
    kill_switch: KillSwitch | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Return the static card with live version, languages and suspension state."""
    card: dict[str, Any] = json.loads(AGENT_CARD_PATH.read_text(encoding="utf-8"))
    card["version"] = __version__
    card["languages"] = [
        {"code": item["code"], "name": item["name"], "teacher": item["teacher"]}
        for item in language_catalogue()
    ]

    if model:
        provider, _, name = model.partition(":")
        card["model"]["runtime"] = model
        card["model"]["provider"] = provider or card["model"]["provider"]
        card["model"]["name"] = name or model

    status = (
        kill_switch.status()
        if kill_switch is not None
        else {
            "active": False,
            "reason": "",
            "actor": "",
            "since": "",
            "source": "none",
            "env_override": False,
        }
    )
    card["kill_switch"] = {
        "active": bool(status["active"]),
        "reason": status["reason"],
        "since": status["since"],
        "source": status["source"],
    }
    card["status"] = "suspended" if status["active"] else "active"
    return card
