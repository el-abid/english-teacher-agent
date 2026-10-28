"""CEFR reference data: levels, skill axes and the syllabus the tutor teaches from.

The syllabus is deliberately static. Language teaching content is well known, so
keeping it in code makes the lesson plan reproducible, cheap (no LLM call) and
easy for a teacher to review. The LLM personalises *how* a topic is taught, not
*what* the level contains.
"""

from __future__ import annotations

from typing import Final, TypedDict


class Topic(TypedDict):
    """One teachable unit inside a level."""

    id: str
    title: str
    can_do: str  # CEFR "can do" descriptor, shown to the student
    grammar: list[str]
    vocabulary: str


LEVELS: Final[tuple[str, ...]] = ("A1", "A2", "B1", "B2", "C1", "C2")

# Text-first tutor: speaking and listening are out of scope for now, so the
# mastery model only tracks what the product can actually observe.
SKILLS: Final[tuple[str, ...]] = (
    "grammar",
    "vocabulary",
    "reading",
    "writing",
)

LEVEL_LABELS: Final[dict[str, str]] = {
    "A1": "Beginner",
    "A2": "Elementary",
    "B1": "Intermediate",
    "B2": "Upper-intermediate",
    "C1": "Advanced",
    "C2": "Proficient",
}

SYLLABUS: Final[dict[str, list[Topic]]] = {
    "A1": [
        {
            "id": "A1-1",
            "title": "Introducing yourself",
            "can_do": "I can greet someone and give my name, age and nationality.",
            "grammar": ["verb 'to be'", "subject pronouns", "possessive adjectives"],
            "vocabulary": "countries, nationalities, numbers 1-20, classroom objects",
        },
        {
            "id": "A1-2",
            "title": "My family and friends",
            "can_do": "I can describe my family and say who people are.",
            "grammar": ["have got", "possessive 's", "plural nouns"],
            "vocabulary": "family members, physical description, colours",
        },
        {
            "id": "A1-3",
            "title": "Daily routine and time",
            "can_do": "I can talk about my day and tell the time.",
            "grammar": [
                "present simple",
                "adverbs of frequency",
                "prepositions of time",
            ],
            "vocabulary": "daily activities, days, months, clock times",
        },
        {
            "id": "A1-4",
            "title": "Food, shops and prices",
            "can_do": "I can order food and ask how much something costs.",
            "grammar": ["countable / uncountable", "some / any", "this / that / these"],
            "vocabulary": "food, drinks, shops, prices",
        },
        {
            "id": "A1-5",
            "title": "Places in town",
            "can_do": "I can ask for and give simple directions.",
            "grammar": ["there is / there are", "imperatives", "prepositions of place"],
            "vocabulary": "buildings, transport, directions",
        },
    ],
    "A2": [
        {
            "id": "A2-1",
            "title": "Telling stories in the past",
            "can_do": "I can describe a past weekend or holiday.",
            "grammar": ["past simple regular / irregular", "past time expressions"],
            "vocabulary": "holidays, feelings, travel verbs",
        },
        {
            "id": "A2-2",
            "title": "Plans and predictions",
            "can_do": "I can talk about future plans and make simple predictions.",
            "grammar": ["going to", "will", "present continuous for future"],
            "vocabulary": "weekend plans, weather, appointments",
        },
        {
            "id": "A2-3",
            "title": "Comparing things",
            "can_do": "I can compare people, places and products.",
            "grammar": ["comparatives", "superlatives", "as ... as"],
            "vocabulary": "adjectives of size, quality, price",
        },
        {
            "id": "A2-4",
            "title": "Health and advice",
            "can_do": "I can describe a health problem and give advice.",
            "grammar": ["should / shouldn't", "have to", "imperatives"],
            "vocabulary": "body, illness, sports, healthy habits",
        },
        {
            "id": "A2-5",
            "title": "Past experiences",
            "can_do": "I can ask and answer about experiences I have had.",
            "grammar": [
                "present perfect with ever / never",
                "past simple vs present perfect",
            ],
            "vocabulary": "experiences, hobbies, achievements",
        },
    ],
    "B1": [
        {
            "id": "B1-1",
            "title": "Life experience and present perfect",
            "can_do": "I can talk about life experiences and recent events in detail.",
            "grammar": ["present perfect", "for / since", "just / already / yet"],
            "vocabulary": "life events, work, study, personal milestones",
        },
        {
            "id": "B1-2",
            "title": "Real conditions and consequences",
            "can_do": "I can discuss what will happen if something occurs.",
            "grammar": ["first conditional", "unless", "imperatives in warnings"],
            "vocabulary": "environment, school rules, consequences",
        },
        {
            "id": "B1-3",
            "title": "Giving opinions",
            "can_do": "I can give my opinion, agree and disagree politely.",
            "grammar": [
                "opinion verbs + gerund",
                "linking words",
                "modals of obligation",
            ],
            "vocabulary": "school life, technology, free time",
        },
        {
            "id": "B1-4",
            "title": "Describing processes",
            "can_do": "I can explain how something is made or done.",
            "grammar": ["passive voice (present / past)", "sequencing words"],
            "vocabulary": "manufacturing, recipes, instructions",
        },
        {
            "id": "B1-5",
            "title": "Narrating and reacting",
            "can_do": "I can tell a story and react to other people's stories.",
            "grammar": ["past continuous vs past simple", "used to", "so / such"],
            "vocabulary": "anecdotes, emotions, surprises",
        },
    ],
    "B2": [
        {
            "id": "B2-1",
            "title": "Hypothetical situations",
            "can_do": "I can discuss imaginary situations and their consequences.",
            "grammar": ["second conditional", "wish / if only", "would rather"],
            "vocabulary": "ambitions, regrets, social issues",
        },
        {
            "id": "B2-2",
            "title": "Reporting what people said",
            "can_do": "I can report a conversation or a news story accurately.",
            "grammar": ["reported speech", "reporting verbs", "tense backshift"],
            "vocabulary": "news, interviews, announcements",
        },
        {
            "id": "B2-3",
            "title": "Debating a topic",
            "can_do": "I can argue a position and respond to counter-arguments.",
            "grammar": ["third conditional", "concession clauses", "hedging"],
            "vocabulary": "environment, media, education policy",
        },
        {
            "id": "B2-4",
            "title": "Describing and defining",
            "can_do": "I can define and describe complex ideas precisely.",
            "grammar": ["relative clauses (defining / non-defining)", "participles"],
            "vocabulary": "science, culture, abstract nouns",
        },
        {
            "id": "B2-5",
            "title": "Writing an argumentative paragraph",
            "can_do": "I can write a structured paragraph defending a claim.",
            "grammar": ["cohesion devices", "sentence variety", "formal linkers"],
            "vocabulary": "academic verbs, evaluation adjectives",
        },
    ],
    "C1": [
        {
            "id": "C1-1",
            "title": "Emphasis and inversion",
            "can_do": "I can emphasise information with advanced sentence structures.",
            "grammar": ["negative inversion", "cleft sentences", "fronting"],
            "vocabulary": "rhetoric, journalism, public speaking",
        },
        {
            "id": "C1-2",
            "title": "Speculating about the past",
            "can_do": "I can speculate and deduce about past events.",
            "grammar": ["modal perfects", "mixed conditionals", "deduction verbs"],
            "vocabulary": "mysteries, history, investigations",
        },
        {
            "id": "C1-3",
            "title": "Nominalisation and register",
            "can_do": "I can shift between spoken and academic register.",
            "grammar": [
                "nominalisation",
                "impersonal constructions",
                "complex noun phrases",
            ],
            "vocabulary": "academic writing, reports, abstracts",
        },
        {
            "id": "C1-4",
            "title": "Nuance in argument",
            "can_do": "I can qualify a claim and anticipate objections.",
            "grammar": ["hedging", "concessive structures", "discourse markers"],
            "vocabulary": "ethics, technology, policy debate",
        },
        {
            "id": "C1-5",
            "title": "Cohesive extended writing",
            "can_do": "I can write a coherent multi-paragraph essay.",
            "grammar": ["paragraph architecture", "reference chains", "ellipsis"],
            "vocabulary": "topic sentences, citation language",
        },
    ],
    "C2": [
        {
            "id": "C2-1",
            "title": "Connotation and precision",
            "can_do": "I can choose words for their exact shade of meaning.",
            "grammar": ["collocation", "register shifts", "euphemism"],
            "vocabulary": "synonym nuance, idiom, connotation",
        },
        {
            "id": "C2-2",
            "title": "Idiomatic fluency",
            "can_do": "I can use idioms and fixed expressions naturally.",
            "grammar": ["idiomatic verb patterns", "binomials", "metaphor"],
            "vocabulary": "idioms, proverbs, cultural references",
        },
        {
            "id": "C2-3",
            "title": "Critical reading",
            "can_do": "I can identify bias, assumption and rhetorical strategy in a text.",
            "grammar": [
                "stance adverbials",
                "complex embedding",
                "rhetorical questions",
            ],
            "vocabulary": "argument analysis, media literacy",
        },
        {
            "id": "C2-4",
            "title": "Academic discourse",
            "can_do": "I can sustain a formal academic argument with citations.",
            "grammar": ["nominal style", "passive reporting", "advanced cohesion"],
            "vocabulary": "research writing, evaluation, synthesis",
        },
        {
            "id": "C2-5",
            "title": "Stylistic control",
            "can_do": "I can adapt tone and style for different audiences.",
            "grammar": [
                "ellipsis and substitution",
                "marked word order",
                "parallelism",
            ],
            "vocabulary": "style, voice, audience awareness",
        },
    ],
}


def topics_for(level: str) -> list[Topic]:
    """Return a copy of the syllabus for ``level`` (raises on unknown level)."""
    return [dict(topic) for topic in SYLLABUS[level]]  # type: ignore[misc]


def level_index(level: str) -> int:
    return LEVELS.index(level)


def next_level(level: str) -> str | None:
    """Level after ``level``, or ``None`` when the student finished C2."""
    index = level_index(level)
    if index + 1 >= len(LEVELS):
        return None
    return LEVELS[index + 1]


def normalise_level(value: object) -> str | None:
    """Accept 'b1', ' B1 ', 'B1 (intermediate)' and return 'B1'."""
    if not isinstance(value, str):
        return None
    compact = value.strip().upper()
    for level in LEVELS:
        if compact == level:
            return level
    return None
