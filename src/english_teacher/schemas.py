"""Typed payloads: what the LLM must return, and what the policy layer computes.

Anything that decides whether a student moves up a level is computed here in
plain Python (see :mod:`english_teacher.policy`). The LLM supplies evidence and
prose, never the final grade. That keeps promotion reproducible and auditable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Placement
# --------------------------------------------------------------------------- #
class PlacementQuestion(BaseModel):
    id: int
    skill: str = Field(default="grammar", description="grammar, vocabulary or reading")
    prompt: str
    choices: dict[str, str] = Field(description="Exactly four options keyed A, B, C, D")
    answer: str = Field(description="Correct option key: A, B, C or D")


class PlacementQuiz(BaseModel):
    """Three quick checks that seed the mastery model before lesson one."""

    intro: str
    questions: list[PlacementQuestion]


# --------------------------------------------------------------------------- #
# Per-turn assessment
# --------------------------------------------------------------------------- #
class Assessment(BaseModel):
    """How the student's last answer moved their skills."""

    feedback: str = Field(description="2-4 sentences, warm and specific, in English")
    scores: dict[str, float] = Field(
        default_factory=dict,
        description="Observed 0..1 performance per skill touched by this answer",
    )
    topic_progress: float = Field(
        default=0.0,
        description="How much of the current topic this answer covers, 0..1",
    )
    topic_complete: bool = False
    points_to_review: list[str] = Field(default_factory=list)


class ReadinessOpinion(BaseModel):
    """The tutor's holistic opinion, used *in addition to* the numeric gate."""

    ready: bool
    rationale: str = Field(description="One short paragraph for the teacher's log")
    weak_skills: list[str] = Field(default_factory=list)


class ExamDecisionAnswer(BaseModel):
    """Interpretation of a free-text reply to 'do you want the exam?'."""

    accepted: bool
    note: str = ""


# --------------------------------------------------------------------------- #
# Exam
# --------------------------------------------------------------------------- #
class ExamItem(BaseModel):
    id: int
    skill: str = Field(description="One of: grammar, vocabulary, reading")
    prompt: str
    choices: dict[str, str]
    answer: str = Field(description="Correct option key: A, B, C or D")


class Exam(BaseModel):
    title: str
    instructions: str
    items: list[ExamItem]
    writing_prompt: str
    writing_criteria: list[str]


class WritingGrade(BaseModel):
    score: float = Field(description="0..1. 0.7 means it meets the level standard")
    feedback: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class FailedPoint(BaseModel):
    skill: str
    point: str
    advice: str = ""


class ExamResult(BaseModel):
    score: float
    passed: bool
    per_skill: dict[str, float] = Field(default_factory=dict)
    failed_points: list[FailedPoint] = Field(default_factory=list)
    summary: str = ""

    def failed_skills(self) -> list[str]:
        return [p.skill for p in self.failed_points]


# --------------------------------------------------------------------------- #
# Remediation
# --------------------------------------------------------------------------- #
class RemediationPlan(BaseModel):
    focus_skills: list[str]
    activities: list[str] = Field(description="3-5 concrete exercises for the next session")
    message: str = Field(description="What the tutor says to the student")
