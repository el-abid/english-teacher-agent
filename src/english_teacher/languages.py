"""Languages the tutor can teach, with their teacher persona and syllabus.

Adding a language means adding one ``Language`` here plus a syllabus module. The
graph, the policy and the exam code are language-agnostic: they only read the
level, the topic and the target language name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .cefr import LEVEL_LABELS, LEVELS, SYLLABUS, Topic
from .syllabus_fr import FRENCH_SYLLABUS

FRENCH_LEVEL_LABELS: Final[dict[str, str]] = {
    "A1": "Débutant",
    "A2": "Élémentaire",
    "B1": "Intermédiaire",
    "B2": "Intermédiaire avancé",
    "C1": "Avancé",
    "C2": "Maîtrise",
}


@dataclass(frozen=True)
class Language:
    """Everything that changes when the student picks another language."""

    code: str
    name: str  # English name, used inside prompts: "French"
    native_name: str  # shown in the picker: "Français"
    teacher: str  # persona name shown to the student
    initials: str  # avatar text
    level_labels: dict[str, str]
    syllabus: dict[str, list[Topic]]
    greeting: str  # "Hi{name}!" / "Bonjour{name} !"
    goal_line: str  # appended when the student gave a goal
    placement_line: str  # last sentence of the intake greeting
    note_fallback: str  # used when the level could not be read
    menu_title: str
    menu_footer: str
    quiz_hint: str
    exam_header: str  # format: {title}
    writing_label: str
    criteria_label: str
    exam_reply_hint: str
    teach_fallback: str  # used only when the model returns empty text
    offer_fallback: str
    finished_line: str
    plan_header: str
    persona_note: str = ""  # extra hard rule in the persona

    # ------------------------------------------------------------------ data
    def label(self, level: str) -> str:
        return self.level_labels.get(level, "")

    def topics(self, level: str) -> list[Topic]:
        """Copy of the syllabus for ``level``; raises on an unknown level."""
        return [dict(topic) for topic in self.syllabus[level]]  # type: ignore[misc]

    def levels(self) -> list[dict[str, str]]:
        return [{"code": code, "label": self.level_labels[code]} for code in LEVELS]

    def describe(self) -> dict[str, str]:
        return {
            "code": self.code,
            "name": self.name,
            "native_name": self.native_name,
            "teacher": self.teacher,
            "initials": self.initials,
        }

    def level_menu(self) -> str:
        rows = []
        for index in range(0, len(LEVELS), 2):
            left = LEVELS[index]
            right = LEVELS[index + 1]
            rows.append(
                f"  {left} {self.level_labels[left]:<22}{right} {self.level_labels[right]}"
            )
        body = "\n".join(rows)
        return f"{self.menu_title}\n\n{body}\n\n{self.menu_footer}"


ENGLISH: Final[Language] = Language(
    code="en",
    name="English",
    native_name="English",
    teacher="Ms. Rivera",
    initials="MR",
    level_labels=LEVEL_LABELS,
    syllabus=SYLLABUS,
    greeting="Hi{name}! I'm {teacher}. From today we work at {level}, {label}.{note}",
    goal_line=" You said your goal is {goal}, so I will aim every task at that.",
    placement_line=(
        " Before lesson one, three quick questions so I don't teach you what you already know."
    ),
    note_fallback=" I could not read a level in your reply, so we start at B1.",
    menu_title="Which level do you want to start at?",
    menu_footer="Reply with one code (for example: B1).",
    quiz_hint="Answer like this: 1B 2C 3A",
    exam_header="FINAL EXAM - {title}",
    writing_label="WRITING TASK",
    criteria_label="Criteria:",
    exam_reply_hint=(
        "Reply in this format:\nANSWERS: 1B 2C 3A ...\nWRITING:\n<your text>"
    ),
    teach_fallback="Let's work on {topic}. Tell me what you already know about it.",
    offer_fallback=(
        "Your work at {level} looks solid. Do you want to take the {level} exam now? "
        "It has {items} questions and one writing task. You can say not yet."
    ),
    finished_line=(
        "That is the last exam on the ladder: you have finished C2. "
        "From here the work is maintenance and style, and you can say you are done."
    ),
    plan_header="Here is our plan:",
)

FRENCH: Final[Language] = Language(
    code="fr",
    name="French",
    native_name="Français",
    teacher="Mme Laurent",
    initials="ML",
    level_labels=FRENCH_LEVEL_LABELS,
    syllabus=FRENCH_SYLLABUS,
    greeting=(
        "Bonjour{name} ! Je suis {teacher}. À partir d'aujourd'hui, nous travaillons "
        "au niveau {level}, {label}.{note}"
    ),
    goal_line=" Tu m'as dit que ton objectif était {goal}, donc j'orienterai chaque exercice.",
    placement_line=(
        " Avant la première leçon, trois questions rapides pour ne pas t'enseigner "
        "ce que tu sais déjà."
    ),
    note_fallback=" Je n'ai pas lu de niveau dans ta réponse, alors nous commençons au niveau B1.",
    menu_title="À quel niveau veux-tu commencer ?",
    menu_footer="Réponds avec un code (par exemple : B1).",
    quiz_hint="Réponds comme ceci : 1B 2C 3A",
    exam_header="EXAMEN FINAL - {title}",
    writing_label="TÂCHE D'ÉCRITURE",
    criteria_label="Critères :",
    exam_reply_hint=(
        "Réponds dans ce format :\nANSWERS: 1B 2C 3A ...\nWRITING:\n<ton texte>"
    ),
    teach_fallback="Travaillons sur « {topic} ». Dis-moi ce que tu sais déjà.",
    offer_fallback=(
        "Ton travail au niveau {level} est solide. Veux-tu passer l'examen {level} "
        "maintenant ? Il contient {items} questions et une tâche d'écriture. "
        "Tu peux répondre « pas encore »."
    ),
    finished_line=(
        "C'était le dernier examen : tu as terminé le niveau C2. "
        "À partir de maintenant, le travail porte sur l'entretien et le style."
    ),
    plan_header="Voici notre plan :",
    persona_note=(
        "- If the student is completely stuck, one short English gloss in brackets is "
        "allowed. Never teach in English beyond that."
    ),
)

LANGUAGES: Final[dict[str, Language]] = {language.code: language for language in (ENGLISH, FRENCH)}

_ALIASES: Final[dict[str, str]] = {
    "en": "en",
    "eng": "en",
    "english": "en",
    "anglais": "en",
    "fr": "fr",
    "fra": "fr",
    "fre": "fr",
    "french": "fr",
    "francais": "fr",
    "français": "fr",
}


def normalise_language(value: object) -> str | None:
    """Accept 'fr', 'FR', 'french', 'français' and return a registry code."""
    if not isinstance(value, str):
        return None
    return _ALIASES.get(value.strip().lower().replace("ç", "c"))


def get_language(value: object) -> Language:
    """Resolve a code or alias; unknown or empty means English."""
    return LANGUAGES.get(normalise_language(value) or "en", ENGLISH)


def language_catalogue() -> list[dict[str, str]]:
    return [LANGUAGES[code].describe() for code in ("en", "fr")]


def topics_for(language: Language, level: str) -> list[Topic]:
    """Language-aware counterpart of ``cefr.topics_for``."""
    return language.topics(level)
