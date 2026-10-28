"""Small helpers that turn state into prompt text."""

from __future__ import annotations

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage

from .cefr import SKILLS
from .policy import SkillState
from .state import TeacherState


def with_user_turn(system: str, history: list[AnyMessage] | None, nudge: str) -> list[AnyMessage]:
    """Build a prompt that always ends with a human turn.

    Gemini rejects a request that only carries a system instruction ("contents
    are required"), so every call gets an explicit user nudge when the
    conversation is empty or ends with the tutor speaking.
    """
    messages: list[AnyMessage] = [SystemMessage(content=system), *(history or [])]
    if not isinstance(messages[-1], HumanMessage):
        messages.append(HumanMessage(content=nudge))
    return messages


def mastery_line(mastery: dict[str, SkillState]) -> str:
    rows = []
    for skill in SKILLS:
        entry = mastery.get(skill, {})
        score = float(entry.get("score", 0.0))
        evidence = int(entry.get("evidence", 0))
        rows.append(
            f"- {skill}: {score:.0%} ({evidence} observation{'s' if evidence != 1 else ''})"
        )
    return "\n".join(rows)


def weakest_skills(mastery: dict[str, SkillState], limit: int = 3) -> list[str]:
    ordered = sorted(
        SKILLS,
        key=lambda skill: float(mastery.get(skill, {}).get("score", 0.0)),
    )
    return ordered[:limit]


def recent_messages(state: TeacherState, limit: int) -> list[AnyMessage]:
    return list(state.get("messages", [])[-limit:])


def placement_line(state: TeacherState) -> str:
    summary = state.get("placement_summary")
    return f"Placement check: {summary}" if summary else ""
