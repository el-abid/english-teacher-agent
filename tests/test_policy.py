"""Tests for the deterministic core: mastery, readiness gate, exam scoring.

These rules decide whether a student is promoted, so they are tested without any
LLM in the loop.
"""

from __future__ import annotations

import pytest

from english_teacher.cefr import LEVELS, SKILLS, SYLLABUS, next_level, normalise_level
from english_teacher.policy import (
    Thresholds,
    apply_observed,
    build_remediation,
    compute_exam_score,
    decide_outcome,
    evaluate_readiness,
    ewma,
    new_mastery,
    parse_mcq_submission,
    score_mcq,
    split_exam_submission,
)
from english_teacher.schemas import FailedPoint


# --------------------------------------------------------------------------- #
# Mastery bookkeeping
# --------------------------------------------------------------------------- #
def test_ewma_moves_towards_observation():
    assert ewma(0.5, 1.0, alpha=0.4) == pytest.approx(0.7)
    assert ewma(0.5, 0.1, alpha=0.4) == pytest.approx(0.34)


def test_ewma_stays_inside_unit_interval():
    assert ewma(0.99, 1.0, alpha=1.0) == 1.0
    assert ewma(0.01, 0.0, alpha=1.0) == 0.0
    assert 0.0 <= ewma(0.3, 1.0, alpha=0.4) <= 1.0


def test_new_mastery_covers_every_skill():
    mastery = new_mastery(initial=0.4)
    assert set(mastery) == set(SKILLS)
    assert all(entry["score"] == 0.4 and entry["evidence"] == 0 for entry in mastery.values())


def test_apply_observed_updates_only_reported_skills():
    mastery = new_mastery(0.5)
    updated = apply_observed(mastery, {"grammar": 1.0})

    assert updated["grammar"]["evidence"] == 1
    assert updated["grammar"]["score"] == pytest.approx(0.7)
    assert updated["reading"]["evidence"] == 0
    assert mastery["grammar"]["evidence"] == 0, "input state must not be mutated"


def test_apply_observed_ignores_unknown_skills_and_clamps():
    mastery = new_mastery(0.5)
    updated = apply_observed(mastery, {"grammar": 42.0, "telepathy": 1.0})

    assert updated["grammar"]["score"] == pytest.approx(0.7)
    assert 0.0 <= updated["grammar"]["score"] <= 1.0
    assert "telepathy" not in updated


# --------------------------------------------------------------------------- #
# Readiness gate
# --------------------------------------------------------------------------- #
def _mastery(score: float, evidence: int = 3) -> dict[str, dict[str, float | int]]:
    return {skill: {"score": score, "evidence": evidence} for skill in SKILLS}


def test_not_ready_before_minimum_lessons():
    verdict = evaluate_readiness(_mastery(0.95), lessons_completed=1)
    assert verdict.ready is False
    assert any("lesson" in reason for reason in verdict.reasons)


def test_ready_when_every_skill_is_strong():
    verdict = evaluate_readiness(_mastery(0.9), lessons_completed=5)
    assert verdict.ready is True
    assert verdict.reasons == []


def test_one_weak_skill_blocks_promotion():
    mastery = _mastery(0.9)
    mastery["writing"] = {"score": 0.4, "evidence": 3}

    verdict = evaluate_readiness(mastery, lessons_completed=6)

    assert verdict.ready is False
    assert verdict.weak_skills == ["writing"]


def test_high_score_without_evidence_is_not_ready():
    mastery = _mastery(0.9, evidence=0)
    verdict = evaluate_readiness(mastery, lessons_completed=8)
    assert verdict.ready is False
    assert "little evidence" in " ".join(verdict.reasons)


def test_low_average_blocks_even_without_hard_failure():
    mastery = {skill: {"score": 0.62, "evidence": 4} for skill in SKILLS}
    verdict = evaluate_readiness(mastery, lessons_completed=10)
    assert verdict.ready is False
    assert any("average" in reason.lower() for reason in verdict.reasons)


def test_thresholds_are_configurable():
    strict = Thresholds(min_lessons=20, min_skill=0.95, mean_skill=0.95)
    assert evaluate_readiness(_mastery(0.9), lessons_completed=19, thresholds=strict).ready is False


# --------------------------------------------------------------------------- #
# MCQ parsing and scoring
# --------------------------------------------------------------------------- #
def test_parse_mcq_accepts_common_formats():
    parsed = parse_mcq_submission("1B 2) c 3. A 4: d", valid_total=4)
    assert parsed == {1: "B", 2: "C", 3: "A", 4: "D"}


def test_parse_mcq_ignores_noise_and_out_of_range():
    parsed = parse_mcq_submission("Q1 = A, Q2 = B, Q99 = C, no idea", valid_total=2)
    assert parsed == {1: "A", 2: "B"}


def test_parse_mcq_empty_input():
    assert parse_mcq_submission("", valid_total=5) == {}


def test_score_mcq_counts_only_correct_letters():
    key = {1: "B", 2: "C", 3: "A"}
    assert score_mcq({1: "B", 2: "A", 3: "A"}, key) == (2, 3)
    assert score_mcq({1: "B"}, key) == (1, 3)
    assert score_mcq({}, key) == (0, 3)


def test_split_submission_prefers_explicit_writing_marker():
    mcq, writing = split_exam_submission("ANSWERS: 1B 2C 3A\nWRITING:\nMy town is great.")
    assert "1B" in mcq and "2C" in mcq
    assert writing == "My town is great."


def test_split_submission_without_marker_keeps_prose_as_writing():
    mcq, writing = split_exam_submission("1B 2C 3A\nI believe that school uniforms are useful.")
    assert mcq == "1B 2C 3A"
    assert writing == "I believe that school uniforms are useful."


def test_split_submission_handles_empty_input():
    assert split_exam_submission("") == ("", "")


# --------------------------------------------------------------------------- #
# Exam result
# --------------------------------------------------------------------------- #
def test_exam_score_blends_mcq_and_writing():
    assert compute_exam_score(8, 10, 0.5, mcq_weight=0.6) == pytest.approx(0.68)
    assert compute_exam_score(6, 10, 0.5) == pytest.approx(0.56)


def test_exam_score_rejects_empty_mcq_section():
    with pytest.raises(ValueError):
        compute_exam_score(0, 0, 0.5, mcq_weight=0.6)


def test_pass_needs_score_and_no_failed_skill():
    passed = decide_outcome(0.82, {"grammar": 0.85, "reading": 0.8, "writing": 0.8})
    assert passed.passed is True
    assert passed.failed_points == []

    weak = decide_outcome(0.82, {"grammar": 0.85, "reading": 0.3, "writing": 0.8})
    assert weak.passed is False
    assert [p.skill for p in weak.failed_points] == ["reading"]


def test_fail_below_pass_mark():
    result = decide_outcome(0.55, {"grammar": 0.55})
    assert result.passed is False
    assert result.failed_points, "a failed exam must produce review points"


def test_existing_failed_points_are_kept_and_not_duplicated():
    points = [FailedPoint(skill="writing", point="Weak topic sentences")]
    result = decide_outcome(0.8, {"writing": 0.4}, failed_points=points)
    assert result.passed is False
    assert len(result.failed_points) == 1
    assert result.failed_points[0].point == "Weak topic sentences"


def test_build_remediation_dedupes_and_caps():
    points = [
        FailedPoint(skill="grammar", point="third conditional"),
        FailedPoint(skill="grammar", point="mixed conditional"),
        FailedPoint(skill="writing", point="paragraph structure"),
        FailedPoint(skill="reading", point="inference"),
        FailedPoint(skill="vocabulary", point="collocation"),
    ]
    tasks = build_remediation(points, limit=3)
    assert [p.skill for p in tasks] == ["grammar", "writing", "reading"]


# --------------------------------------------------------------------------- #
# CEFR data
# --------------------------------------------------------------------------- #
def test_next_level_walks_the_ladder_and_stops_at_c2():
    assert next_level("A1") == "A2"
    assert next_level("B2") == "C1"
    assert next_level("C2") is None


def test_every_level_has_teachable_topics():
    for level in LEVELS:
        topics = SYLLABUS[level]
        assert len(topics) >= 4, f"{level} needs at least four topics"
        assert len({t["id"] for t in topics}) == len(topics)
        for topic in topics:
            assert topic["can_do"] and topic["grammar"] and topic["vocabulary"]


def test_normalise_level_tolerates_sloppy_input():
    assert normalise_level(" b1 ") == "B1"
    assert normalise_level("c2") == "C2"
    assert normalise_level("Z9") is None
    assert normalise_level(None) is None
