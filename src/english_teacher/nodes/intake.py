"""Level choice and the short placement quiz that seeds the mastery model."""

from __future__ import annotations

import re

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from ..cefr import normalise_level
from ..context import with_user_turn
from ..languages import get_language
from ..llm import resolve_llm
from ..policy import apply_observed, parse_mcq_submission
from ..prompts import placement_prompt
from ..rendering import render_quiz
from ..schemas import PlacementQuiz
from ..state import TeacherState

_PLACEMENT_SKILLS = {"grammar", "vocabulary", "reading"}
_LEVEL_IN_TEXT = re.compile(r"\b([abc][12])\b", re.IGNORECASE)
_NAME_IN_TEXT = re.compile(
    r"(?:my name is|i am|i'm|call me|je m'appelle|moi c'est)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]{1,20})",
    re.IGNORECASE,
)


def _level_from_text(text: str) -> str | None:
    match = _LEVEL_IN_TEXT.search(text or "")
    if not match:
        return None
    return normalise_level(match.group(1))


def intake(state: TeacherState, config: RunnableConfig) -> dict:
    """Resolve the starting level, build the syllabus plan, greet the student."""
    language = get_language(state.get("language"))
    raw_level = state.get("level")
    level = normalise_level(raw_level)
    note = ""
    name = (state.get("student_name") or "").strip()

    if level is None:
        reply = str(interrupt({"kind": "level_choice", "prompt": language.level_menu()}))
        level = normalise_level(reply) or _level_from_text(reply)
        if not name:
            found = _NAME_IN_TEXT.search(reply)
            name = found.group(1).capitalize() if found else ""
        if level is None:
            level = "B1"
            note = language.note_fallback

    greeting = language.greeting.format(
        name=f", {name}" if name else "",
        teacher=language.teacher,
        level=level,
        label=language.label(level),
        note=note,
    )

    goal = (state.get("goal") or "").strip()
    if goal:
        greeting += language.goal_line.format(goal=goal.rstrip("."))
    greeting += language.placement_line

    plan = language.topics(level)
    return {
        "student_name": name,
        "language": language.code,
        "level": level,
        "level_history": [*(state.get("level_history") or []), level],
        "plan": plan,
        "current_topic": plan[0],
        "topics_seen": [plan[0]["id"]],
        "phase": "placement",
        "teacher_message": greeting,
        # messages are appended by placement_quiz so the greeting is not duplicated
    }


def _sanitise_quiz(quiz: PlacementQuiz) -> PlacementQuiz | None:
    questions = []
    for index, question in enumerate(quiz.questions[:3], start=1):
        choices = {str(k).upper(): str(v) for k, v in question.choices.items()}
        if len(choices) != 4 or question.answer.upper() not in choices:
            continue
        skill = question.skill if question.skill in _PLACEMENT_SKILLS else "grammar"
        questions.append(
            question.model_copy(
                update={
                    "id": index,
                    "skill": skill,
                    "answer": question.answer.upper(),
                    "choices": choices,
                }
            )
        )
    if not questions:
        return None
    return quiz.model_copy(update={"questions": questions})


def placement_quiz(state: TeacherState, config: RunnableConfig) -> dict:
    """Ask three level-appropriate questions. Skipped if the model returns junk."""
    llm = resolve_llm(config)
    language = get_language(state.get("language"))
    level = state.get("level", "B1")

    quiz: PlacementQuiz | None = None
    try:
        raw = llm.with_structured_output(PlacementQuiz).invoke(
            with_user_turn(
                placement_prompt(level, language), None, "Write the placement check now."
            )
        )
        quiz = _sanitise_quiz(raw)
    except Exception:  # noqa: BLE001 - bad model output: placement is optional
        quiz = None

    if quiz is None:
        return {"placement_quiz": None, "phase": "teaching"}

    message = f"{state.get('teacher_message', '')}\n\n{render_quiz(quiz, language)}"
    return {
        "placement_quiz": quiz,
        "teacher_message": message,
        "phase": "placement",
        "messages": [AIMessage(content=message)],
    }


def grade_placement(state: TeacherState, config: RunnableConfig) -> dict:
    """Score the placement answers and seed every skill's mastery estimate."""
    quiz = state.get("placement_quiz")
    mastery = state.get("mastery") or {}
    if not quiz or not quiz.questions:
        return {"next_action": "teach"}

    answers = parse_mcq_submission(state.get("student_message", ""), len(quiz.questions))
    observed: dict[str, float] = {}
    correct = 0
    for question in quiz.questions:
        hit = answers.get(question.id) == question.answer.upper()
        correct += int(hit)
        observed[question.skill] = 1.0 if hit else 0.0

    updated = apply_observed(mastery, observed, alpha=0.5)
    summary = f"{correct}/{len(quiz.questions)} correct on the placement check."
    return {"mastery": updated, "placement_summary": summary, "next_action": "teach"}
