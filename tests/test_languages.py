"""Registry tests: the French teacher is a real language, not a relabelled English one."""

from __future__ import annotations

from test_graph import b1_exam, placement_quiz

from english_teacher.cefr import LEVELS
from english_teacher.languages import (
    ENGLISH,
    FRENCH,
    LANGUAGES,
    get_language,
    language_catalogue,
    normalise_language,
    topics_for,
)
from english_teacher.prompts import placement_prompt, teaching_prompt, tutor_persona
from english_teacher.rendering import render_exam, render_quiz


def test_both_languages_are_registered_with_a_full_syllabus():
    assert set(LANGUAGES) == {"en", "fr"}
    for language in (ENGLISH, FRENCH):
        assert tuple(language.syllabus) == LEVELS
        for level in LEVELS:
            topics = language.topics(level)
            assert len(topics) == 5
            assert all(topic["title"] and topic["can_do"] for topic in topics)


def test_french_topic_ids_cannot_collide_with_english_ones():
    french_ids = [topic["id"] for level in LEVELS for topic in FRENCH.topics(level)]
    english_ids = [topic["id"] for level in LEVELS for topic in ENGLISH.topics(level)]
    assert len(french_ids) == 30
    assert all(topic_id.startswith("FR-") for topic_id in french_ids)
    assert not set(french_ids) & set(english_ids)


def test_aliases_resolve_to_the_right_language():
    for value in ("fr", "FR", "fra", "fre", "french", "francais", "français"):
        assert normalise_language(value) == "fr"
    for value in ("en", "ENG", "english", "anglais"):
        assert normalise_language(value) == "en"
    assert normalise_language("deutsch") is None
    assert normalise_language(None) is None
    assert get_language("français") is FRENCH
    assert get_language("") is ENGLISH
    assert get_language("nope") is ENGLISH


def test_catalogue_describes_both_teachers():
    catalogue = {item["code"]: item for item in language_catalogue()}
    assert catalogue["en"]["teacher"] == "Ms. Rivera"
    assert catalogue["fr"]["teacher"] == "Mme Laurent"
    assert catalogue["fr"]["native_name"] == "Français"
    assert catalogue["fr"]["initials"] == "ML"


def test_level_labels_are_localised():
    assert FRENCH.label("A1") == "Débutant"
    assert FRENCH.label("C2") == "Maîtrise"
    assert ENGLISH.label("A1") == "Beginner"
    assert {item["code"] for item in FRENCH.levels()} == set(LEVELS)


def test_topics_for_returns_a_copy():
    topics = topics_for(FRENCH, "A1")
    topics[0]["title"] = "changed"
    assert FRENCH.topics("A1")[0]["title"] == "Se présenter"


def test_french_prompts_name_the_french_teacher_and_language():
    persona = tutor_persona("B1", FRENCH)
    assert "Mme Laurent" in persona
    assert "Speak French only" in persona
    assert "English gloss in brackets" in persona
    assert "Ms. Rivera" not in persona

    placement = placement_prompt("A2", FRENCH)
    assert "in French" in placement
    assert "A2" in placement

    topic = FRENCH.topics("B1")[0]
    teaching = teaching_prompt(
        language=FRENCH,
        level="B1",
        topic=topic,
        mastery_line="grammar 40%",
        weak_skills=["grammar"],
        review_mode=False,
        remediation=[],
        last_feedback="",
        placement_summary="",
    )
    assert "Récits et imparfait" in teaching
    assert "Intermédiaire" in teaching
    assert "Mme Laurent" in teaching


def test_french_rendering_localises_chrome_but_keeps_machine_markers():
    quiz = render_quiz(placement_quiz(), FRENCH)
    assert "Réponds comme ceci" in quiz
    assert "Answer like this" not in quiz

    exam = render_exam(b1_exam(), FRENCH)
    assert "EXAMEN FINAL - B1 Final" in exam
    assert "TÂCHE D'ÉCRITURE" in exam
    assert "Critères :" in exam
    assert "ANSWERS:" in exam
    assert "WRITING:" in exam

    english_exam = render_exam(b1_exam(), ENGLISH)
    assert "FINAL EXAM - B1 Final" in english_exam
    assert "WRITING TASK" in english_exam
