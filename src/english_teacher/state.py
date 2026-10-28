"""The single state object that flows through the graph."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from .cefr import Topic
from .policy import SkillState
from .schemas import Exam, ExamResult, FailedPoint, PlacementQuiz


class TeacherState(TypedDict, total=False):
    # --- student ----------------------------------------------------------- #
    student_name: str
    goal: str
    language: str  # registry code: "en" / "fr"
    level: str
    level_history: list[str]

    # --- conversation ------------------------------------------------------ #
    messages: Annotated[list[AnyMessage], add_messages]
    teacher_message: str  # what the tutor last said (also the pending prompt)
    student_message: str  # the student's last reply
    phase: str  # intake | placement | teaching | exam_offer | exam | review | done
    next_action: str  # teach | advance_topic | offer_exam

    # --- progress ---------------------------------------------------------- #
    mastery: dict[str, SkillState]
    lessons_completed: int
    turns: int
    plan: list[Topic]
    current_topic: Topic | None
    topics_seen: list[str]
    topic_progress: float
    topic_complete: bool
    review_mode: bool
    last_feedback: str
    points_to_review: list[str]
    readiness_note: str
    readiness_reasons: list[str]

    # --- placement --------------------------------------------------------- #
    placement_quiz: PlacementQuiz | None
    placement_summary: str

    # --- exam -------------------------------------------------------------- #
    exam: Exam | None
    exam_submission: str | None
    exam_result: ExamResult | None
    exam_writing_feedback: str
    failed_points: list[FailedPoint]
    remediation_activities: list[str]
    cooldown_until: int
    offers_declined: int
    graduated: bool
