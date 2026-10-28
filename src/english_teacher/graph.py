"""Graph wiring.

Shape:

    START -> intake -> placement -> [teach <-> assess] -> readiness
                                        |                   |
                                        |            offer_exam -> wait (yes/no)
                                        |                   |
                                        |            exam -> grade -> review
                                        |                            |
                                        +---- remediation <----------+
                                                     |
                                              promote to next level

Every student turn is one ``interrupt``: the graph pauses on ``wait_student``
and resumes with ``Command(resume=...)``. That is what makes the "waits for his
response" requirement cheap and crash-safe: the pause is checkpointed, not a
sleep loop.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from .cefr import normalise_level
from .languages import get_language
from .nodes import (
    advance_level,
    advance_topic,
    assess_answer,
    build_exam,
    check_readiness,
    grade_exam,
    grade_placement,
    handle_exam_decision,
    intake,
    offer_exam,
    placement_quiz,
    remediation,
    review_exam,
    teacher_turn,
    wait_student,
)
from .policy import new_mastery
from .state import TeacherState

Node = Callable[[TeacherState, RunnableConfig], dict]

SCHEMA_TYPE_NAMES = (
    "PlacementQuestion",
    "PlacementQuiz",
    "Assessment",
    "ReadinessOpinion",
    "ExamDecisionAnswer",
    "ExamItem",
    "Exam",
    "WritingGrade",
    "FailedPoint",
    "ExamResult",
    "RemediationPlan",
)


def route_after_placement(state: TeacherState) -> str:
    return "wait_student" if state.get("placement_quiz") else "teacher_turn"


def route_after_reply(state: TeacherState) -> str:
    phase = state.get("phase")
    if phase == "placement":
        return "grade_placement"
    if phase == "exam_offer":
        return "handle_exam_decision"
    if phase == "exam":
        return "grade_exam"
    return "assess_answer"


def route_after_decision(state: TeacherState) -> str:
    return "build_exam" if state.get("next_action") == "build_exam" else "teacher_turn"


def route_after_check(state: TeacherState) -> str:
    action = state.get("next_action")
    if action == "offer_exam":
        return "offer_exam"
    if action == "advance_topic":
        return "advance_topic"
    return "teacher_turn"


def route_after_review(state: TeacherState) -> str:
    return "advance_level" if state.get("next_action") == "advance" else "remediation"


def route_after_advance(state: TeacherState) -> str:
    return END if state.get("graduated") else "teacher_turn"


def build_graph() -> StateGraph:
    graph = StateGraph(TeacherState)

    nodes: dict[str, Node] = {
        "intake": intake,
        "placement_quiz": placement_quiz,
        "grade_placement": grade_placement,
        "teacher_turn": teacher_turn,
        "wait_student": wait_student,
        "assess_answer": assess_answer,
        "check_readiness": check_readiness,
        "advance_topic": advance_topic,
        "offer_exam": offer_exam,
        "handle_exam_decision": handle_exam_decision,
        "build_exam": build_exam,
        "grade_exam": grade_exam,
        "review_exam": review_exam,
        "advance_level": advance_level,
        "remediation": remediation,
    }
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "placement_quiz")
    graph.add_conditional_edges(
        "placement_quiz",
        route_after_placement,
        {"wait_student": "wait_student", "teacher_turn": "teacher_turn"},
    )
    graph.add_edge("grade_placement", "teacher_turn")
    graph.add_edge("teacher_turn", "wait_student")
    graph.add_conditional_edges(
        "wait_student",
        route_after_reply,
        {
            "grade_placement": "grade_placement",
            "handle_exam_decision": "handle_exam_decision",
            "grade_exam": "grade_exam",
            "assess_answer": "assess_answer",
        },
    )
    graph.add_edge("assess_answer", "check_readiness")
    graph.add_conditional_edges(
        "check_readiness",
        route_after_check,
        {
            "offer_exam": "offer_exam",
            "advance_topic": "advance_topic",
            "teacher_turn": "teacher_turn",
        },
    )
    graph.add_edge("advance_topic", "teacher_turn")
    graph.add_edge("offer_exam", "wait_student")
    graph.add_conditional_edges(
        "handle_exam_decision",
        route_after_decision,
        {"build_exam": "build_exam", "teacher_turn": "teacher_turn"},
    )
    graph.add_edge("build_exam", "wait_student")
    graph.add_edge("grade_exam", "review_exam")
    graph.add_conditional_edges(
        "review_exam",
        route_after_review,
        {"advance_level": "advance_level", "remediation": "remediation"},
    )
    graph.add_conditional_edges(
        "advance_level",
        route_after_advance,
        {"teacher_turn": "teacher_turn", END: END},
    )
    graph.add_edge("remediation", "wait_student")

    return graph


def make_checkpointer(db_path: str | None = None) -> Any:
    """Memory by default; sqlite when a path is configured.

    The custom serde whitelists our own pydantic models so checkpoints stay
    readable after LangGraph tightens its default deserialisation rules.
    """
    serde = make_serde()
    if not db_path:
        return InMemorySaver(serde=serde)
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError as exc:
        raise RuntimeError(
            "SQLite persistence needs `pip install langgraph-checkpoint-sqlite`"
        ) from exc
    return SqliteSaver(sqlite3.connect(db_path, check_same_thread=False), serde=serde)


def make_serde() -> Any:
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    return JsonPlusSerializer(
        allowed_msgpack_modules=[("english_teacher.schemas", name) for name in SCHEMA_TYPE_NAMES]
    )


def compile_graph(checkpointer: Any = None):
    return build_graph().compile(checkpointer=checkpointer or make_checkpointer())


def initial_state(
    student_name: str = "",
    level: str = "",
    goal: str = "",
    language: str = "en",
) -> dict:
    resolved = normalise_level(level)
    chosen = get_language(language)
    return {
        "student_name": student_name,
        "language": chosen.code,
        "level": resolved or "",
        "goal": goal,
        "mastery": new_mastery(),
        "phase": "intake",
        "messages": [],
        "lessons_completed": 0,
        "turns": 0,
        "topics_seen": [],
        "topic_progress": 0.0,
        "topic_complete": False,
        "cooldown_until": 0,
        "offers_declined": 0,
        "graduated": False,
        "plan": chosen.topics(resolved) if resolved else [],
    }
