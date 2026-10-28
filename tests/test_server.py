"""HTTP API tests. The graph runs on a scripted model, no network involved."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fakes import ScriptedLLM
from fastapi.testclient import TestClient
from test_graph import placement_quiz

from english_teacher.graph import make_checkpointer
from english_teacher.server import create_app


def make_client(llm: ScriptedLLM, events_path: str | None = None) -> TestClient:
    # Never touch the real events.sqlite: every test gets its own temp log.
    path = events_path or str(Path(tempfile.mkdtemp()) / "events.sqlite")
    return TestClient(create_app(llm=llm, checkpointer=make_checkpointer(), events_path=path))


def test_levels_endpoint_lists_the_ladder():
    response = make_client(ScriptedLLM()).get("/api/levels")
    assert response.status_code == 200
    codes = [item["code"] for item in response.json()]
    assert codes == ["A1", "A2", "B1", "B2", "C1", "C2"]


def test_levels_endpoint_localises_labels_for_a_language():
    response = make_client(ScriptedLLM()).get("/api/levels?language=fr")
    assert response.status_code == 200
    labels = {item["code"]: item["label"] for item in response.json()}
    assert labels["A1"] == "Débutant"
    assert labels["B2"] == "Intermédiaire avancé"
    assert labels["C2"] == "Maîtrise"


def test_languages_endpoint_lists_both_teachers():
    body = make_client(ScriptedLLM()).get("/api/languages").json()
    by_code = {item["code"]: item for item in body}
    assert set(by_code) == {"en", "fr"}
    assert by_code["en"]["teacher"] == "Ms. Rivera"
    assert by_code["fr"]["teacher"] == "Mme Laurent"
    assert by_code["fr"]["native_name"] == "Français"
    assert by_code["fr"]["initials"] == "ML"


def test_start_session_returns_the_placement_prompt():
    llm = ScriptedLLM(structured={"PlacementQuiz": [placement_quiz()]})
    client = make_client(llm)

    response = client.post(
        "/api/sessions", json={"name": "Yassine", "level": "b1", "goal": "pass the bac"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "B1"
    assert body["kind"] == "placement"
    assert body["awaiting"] is True
    assert "She ___ to school every day." in body["reply"]
    assert set(body["mastery"]) == {"grammar", "vocabulary", "reading", "writing"}
    assert [line["role"] for line in body["history"]] == ["teacher"]
    assert body["topic"], "the sidebar needs a topic before the first lesson"

    again = client.get(f"/api/sessions/{body['thread_id']}")
    assert again.status_code == 200
    assert again.json()["reply"] == body["reply"]
    assert again.json()["history"] == body["history"]


def test_history_replays_the_transcript_after_a_reload():
    llm = ScriptedLLM(
        texts=["Welcome. Today: present perfect."],
        structured={"PlacementQuiz": [placement_quiz()]},
    )
    client = make_client(llm)
    session = client.post("/api/sessions", json={"level": "B1", "name": "Sara"}).json()

    client.post(f"/api/sessions/{session['thread_id']}/messages", json={"message": "1B 2A 3A"})
    body = client.get(f"/api/sessions/{session['thread_id']}").json()

    assert [line["role"] for line in body["history"]] == ["teacher", "student", "teacher"]
    assert body["history"][1]["text"] == "1B 2A 3A"
    assert body["history"][-1]["text"] == body["reply"]


def test_reply_is_resumed_into_the_teaching_loop():
    llm = ScriptedLLM(
        texts=["Welcome. Today: present perfect."],
        structured={"PlacementQuiz": [placement_quiz()]},
    )
    client = make_client(llm)
    session = client.post("/api/sessions", json={"level": "B1", "name": "Sara"}).json()

    response = client.post(
        f"/api/sessions/{session['thread_id']}/messages", json={"message": "1B 2A 3A"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "teaching"
    assert body["reply"] == "Welcome. Today: present perfect."
    assert body["mastery"]["grammar"] >= 60


def test_french_session_speaks_french_and_uses_the_french_syllabus(tmp_path):
    llm = ScriptedLLM(
        texts=["Bonjour ! Aujourd'hui, nous travaillons le passé composé."],
        structured={"PlacementQuiz": [placement_quiz()]},
    )
    client = make_client(llm, events_path=str(tmp_path / "events.sqlite"))

    session = client.post(
        "/api/sessions",
        json={"name": "Amelie", "level": "A2", "language": "fr"},
    ).json()

    assert session["language"] == "fr"
    assert session["language_name"] == "French"
    assert session["teacher"] == "Mme Laurent"
    assert session["initials"] == "ML"
    assert session["level_label"] == "Élémentaire"
    assert session["reply"].startswith("Bonjour, Amelie ! Je suis Mme Laurent.")
    assert "Avant la première leçon" in session["reply"]
    assert "Réponds comme ceci" in session["reply"]
    assert session["topic"] == "Raconter au passé"

    placement_system = str(llm.structured_calls[0][1][0].content)
    assert "in French" in placement_system

    response = client.post(
        f"/api/sessions/{session['thread_id']}/messages",
        json={"message": "1B 2A 3A"},
    ).json()

    assert response["kind"] == "teaching"
    assert response["reply"].startswith("Bonjour !")
    teaching_system = str(llm.text_calls[-1][0].content)
    assert "Mme Laurent" in teaching_system
    assert "Speak French only" in teaching_system
    assert "Raconter au passé" in teaching_system

    events = client.get("/api/dashboard").json()["events"]
    assert events
    assert all("lang=fr" in event["detail"] for event in events)


def test_unknown_session_is_a_404():
    client = make_client(ScriptedLLM())
    assert client.get("/api/sessions/nope").status_code == 404
    assert client.post("/api/sessions/nope/messages", json={"message": "hello"}).status_code == 404


def test_empty_message_is_rejected_before_reaching_the_graph():
    llm = ScriptedLLM(structured={"PlacementQuiz": [placement_quiz()]})
    client = make_client(llm)
    session = client.post("/api/sessions", json={"level": "B1"}).json()

    response = client.post(
        f"/api/sessions/{session['thread_id']}/messages", json={"message": "   "}
    )
    assert response.status_code == 422


def test_index_serves_the_app_shell():
    client = make_client(ScriptedLLM())
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="languagePicker"' in response.text
    assert "Start where you are." in response.text
    assert "/static/app.js" in response.text


def test_dashboard_records_a_turn_without_touching_the_model(tmp_path, monkeypatch):
    # Alerting reads the environment at request time; keep this test independent
    # from whatever .env the developer has on disk.
    for name in ("ALERT_EMAIL_TO", "ALERT_SMTP_HOST", "MAIL_SERVER", "MAIL_USERNAME"):
        monkeypatch.delenv(name, raising=False)
    llm = ScriptedLLM(structured={"PlacementQuiz": [placement_quiz()]})
    client = make_client(llm, events_path=str(tmp_path / "events.sqlite"))

    session = client.post("/api/sessions", json={"level": "B1", "name": "Nadia"})
    assert session.status_code == 200

    body = client.get("/api/dashboard").json()
    assert body["totals"]["turns"] == 1
    assert body["totals"]["errors"] == 0
    assert body["events"][0]["kind"] == "turn"
    assert body["events"][0]["name"] == "start_session"
    assert body["events"][0]["user_id"] == "Nadia"
    assert "level=B1" in body["events"][0]["detail"]
    assert "phase=" in body["events"][0]["detail"]
    assert body["alerts"]["email_configured"] is False

    filtered = client.get("/api/dashboard?kind=turn").json()
    assert all(event["kind"] == "turn" for event in filtered["events"])
    assert client.get("/api/dashboard?kind=error").json()["events"] == []


def test_dashboard_page_is_served(tmp_path):
    client = make_client(ScriptedLLM(), events_path=str(tmp_path / "events.sqlite"))
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Logs &amp; tokens" in response.text
    assert "/static/dashboard.js" in response.text
