"""Plain-text rendering of structured objects, shown to the student as-is."""

from __future__ import annotations

from typing import Any

from .languages import Language
from .schemas import Exam, PlacementQuiz


def to_text(response: Any) -> str:
    """Flatten a chat response whose content may be a string or content blocks."""
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text", "")))
            else:
                parts.append(str(part))
        content = " ".join(parts)
    return str(content).strip()


def render_quiz(quiz: PlacementQuiz, language: Language) -> str:
    lines = [quiz.intro.strip(), ""]
    for question in quiz.questions:
        lines.append(f"{question.id}. {question.prompt}")
        for key, value in question.choices.items():
            lines.append(f"   {key}) {value}")
    lines.append("")
    lines.append(language.quiz_hint)
    return "\n".join(line for line in lines if line is not None)


def render_exam(exam: Exam, language: Language) -> str:
    lines = [language.exam_header.format(title=exam.title), "", exam.instructions.strip(), ""]
    for item in exam.items:
        lines.append(f"{item.id}. [{item.skill}] {item.prompt}")
        for key, value in item.choices.items():
            lines.append(f"   {key}) {value}")
        lines.append("")
    lines.append(f"{language.writing_label}\n{exam.writing_prompt}")
    if exam.writing_criteria:
        lines.append(f"{language.criteria_label} " + ", ".join(exam.writing_criteria))
    lines.append("")
    lines.append(language.exam_reply_hint)
    return "\n".join(lines)
