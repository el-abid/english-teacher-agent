"""Runtime settings, all overridable from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .policy import Thresholds


@dataclass(frozen=True)
class Settings:
    model: str = "google_genai:gemini-3.1-flash-lite"
    temperature: float = 0.3
    db_path: str | None = None
    alpha: float = 0.4  # mastery smoothing: higher = reacts faster to new answers
    exam_items: int = 8
    exam_mcq_weight: float = 0.6
    offer_cooldown_turns: int = 3
    max_context_messages: int = 8
    thresholds: Thresholds = field(default_factory=Thresholds)


def load_env_file(path: str = ".env") -> None:
    """Minimal .env loader: real environment variables always win."""
    file = Path(path)
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_settings() -> Settings:
    """Read settings at call time so tests and the CLI can override freely."""
    return Settings(
        model=os.getenv("ENGLISH_TEACHER_MODEL", Settings.model),
        temperature=float(os.getenv("ENGLISH_TEACHER_TEMPERATURE", Settings.temperature)),
        db_path=os.getenv("ENGLISH_TEACHER_DB") or None,
        alpha=float(os.getenv("ENGLISH_TEACHER_ALPHA", Settings.alpha)),
        exam_items=int(os.getenv("ENGLISH_TEACHER_EXAM_ITEMS", Settings.exam_items)),
        exam_mcq_weight=float(
            os.getenv("ENGLISH_TEACHER_EXAM_MCQ_WEIGHT", Settings.exam_mcq_weight)
        ),
        offer_cooldown_turns=int(
            os.getenv("ENGLISH_TEACHER_OFFER_COOLDOWN", Settings.offer_cooldown_turns)
        ),
        thresholds=Thresholds(
            min_lessons=int(os.getenv("ENGLISH_TEACHER_MIN_LESSONS", Thresholds.min_lessons)),
            min_skill=float(os.getenv("ENGLISH_TEACHER_MIN_SKILL", Thresholds.min_skill)),
            pass_mark=float(os.getenv("ENGLISH_TEACHER_PASS_MARK", Thresholds.pass_mark)),
        ),
    )
