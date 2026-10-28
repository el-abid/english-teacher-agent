"""Teaching loop: explain, listen, assess, decide whether the level exam is due."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from ..config import load_settings
from ..context import (
    mastery_line,
    placement_line,
    recent_messages,
    weakest_skills,
    with_user_turn,
)
from ..languages import get_language
from ..llm import resolve_llm
from ..policy import apply_observed, evaluate_readiness, new_mastery
from ..prompts import assessment_prompt, readiness_prompt, teaching_prompt
from ..rendering import to_text
from ..schemas import Assessment, ReadinessOpinion
from ..state import TeacherState


def _topic(state: TeacherState) -> dict:
    topic = state.get("current_topic")
    if topic:
        return topic
    language = get_language(state.get("language"))
    plan = state.get("plan") or language.topics(state.get("level", "B1"))
    return plan[0]


_text = to_text


def teacher_turn(state: TeacherState, config: RunnableConfig) -> dict:
    """Produce the next teaching message: one explanation plus one task."""
    settings = load_settings()
    llm = resolve_llm(config)
    language = get_language(state.get("language"))
    level = state.get("level", "B1")
    topic = _topic(state)
    mastery = state.get("mastery") or new_mastery()

    system = teaching_prompt(
        language=language,
        level=level,
        topic=topic,
        mastery_line=mastery_line(mastery),
        weak_skills=weakest_skills(mastery, 2),
        review_mode=bool(state.get("review_mode")),
        remediation=list(state.get("remediation_activities") or []),
        last_feedback=state.get("last_feedback", ""),
        placement_summary=placement_line(state),
    )
    history = recent_messages(state, settings.max_context_messages)
    message = _text(llm.invoke(with_user_turn(system, history, "Teach the next small step now.")))
    if not message:
        message = language.teach_fallback.format(topic=topic["title"])

    return {
        "teacher_message": message,
        "phase": "teaching",
        "messages": [AIMessage(content=message)],
    }


def assess_answer(state: TeacherState, config: RunnableConfig) -> dict:
    """Grade the student's last answer and fold it into the mastery model."""
    settings = load_settings()
    llm = resolve_llm(config)
    language = get_language(state.get("language"))
    level = state.get("level", "B1")
    topic = _topic(state)

    system = assessment_prompt(language, level, topic)
    history = recent_messages(state, settings.max_context_messages)
    assessment = llm.with_structured_output(Assessment).invoke(
        with_user_turn(system, history, "Grade my last answer now.")
    )

    mastery = state.get("mastery") or new_mastery()
    if assessment.scores:
        mastery = apply_observed(mastery, assessment.scores, alpha=settings.alpha)

    progress = min(
        1.0,
        max(0.0, float(state.get("topic_progress", 0.0)))
        + max(0.0, float(assessment.topic_progress)),
    )
    complete = bool(assessment.topic_complete) or progress >= 1.0

    return {
        "mastery": mastery,
        "topic_progress": progress,
        "topic_complete": complete,
        "lessons_completed": int(state.get("lessons_completed", 0)) + int(complete),
        "last_feedback": assessment.feedback,
        "points_to_review": assessment.points_to_review,
    }


def check_readiness(state: TeacherState, config: RunnableConfig) -> dict:
    """Numeric gate first; the tutor's opinion only when the numbers already pass.

    The model can delay a promotion it considers premature, never trigger one on
    its own.
    """
    settings = load_settings()
    language = get_language(state.get("language"))
    level = state.get("level", "B1")
    mastery = state.get("mastery") or new_mastery()
    lessons = int(state.get("lessons_completed", 0))
    verdict = evaluate_readiness(mastery, lessons, settings.thresholds)

    next_action = "advance_topic" if state.get("topic_complete") else "teach"
    result: dict = {
        "readiness_reasons": verdict.reasons,
        "readiness_note": verdict.summary,
        "next_action": next_action,
    }

    if not verdict.ready:
        return result

    llm = resolve_llm(config)
    opinion = llm.with_structured_output(ReadinessOpinion).invoke(
        with_user_turn(
            readiness_prompt(
                language,
                level,
                mastery_line(mastery),
                lessons,
                ", ".join(t["title"] for t in state.get("plan") or []),
            ),
            None,
            "Give your readiness opinion now.",
        )
    )
    result["readiness_note"] = opinion.rationale

    if not opinion.ready:
        return result

    if int(state.get("turns", 0)) < int(state.get("cooldown_until", 0)):
        return result

    result.update({"next_action": "offer_exam", "phase": "exam_offer"})
    return result


def advance_topic(state: TeacherState, config: RunnableConfig) -> dict:
    """Move to the next unseen topic, or recycle the syllabus for review."""
    level = state.get("level", "B1")
    language = get_language(state.get("language"))
    plan = state.get("plan") or language.topics(level)
    seen = list(state.get("topics_seen") or [])
    remaining = [topic for topic in plan if topic["id"] not in seen]

    if remaining:
        topic = remaining[0]
        review = False
    else:
        topic = plan[len(seen) % len(plan)]
        review = True

    return {
        "current_topic": topic,
        "topics_seen": [*seen, topic["id"]],
        "topic_progress": 0.0,
        "topic_complete": False,
        "review_mode": review,
        "remediation_activities": [],
    }
