"""End-to-end graph tests with a scripted model.

Covers the promise of the product: placement, teaching, readiness offer, exam,
grading, promotion. Also covers the two guard rails that matter: never offer the
exam on numbers alone, and never let the model promote anyone by itself.
"""

from __future__ import annotations

from fakes import ScriptedLLM
from langgraph.types import Command

from english_teacher.cefr import SKILLS
from english_teacher.graph import compile_graph, initial_state
from english_teacher.nodes import check_readiness
from english_teacher.policy import evaluate_readiness, new_mastery
from english_teacher.schemas import (
    Assessment,
    Exam,
    ExamDecisionAnswer,
    ExamItem,
    PlacementQuestion,
    PlacementQuiz,
    ReadinessOpinion,
    RemediationPlan,
    WritingGrade,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def placement_quiz() -> PlacementQuiz:
    return PlacementQuiz(
        intro="Three quick questions before we start.",
        questions=[
            PlacementQuestion(
                id=1,
                skill="grammar",
                prompt="She ___ to school every day.",
                choices={"A": "go", "B": "goes", "C": "going", "D": "gone"},
                answer="B",
            ),
            PlacementQuestion(
                id=2,
                skill="vocabulary",
                prompt="A place where you borrow books.",
                choices={"A": "library", "B": "bakery", "C": "pharmacy", "D": "garage"},
                answer="A",
            ),
            PlacementQuestion(
                id=3,
                skill="reading",
                prompt="Tom woke up late, so he ___ breakfast.",
                choices={"A": "skipped", "B": "cooked", "C": "enjoyed", "D": "bought"},
                answer="A",
            ),
        ],
    )


def strong_assessment() -> Assessment:
    return Assessment(
        feedback="Good control of the target structure. Watch the third person -s.",
        scores={skill: 0.95 for skill in SKILLS},
        topic_progress=1.0,
        topic_complete=True,
        points_to_review=["third person -s"],
    )


def b1_exam() -> Exam:
    return Exam(
        title="B1 Final",
        instructions="Answer all eight questions.",
        items=[
            ExamItem(
                id=1,
                skill="grammar",
                prompt="I ___ here since 2020.",
                choices={"A": "live", "B": "lived", "C": "have lived", "D": "living"},
                answer="C",
            ),
            ExamItem(
                id=2,
                skill="vocabulary",
                prompt="Choose the synonym of 'huge'.",
                choices={"A": "tiny", "B": "enormous", "C": "narrow", "D": "quiet"},
                answer="B",
            ),
            ExamItem(
                id=3,
                skill="reading",
                prompt="Maya missed the bus, so she...",
                choices={
                    "A": "arrived early",
                    "B": "walked to school",
                    "C": "stayed home",
                    "D": "took a taxi",
                },
                answer="B",
            ),
            ExamItem(
                id=4,
                skill="grammar",
                prompt="If I ___ more time, I would travel around Asia.",
                choices={"A": "have", "B": "had had", "C": "had", "D": "will have"},
                answer="C",
            ),
        ],
        writing_prompt="Write 120-180 words about a trip that went wrong.",
        writing_criteria=["task response", "past tenses", "linking words"],
    )


def scripted_llm() -> ScriptedLLM:
    return ScriptedLLM(
        texts=[
            "Welcome! Today: present perfect. When do we use 'for' and 'since'?",  # after placement
            "Nice. Now try: I have lived here ___ five years.",  # turn 1
            "Good. Make a sentence with 'since'.",  # turn 2
            "Your grammar is solid now. Want to try the B1 exam?",  # exam offer
            "You scored 96%. Strong grammar, clear writing.",  # results
            "Welcome to B2. Today we start with hypothetical situations.",  # next level
        ],
        structured={
            "PlacementQuiz": [placement_quiz()],
            "Assessment": [
                strong_assessment(),
                strong_assessment(),
                strong_assessment(),
            ],
            "ReadinessOpinion": [
                ReadinessOpinion(ready=True, rationale="Consistent strong answers.", weak_skills=[])
            ],
            "ExamDecisionAnswer": [ExamDecisionAnswer(accepted=True, note="Student said yes")],
            "Exam": [b1_exam()],
            "WritingGrade": [
                WritingGrade(
                    score=0.9,
                    feedback="Clear narrative, good past tenses.",
                    strengths=["linking words"],
                    weaknesses=[],
                )
            ],
        },
    )


def _prompt(state: dict) -> str:
    interrupts = state["__interrupt__"]
    value = interrupts[0].value
    assert isinstance(value, dict)
    return value["prompt"]


def _kind(state: dict) -> str:
    return state["__interrupt__"][0].value["kind"]


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_full_journey_from_placement_to_promotion():
    llm = scripted_llm()
    graph = compile_graph()
    config = {"configurable": {"thread_id": "t1", "llm": llm}}

    state = graph.invoke(initial_state("Yassine", "B1", "pass my bac"), config)

    # 1. placement quiz is shown, level honoured
    assert state["level"] == "B1"
    assert _kind(state) == "placement"
    assert "1. She ___ to school every day." in _prompt(state)
    assert "goal is pass my bac" in _prompt(state)

    # 2. placement answers are graded, first lesson starts
    state = graph.invoke(Command(resume="1B 2A 3A"), config)
    assert state["placement_summary"] == "3/3 correct on the placement check."
    assert _kind(state) == "teaching"
    assert state["mastery"]["grammar"]["evidence"] >= 1

    # 3. three strong answers complete three topics
    for answer in [
        "For five years.",
        "I have lived here since 2020.",
        "I have studied English since 2019.",
    ]:
        state = graph.invoke(Command(resume=answer), config)

    # 4. numeric gate + tutor opinion => exam is offered, not imposed
    assert _kind(state) == "exam_offer"
    assert "exam" in _prompt(state).lower()
    assert state["lessons_completed"] == 3

    # 5. accepting produces the exam
    state = graph.invoke(Command(resume="Yes, let's do it."), config)
    assert _kind(state) == "exam"
    assert "FINAL EXAM - B1 Final" in _prompt(state)
    assert "WRITING TASK" in _prompt(state)

    # 6. submission is graded and the student is promoted
    state = graph.invoke(
        Command(
            resume="ANSWERS: 1C 2B 3B 4C\nWRITING: Last summer my family travelled to the coast."
        ),
        config,
    )
    assert state["exam_result"].passed is True
    assert state["exam_result"].score > 0.9
    assert state["level"] == "B2"
    assert state["level_history"] == ["B1", "B2"]
    assert state["lessons_completed"] == 0, "progress resets at the new level"
    assert _kind(state) == "teaching"
    assert "B2" in _prompt(state)


def test_failed_exam_leads_to_remediation_not_promotion():
    llm = scripted_llm()
    llm.texts.append("Let's rebuild the third conditional together.")
    llm.structured["WritingGrade"] = [
        WritingGrade(
            score=0.3,
            feedback="Short and off-topic.",
            strengths=[],
            weaknesses=["no paragraph structure"],
        )
    ]
    llm.structured["RemediationPlan"] = [
        RemediationPlan(
            focus_skills=["writing"],
            activities=["Rewrite one paragraph", "Three linking-word drills"],
            message="You scored 52%, so we work on writing this week.",
        )
    ]

    graph = compile_graph()
    config = {"configurable": {"thread_id": "t2", "llm": llm}}
    state = graph.invoke(initial_state("Sara", "B1"), config)
    state = graph.invoke(Command(resume="1B 2A 3A"), config)
    for answer in ["For five years.", "Since 2020.", "Since 2019."]:
        state = graph.invoke(Command(resume=answer), config)
    state = graph.invoke(Command(resume="yes"), config)
    state = graph.invoke(
        Command(resume="ANSWERS: 1A 2A 3A 4A\nWRITING: I dont like trip."),
        config,
    )

    assert state["exam_result"].passed is False
    assert state["level"] == "B1"
    assert state["review_mode"] is True
    assert state["failed_points"], "failed skills become review points"
    assert "writing" in {point.skill for point in state["failed_points"]}
    assert _kind(state) == "teaching"


def test_numeric_gate_alone_cannot_trigger_an_offer():
    llm = ScriptedLLM(structured={"ReadinessOpinion": []})  # would explode if called
    state = {
        "level": "B1",
        "mastery": new_mastery(0.3),
        "lessons_completed": 0,
        "topic_complete": True,
        "plan": [],
        "turns": 5,
    }

    result = check_readiness(state, {"configurable": {"llm": llm}})

    assert result["next_action"] != "offer_exam"
    assert result["readiness_reasons"]


def test_tutor_opinion_can_delay_a_promotion():
    mastery = {skill: {"score": 0.95, "evidence": 4} for skill in SKILLS}
    assert evaluate_readiness(mastery, 5).ready is True

    llm = ScriptedLLM(
        structured={
            "ReadinessOpinion": [
                ReadinessOpinion(
                    ready=False,
                    rationale="Only drill answers so far.",
                    weak_skills=["writing"],
                )
            ]
        }
    )
    state = {
        "level": "B1",
        "mastery": mastery,
        "lessons_completed": 5,
        "topic_complete": False,
        "plan": [],
        "turns": 10,
    }

    result = check_readiness(state, {"configurable": {"llm": llm}})

    assert result["next_action"] == "teach"
    assert "drill answers" in result["readiness_note"]
