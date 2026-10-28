"""Prompt assembly: Gemini needs at least one user turn in every request."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from english_teacher.context import with_user_turn


def test_adds_a_user_turn_when_history_is_empty():
    messages = with_user_turn("system prompt", None, "do it")
    assert messages[0].content == "system prompt"
    assert isinstance(messages[-1], HumanMessage)
    assert messages[-1].content == "do it"


def test_keeps_the_students_last_message():
    messages = with_user_turn("system prompt", [HumanMessage(content="my answer")], "nudge")
    assert len(messages) == 2
    assert messages[-1].content == "my answer"


def test_adds_a_nudge_after_a_tutor_message():
    messages = with_user_turn("system prompt", [AIMessage(content="lesson")], "nudge")
    assert len(messages) == 3
    assert messages[-1].content == "nudge"
