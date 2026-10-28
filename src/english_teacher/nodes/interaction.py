"""The only node that talks to the student: pause, get one reply, store it."""

from __future__ import annotations

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from ..state import TeacherState


def wait_student(state: TeacherState, config: RunnableConfig) -> dict:
    """Pause the graph until the student answers.

    LangGraph re-runs this node after the resume value arrives, so the function
    must stay side-effect free apart from returning the reply.
    """
    payload = {
        "kind": state.get("phase", "teaching"),
        "prompt": state.get("teacher_message", ""),
    }
    reply = interrupt(payload)
    text = reply if isinstance(reply, str) else str(reply)
    text = text.strip()

    return {
        "student_message": text,
        "turns": int(state.get("turns", 0)) + 1,
        "messages": [HumanMessage(content=text)],
    }
