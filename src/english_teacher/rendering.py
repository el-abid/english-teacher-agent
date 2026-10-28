"""Plain-text rendering of structured objects, shown to the student as-is."""

from __future__ import annotations

from typing import Any

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


def render_quiz(quiz: PlacementQuiz) -> str:
    lines = [quiz.intro.strip(), ""]
    for question in quiz.questions:
        lines.append(f"{question.id}. {question.prompt}")
        for key, value in question.choices.items():
            lines.append(f"   {key}) {value}")
    lines.append("")
    lines.append("Answer like this: 1B 2C 3A")
    return "\n".join(line for line in lines if line is not None)


def render_exam(exam: Exam) -> str:
    lines = [f"FINAL EXAM - {exam.title}", "", exam.instructions.strip(), ""]
    for item in exam.items:
        lines.append(f"{item.id}. [{item.skill}] {item.prompt}")
        for key, value in item.choices.items():
            lines.append(f"   {key}) {value}")
        lines.append("")
    lines.append(f"WRITING TASK\n{exam.writing_prompt}")
    if exam.writing_criteria:
        lines.append("Criteria: " + ", ".join(exam.writing_criteria))
    lines.append("")
    lines.append("Reply in this format:\nANSWERS: 1B 2C 3A ...\nWRITING:\n<your text>")
    return "\n".join(lines)
