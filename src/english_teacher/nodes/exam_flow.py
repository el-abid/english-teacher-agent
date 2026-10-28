"""Exam lifecycle: offer -> accept -> generate -> grade -> promote or remediate."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from ..cefr import next_level, topics_for
from ..config import load_settings
from ..context import mastery_line, recent_messages, with_user_turn
from ..llm import resolve_llm
from ..policy import (
    build_remediation,
    compute_exam_score,
    decide_outcome,
    new_mastery,
    parse_mcq_submission,
    score_mcq,
    split_exam_submission,
)
from ..prompts import (
    decision_prompt,
    exam_prompt,
    offer_prompt,
    remediation_prompt,
    results_prompt,
    writing_grade_prompt,
)
from ..rendering import render_exam, to_text
from ..schemas import (
    Exam,
    ExamDecisionAnswer,
    FailedPoint,
    RemediationPlan,
    WritingGrade,
)
from ..state import TeacherState

_OBJECTIVE_SKILLS = {"grammar", "vocabulary", "reading"}


def _unit(value: Any) -> float:
    """Clamp a model score to 0..1, tolerating percentages like 85."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number > 1.0:
        number = number / 100.0
    return min(max(number, 0.0), 1.0)


def _focus(state: TeacherState) -> str:
    failed = state.get("failed_points") or []
    if not failed:
        return ""
    return "; ".join(f"{point.skill}: {point.point}" for point in failed[:3])


def offer_exam(state: TeacherState, config: RunnableConfig) -> dict:
    """Suggest the exam and stop. The student's answer decides what happens next."""
    settings = load_settings()
    llm = resolve_llm(config)
    level = state.get("level", "B1")
    mastery = state.get("mastery") or new_mastery()
    topics = ", ".join(t["title"] for t in state.get("plan") or [])

    system = offer_prompt(level, mastery_line(mastery), topics, settings.exam_items)
    text = to_text(
        llm.invoke(with_user_turn(system, recent_messages(state, 4), "Offer the exam now."))
    )
    if not text:
        text = (
            f"Your work at {level} looks solid. Do you want to take the {level} exam now? "
            f"It has {settings.exam_items} questions and one writing task. You can say not yet."
        )

    return {
        "teacher_message": text,
        "phase": "exam_offer",
        "messages": [AIMessage(content=text)],
    }


def handle_exam_decision(state: TeacherState, config: RunnableConfig) -> dict:
    """Turn 'yes / not yet / I'm scared' into a routing decision."""
    settings = load_settings()
    llm = resolve_llm(config)
    answer = llm.with_structured_output(ExamDecisionAnswer).invoke(
        [
            SystemMessage(content=decision_prompt()),
            HumanMessage(content=state.get("student_message", "")),
        ]
    )

    if answer.accepted:
        return {"next_action": "build_exam"}

    return {
        "phase": "teaching",
        "next_action": "teach",
        "cooldown_until": int(state.get("turns", 0)) + settings.offer_cooldown_turns,
        "offers_declined": int(state.get("offers_declined", 0)) + 1,
    }


def _normalise_exam(exam: Exam) -> Exam:
    items = []
    for index, item in enumerate(exam.items[:12], start=1):
        choices = {str(key).upper(): str(value) for key, value in item.choices.items()}
        answer = str(item.answer).strip().upper()
        if len(choices) != 4 or answer not in choices:
            continue
        skill = item.skill.strip().lower()
        items.append(
            item.model_copy(
                update={
                    "id": index,
                    "choices": choices,
                    "answer": answer,
                    "skill": skill if skill in _OBJECTIVE_SKILLS else "grammar",
                }
            )
        )

    if len(items) < 4:
        raise ValueError("exam has fewer than four valid multiple-choice items")
    if not exam.writing_prompt.strip():
        raise ValueError("exam has no writing task")

    criteria = exam.writing_criteria or [
        "task response",
        "accuracy",
        "range",
        "organisation",
    ]
    return exam.model_copy(update={"items": items, "writing_criteria": criteria})


def build_exam(state: TeacherState, config: RunnableConfig) -> dict:
    """Generate the exam, validate it, then present it."""
    settings = load_settings()
    llm = resolve_llm(config)
    level = state.get("level", "B1")
    topics = ", ".join(t["title"] for t in state.get("plan") or topics_for(level))

    exam: Exam | None = None
    error = ""
    for _ in range(2):
        prompt = exam_prompt(level, topics, _focus(state), settings.exam_items)
        if error:
            prompt += f"\n\nYour previous exam was invalid: {error}. Fix it."
        try:
            raw = llm.with_structured_output(Exam).invoke(
                with_user_turn(prompt, None, "Write the exam now.")
            )
            exam = _normalise_exam(raw)
            break
        except Exception as exc:  # noqa: BLE001 - bad model output is retried, then raised
            error = str(exc)

    if exam is None:
        raise RuntimeError(f"Could not build a valid {level} exam: {error}")

    message = render_exam(exam)
    return {
        "exam": exam,
        "teacher_message": message,
        "phase": "exam",
        "messages": [AIMessage(content=message)],
    }


def grade_exam(state: TeacherState, config: RunnableConfig) -> dict:
    """Objective part is graded in Python; only the writing sample needs a rubric."""
    settings = load_settings()
    llm = resolve_llm(config)
    level = state.get("level", "B1")
    exam = state.get("exam")
    if exam is None:
        raise RuntimeError("grade_exam called without an exam")

    submission = state.get("student_message") or ""
    mcq_text, writing_text = split_exam_submission(submission)
    answers = parse_mcq_submission(mcq_text, len(exam.items))
    key = {item.id: item.answer for item in exam.items}
    correct, total = score_mcq(answers, key)

    if writing_text.strip():
        grade = llm.with_structured_output(WritingGrade).invoke(
            [
                SystemMessage(
                    content=writing_grade_prompt(level, exam.writing_prompt, exam.writing_criteria)
                ),
                HumanMessage(content=writing_text),
            ]
        )
        writing_score = _unit(grade.score)
        writing_feedback = grade.feedback
        weaknesses = grade.weaknesses
    else:
        writing_score = 0.0
        writing_feedback = "No writing sample was submitted."
        weaknesses = ["the writing task was left empty"]

    buckets: dict[str, list[bool]] = {}
    wrong_items: list[FailedPoint] = []
    for item in exam.items:
        hit = answers.get(item.id) == item.answer
        buckets.setdefault(item.skill, []).append(hit)
        if not hit:
            wrong_items.append(
                FailedPoint(
                    skill=item.skill,
                    point=f"missed: {item.prompt[:90]}",
                    advice=f"Redo a similar {item.skill} item on this topic.",
                )
            )

    per_skill = {skill: sum(hits) / len(hits) for skill, hits in buckets.items()}
    per_skill["writing"] = writing_score

    score = compute_exam_score(correct, total, writing_score, settings.exam_mcq_weight)
    preliminary = decide_outcome(score, per_skill, thresholds=settings.thresholds)
    if preliminary.passed:
        result = preliminary
    else:
        weak = set(preliminary.failed_skills())
        concrete = [point for point in wrong_items if point.skill in weak]
        if weaknesses:
            concrete.append(
                FailedPoint(
                    skill="writing",
                    point="; ".join(weaknesses),
                    advice=writing_feedback[:200],
                )
            )
        result = decide_outcome(
            score,
            per_skill,
            concrete or preliminary.failed_points,
            thresholds=settings.thresholds,
        )

    return {
        "exam_submission": submission,
        "exam_result": result,
        "exam_writing_feedback": writing_feedback,
        "failed_points": result.failed_points,
    }


def review_exam(state: TeacherState, config: RunnableConfig) -> dict:
    """Explain the result, then hand over to promotion or remediation."""
    llm = resolve_llm(config)
    level = state.get("level", "B1")
    result = state.get("exam_result")
    if result is None:
        raise RuntimeError("review_exam called without a result")

    text = to_text(
        llm.invoke(
            [
                SystemMessage(content=results_prompt(level, result)),
                HumanMessage(content="Give me my result."),
            ]
        )
    )
    if not text:
        text = result.summary

    return {
        "teacher_message": text,
        "phase": "review",
        "messages": [AIMessage(content=text)],
        "next_action": "advance" if result.passed else "remediate",
    }


def advance_level(state: TeacherState, config: RunnableConfig) -> dict:
    """Promote the student, carrying a conservative mastery baseline forward."""
    level = state.get("level", "B1")
    following = next_level(level)
    history = (
        [*(state.get("level_history") or []), following]
        if following
        else list(state.get("level_history") or [])
    )

    if following is None:
        text = (
            "That is the last exam on the ladder: you have finished C2. "
            "From here the work is maintenance and style, and you can say you are done."
        )
        return {
            "graduated": True,
            "phase": "done",
            "level_history": history,
            "teacher_message": text,
            "messages": [AIMessage(content=text)],
            "next_action": "end",
        }

    mastery = state.get("mastery") or new_mastery()
    mean = sum(float(entry.get("score", 0.0)) for entry in mastery.values()) / max(len(mastery), 1)
    baseline = round(min(max(mean * 0.75, 0.45), 0.60), 4)
    plan = topics_for(following)

    return {
        "level": following,
        "level_history": history,
        "mastery": new_mastery(baseline),
        "plan": plan,
        "current_topic": plan[0],
        "topics_seen": [plan[0]["id"]],
        "topic_progress": 0.0,
        "topic_complete": False,
        "lessons_completed": 0,
        "review_mode": False,
        "exam_result": state.get("exam_result"),
        "exam_submission": None,
        "failed_points": [],
        "cooldown_until": int(state.get("turns", 0)) + 2,
        "next_action": "teach",
    }


def _topic_for_skill(level: str, skill: str) -> dict:
    plan = topics_for(level)
    needle = skill.lower()
    for topic in plan:
        haystack = " ".join([topic["title"], topic["can_do"], *topic["grammar"]]).lower()
        if needle in haystack:
            return topic
    return plan[0]


def remediation(state: TeacherState, config: RunnableConfig) -> dict:
    """Build a targeted review plan and start it immediately."""
    llm = resolve_llm(config)
    level = state.get("level", "B1")
    result = state.get("exam_result")
    points = list(state.get("failed_points") or (result.failed_points if result else []))
    tasks = build_remediation(points, limit=3)
    topic = _topic_for_skill(level, tasks[0].skill) if tasks else topics_for(level)[0]

    plan = llm.with_structured_output(RemediationPlan).invoke(
        with_user_turn(remediation_prompt(level, tasks, topic), None, "Write the review plan now.")
    )

    activities = "\n".join(
        f"{index}. {activity}" for index, activity in enumerate(plan.activities, 1)
    )
    message = plan.message.strip()
    if activities:
        message = f"{message}\n\nHere is our plan:\n{activities}"

    return {
        "teacher_message": message,
        "phase": "teaching",
        "messages": [AIMessage(content=message)],
        "remediation_activities": plan.activities,
        "current_topic": topic,
        "topic_progress": 0.0,
        "topic_complete": False,
        "review_mode": True,
        "next_action": "teach",
    }
