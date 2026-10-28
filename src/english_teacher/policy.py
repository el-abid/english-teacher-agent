"""Deterministic teaching policy: mastery maths, readiness gate, exam outcome.

Design rule: the LLM gathers evidence and writes feedback, this module decides.
Promotion must never depend on a model being in a generous mood.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from .cefr import SKILLS
from .schemas import ExamResult, FailedPoint


class SkillState(dict):
    """``{"score": 0..1, "evidence": int}`` kept as a plain dict for JSON state."""


@dataclass(frozen=True)
class Thresholds:
    """Tune here to make the course harder or easier."""

    min_lessons: int = 3
    min_skill: float = 0.60
    mean_skill: float = 0.68
    skill_floor: float = 0.45
    min_evidence: int = 2
    pass_mark: float = 0.70
    exam_skill_floor: float = 0.50


@dataclass
class ReadinessVerdict:
    ready: bool
    reasons: list[str] = field(default_factory=list)
    weak_skills: list[str] = field(default_factory=list)
    mean_score: float = 0.0

    @property
    def summary(self) -> str:
        if self.ready:
            return f"All skills solid (average {self.mean_score:.0%})."
        return "Not yet ready: " + "; ".join(self.reasons)


def new_mastery(initial: float = 0.35) -> dict[str, SkillState]:
    """Cold-start every skill at ``initial`` with zero evidence."""
    return {skill: {"score": initial, "evidence": 0} for skill in SKILLS}


def ewma(current: float, observed: float, alpha: float = 0.4) -> float:
    """Exponential moving average, clamped to [0, 1].

    Recent answers matter more than old ones, but a single bad day cannot erase
    a term of good work.
    """
    alpha = min(max(alpha, 0.0), 1.0)
    value = (1 - alpha) * current + alpha * observed
    return round(min(max(value, 0.0), 1.0), 6)


def apply_observed(
    mastery: dict[str, SkillState],
    scores: dict[str, float],
    alpha: float = 0.4,
) -> dict[str, SkillState]:
    """Return a new mastery map with ``scores`` folded in."""
    updated = {skill: dict(entry) for skill, entry in mastery.items()}
    for skill, raw in scores.items():
        if skill not in updated or not isinstance(raw, (int, float)):
            continue
        observed = min(max(float(raw), 0.0), 1.0)
        updated[skill]["score"] = ewma(updated[skill]["score"], observed, alpha)
        updated[skill]["evidence"] = updated[skill].get("evidence", 0) + 1
    return updated


def evaluate_readiness(
    mastery: dict[str, SkillState],
    lessons_completed: int,
    thresholds: Thresholds | None = None,
) -> ReadinessVerdict:
    """The numeric gate that must pass before the tutor offers the level exam."""
    t = thresholds or Thresholds()
    reasons: list[str] = []
    weak: list[str] = []

    if lessons_completed < t.min_lessons:
        missing = t.min_lessons - lessons_completed
        reasons.append(f"needs {missing} more lesson(s) before the exam")

    for skill in SKILLS:
        entry = mastery.get(skill, {})
        score = float(entry.get("score", 0.0))
        evidence = int(entry.get("evidence", 0))
        if evidence < t.min_evidence:
            reasons.append(
                f"{skill}: little evidence yet ({evidence}/{t.min_evidence} observations)"
            )
        elif score < t.min_skill:
            weak.append(skill)
            reasons.append(f"{skill}: {score:.0%} is below the {t.min_skill:.0%} bar")
        elif score < t.skill_floor:
            weak.append(skill)
            reasons.append(f"{skill}: {score:.0%} is far below the {t.skill_floor:.0%} floor")

    scores = [float(mastery.get(skill, {}).get("score", 0.0)) for skill in SKILLS]
    mean_score = sum(scores) / len(scores) if scores else 0.0
    if mean_score < t.mean_skill:
        reasons.append(f"average {mean_score:.0%} below the {t.mean_skill:.0%} target")

    if any(float(mastery.get(skill, {}).get("score", 0.0)) < t.skill_floor for skill in SKILLS):
        reasons.append(f"at least one skill is under the {t.skill_floor:.0%} floor")

    return ReadinessVerdict(
        ready=not reasons,
        reasons=reasons,
        weak_skills=weak,
        mean_score=round(mean_score, 4),
    )


# --------------------------------------------------------------------------- #
# Exam grading
# --------------------------------------------------------------------------- #
_MCQ_PATTERN = re.compile(r"(\d{1,2})\s*[).:\-=]?\s*([A-Da-d])(?![A-Za-z])")


def parse_mcq_submission(text: str, valid_total: int) -> dict[int, str]:
    """Parse '1B 2) c 3. A' into ``{1: 'B', 2: 'C', 3: 'A'}``.

    Students type answers in every shape imaginable, so be permissive and drop
    anything that does not map to a real question number.
    """
    answers: dict[int, str] = {}
    for number, letter in _MCQ_PATTERN.findall(text or ""):
        index = int(number)
        if 1 <= index <= valid_total:
            answers[index] = letter.upper()
    return answers


def score_mcq(submission: dict[int, str], answer_key: dict[int, str]) -> tuple[int, int]:
    """Return ``(correct, total)``; unanswered questions count as wrong."""
    correct = sum(1 for qid, letter in answer_key.items() if submission.get(qid) == letter.upper())
    return correct, len(answer_key)


def compute_exam_score(
    mcq_correct: int,
    mcq_total: int,
    writing_score: float,
    mcq_weight: float = 0.6,
) -> float:
    """Weighted total of the objective section and the writing task."""
    if mcq_total <= 0:
        raise ValueError("exam has no objective items to grade")
    mcq_ratio = min(max(mcq_correct / mcq_total, 0.0), 1.0)
    writing_score = min(max(float(writing_score), 0.0), 1.0)
    weight = min(max(mcq_weight, 0.0), 1.0)
    return round(weight * mcq_ratio + (1 - weight) * writing_score, 4)


def decide_outcome(
    score: float,
    per_skill: dict[str, float],
    failed_points: Iterable[FailedPoint] | None = None,
    thresholds: Thresholds | None = None,
) -> ExamResult:
    """Turn a score into a promotion decision plus the review list for a retake."""
    t = thresholds or Thresholds()
    points = list(failed_points or [])
    known = {p.skill for p in points}

    for skill, skill_score in per_skill.items():
        if skill_score < t.exam_skill_floor and skill not in known:
            points.append(
                FailedPoint(
                    skill=skill,
                    point=f"{skill} section scored {skill_score:.0%}",
                    advice=f"Review the {skill} exercises from this level before retaking.",
                )
            )
            known.add(skill)

    passed = score >= t.pass_mark and not points

    if not passed and not points:
        # Failing on total score alone: point at the weakest measured skill.
        weakest = min(per_skill.items(), key=lambda item: item[1], default=("grammar", 0.0))
        points.append(
            FailedPoint(
                skill=weakest[0],
                point=f"overall {score:.0%}, weakest area {weakest[0]} at {weakest[1]:.0%}",
                advice="Revisit the level's core topics, then retake the exam.",
            )
        )

    return ExamResult(
        score=round(float(score), 4),
        passed=passed,
        per_skill={k: round(float(v), 4) for k, v in per_skill.items()},
        failed_points=points,
        summary=(
            f"Passed with {score:.0%}."
            if passed
            else f"Not yet: {score:.0%}, needs {t.pass_mark:.0%}."
        ),
    )


_WRITING_MARKER = re.compile(r"^\s*writing\b\s*[:\-]?\s*", re.IGNORECASE | re.MULTILINE)
_ANSWER_LINE = re.compile(r"(?:q?\d{1,2}\s*[).:\-=]?\s*[A-Da-d]\s*[,;]?\s*)+", re.IGNORECASE)


def split_exam_submission(text: str) -> tuple[str, str]:
    """Separate the answer key part from the writing sample.

    Preferred format is ``ANSWERS: 1B 2C ...`` then a ``WRITING:`` line. When the
    student ignores the format, answer-looking lines are kept and every other
    line is treated as their writing.
    """
    raw = (text or "").strip()
    if not raw:
        return "", ""

    marker = _WRITING_MARKER.search(raw)
    if marker:
        return raw[: marker.start()].strip(), raw[marker.end() :].strip()

    answer_lines: list[str] = []
    prose_lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped and _ANSWER_LINE.fullmatch(stripped):
            answer_lines.append(stripped)
        elif stripped:
            prose_lines.append(stripped)
    return " ".join(answer_lines), "\n".join(prose_lines)


def build_remediation(failed_points: Iterable[FailedPoint], limit: int = 3) -> list[FailedPoint]:
    """One review task per skill, first-come order, capped at ``limit``."""
    tasks: list[FailedPoint] = []
    seen: set[str] = set()
    for point in failed_points:
        if point.skill in seen:
            continue
        seen.add(point.skill)
        tasks.append(point)
        if len(tasks) >= limit:
            break
    return tasks
