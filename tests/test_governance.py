"""Governance tests: Agent Card, SemVer, kill switch and deployment artefacts."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest
from fakes import ScriptedLLM
from fastapi.testclient import TestClient
from test_graph import placement_quiz

from english_teacher import __version__
from english_teacher.agent_card import AGENT_CARD_PATH, load_agent_card
from english_teacher.governance import KillSwitch, kill_switch_path
from english_teacher.governance import main as governance_main
from english_teacher.graph import make_checkpointer
from english_teacher.server import create_app

ROOT = Path(__file__).resolve().parents[1]
ADMIN = {"X-Admin-Token": "right-token"}


def make_client(
    tmp_path: Path,
    *,
    llm: ScriptedLLM | None = None,
    admin_secret: str = "",
    **kwargs,
) -> TestClient:
    llm = llm or ScriptedLLM(structured={"PlacementQuiz": [placement_quiz()]})
    return TestClient(
        create_app(
            llm=llm,
            checkpointer=make_checkpointer(),
            events_path=str(tmp_path / "events.sqlite"),
            admin_secret=admin_secret,
            **kwargs,
        )
    )


# --------------------------------------------------------------------------- #
# Agent Card and SemVer
# --------------------------------------------------------------------------- #
def test_version_is_semver_and_matches_pyproject_and_agent_card():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == project["project"]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)

    raw = json.loads(AGENT_CARD_PATH.read_text(encoding="utf-8"))
    assert raw["version"] == __version__


def test_agent_card_has_the_governance_sections(tmp_path):
    card = load_agent_card(kill_switch=KillSwitch(tmp_path / "kill-switch.json"))

    assert card["id"]
    assert card["name"]
    assert card["version"] == __version__
    assert card["owners"]["business"]["role"]
    assert card["owners"]["business"]["contact"]
    assert card["owners"]["technical"]["role"]
    assert card["owners"]["technical"]["contact"]
    assert card["responsibilities"]
    assert card["capabilities"]
    assert card["resources"]
    assert card["limits"]["in_scope"]
    assert card["limits"]["out_of_scope"]
    assert card["limits"]["guardrails"]
    assert card["data_handling"]["student_data"]
    assert card["security"]["secrets"]
    assert card["versioning"]["scheme"] == "SemVer"
    assert card["versioning"]["tag_pattern"] == "vMAJOR.MINOR.PATCH"
    assert card["runbook"] == "docs/RUNBOOK.md"
    assert card["changelog"] == "CHANGELOG.md"
    assert card["status"] == "active"
    assert card["kill_switch"]["active"] is False
    assert any("listening" in item.lower() for item in card["limits"]["out_of_scope"])


def test_agent_card_never_carries_a_secret_value(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "SECRET-MARKER-DO-NOT-LEAK")
    card = load_agent_card(kill_switch=KillSwitch(tmp_path / "kill-switch.json"))
    assert "SECRET-MARKER-DO-NOT-LEAK" not in json.dumps(card)
    assert "GOOGLE_API_KEY" in json.dumps(card)  # variable name only


def test_suspended_agent_card_reflects_the_kill_switch(tmp_path):
    switcher = KillSwitch(tmp_path / "kill-switch.json")
    switcher.set(True, reason="policy violation", actor="ops")

    card = load_agent_card(kill_switch=switcher)
    assert card["status"] == "suspended"
    assert card["kill_switch"]["active"] is True
    assert card["kill_switch"]["reason"] == "policy violation"


# --------------------------------------------------------------------------- #
# Kill switch primitive
# --------------------------------------------------------------------------- #
def test_kill_switch_file_lifecycle(tmp_path, monkeypatch):
    monkeypatch.delenv("ENGLISH_TEACHER_KILL_SWITCH", raising=False)
    path = tmp_path / "kill-switch.json"
    switcher = KillSwitch(path)

    assert switcher.status()["active"] is False
    assert switcher.status()["source"] == "none"

    status = switcher.set(True, reason="bad answers", actor="on-call")
    assert status["active"] is True
    assert status["source"] == "file"
    assert status["reason"] == "bad answers"
    assert status["actor"] == "on-call"
    assert status["since"]

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["active"] is True
    assert stored["reason"] == "bad answers"

    status = switcher.set(False, actor="on-call")
    assert status["active"] is False
    assert status["since"] == ""


def test_env_switch_wins_over_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGLISH_TEACHER_KILL_SWITCH", "1")
    monkeypatch.setenv("ENGLISH_TEACHER_KILL_SWITCH_REASON", "maintenance window")
    switcher = KillSwitch(tmp_path / "kill-switch.json")

    status = switcher.status()
    assert status["active"] is True
    assert status["source"] == "env"
    assert status["env_override"] is True
    assert status["reason"] == "maintenance window"

    switcher.set(False)
    assert switcher.status()["active"] is True


def test_kill_switch_path_follows_the_database(tmp_path, monkeypatch):
    monkeypatch.delenv("ENGLISH_TEACHER_KILL_SWITCH_FILE", raising=False)
    assert kill_switch_path(str(tmp_path / "sessions.sqlite")) == tmp_path / "kill-switch.json"

    override = tmp_path / "custom.json"
    monkeypatch.setenv("ENGLISH_TEACHER_KILL_SWITCH_FILE", str(override))
    assert kill_switch_path(str(tmp_path / "sessions.sqlite")) == override


def test_governance_cli_toggles_the_file(tmp_path, monkeypatch, capsys):
    path = tmp_path / "kill-switch.json"
    monkeypatch.setenv("ENGLISH_TEACHER_KILL_SWITCH_FILE", str(path))
    monkeypatch.delenv("ENGLISH_TEACHER_KILL_SWITCH", raising=False)

    assert governance_main(["status"]) == 0
    assert json.loads(capsys.readouterr().out)["active"] is False

    assert governance_main(["on", "--reason", "drill", "--actor", "ops"]) == 0
    assert json.loads(capsys.readouterr().out)["active"] is True
    assert KillSwitch(path).status()["reason"] == "drill"

    assert governance_main(["off", "--actor", "ops"]) == 0
    assert json.loads(capsys.readouterr().out)["active"] is False


# --------------------------------------------------------------------------- #
# HTTP surface and enforcement
# --------------------------------------------------------------------------- #
def test_admin_api_is_hidden_when_no_token_is_configured(tmp_path):
    client = make_client(tmp_path, admin_secret="")
    response = client.post(
        "/api/admin/kill-switch",
        json={"active": True, "reason": "drill"},
        headers={"X-Admin-Token": "anything"},
    )
    assert response.status_code == 404
    assert "disabled" in response.json()["detail"].lower()


def test_admin_api_rejects_a_wrong_token(tmp_path):
    client = make_client(tmp_path, admin_secret="right-token")
    response = client.post(
        "/api/admin/kill-switch",
        json={"active": True, "reason": "drill"},
        headers={"X-Admin-Token": "wrong-token"},
    )
    assert response.status_code == 403
    assert client.get("/api/governance").json()["kill_switch"]["active"] is False


def test_kill_switch_blocks_writes_but_keeps_reads_available(tmp_path):
    llm = ScriptedLLM(
        structured={"PlacementQuiz": [placement_quiz(), placement_quiz()]},
    )
    client = make_client(tmp_path, llm=llm, admin_secret="right-token")
    session = client.post("/api/sessions", json={"name": "Sara", "level": "B1"}).json()

    activated = client.post(
        "/api/admin/kill-switch",
        json={"active": True, "reason": "wrong correction", "actor": "on-call"},
        headers=ADMIN,
    )
    assert activated.status_code == 200
    assert activated.json()["active"] is True

    assert client.get(f"/api/sessions/{session['thread_id']}").status_code == 200
    assert client.get("/api/governance").json()["status"] == "suspended"
    assert client.get("/api/agent-card").json()["status"] == "suspended"

    blocked_start = client.post("/api/sessions", json={"name": "Nadia", "level": "B1"})
    assert blocked_start.status_code == 503
    assert "kill switch" in blocked_start.json()["detail"].lower()

    blocked_turn = client.post(
        f"/api/sessions/{session['thread_id']}/messages",
        json={"message": "1B 2A 3A"},
    )
    assert blocked_turn.status_code == 503

    deactivated = client.post(
        "/api/admin/kill-switch",
        json={"active": False, "reason": "fixed", "actor": "on-call"},
        headers=ADMIN,
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False

    resumed = client.post("/api/sessions", json={"name": "Nadia", "level": "B1"})
    assert resumed.status_code == 200
    assert resumed.json()["kind"] == "placement"


def test_governance_events_reach_the_dashboard(tmp_path):
    client = make_client(tmp_path, admin_secret="right-token")
    client.post(
        "/api/admin/kill-switch",
        json={"active": True, "reason": "drill", "actor": "ops"},
        headers=ADMIN,
    )

    events = client.get("/api/dashboard?kind=governance").json()["events"]
    assert events
    assert events[0]["name"] == "kill_switch_on"
    assert "actor=ops" in events[0]["detail"]
    assert "reason=drill" in events[0]["detail"]


def test_health_exposes_version_and_switch_state(tmp_path):
    client = make_client(tmp_path, admin_secret="right-token")
    body = client.get("/api/health").json()
    assert body["version"] == __version__
    assert body["kill_switch"] == "off"

    client.post(
        "/api/admin/kill-switch",
        json={"active": True, "reason": "drill"},
        headers=ADMIN,
    )
    assert client.get("/api/health").json()["kill_switch"] == "active"


def test_agent_card_is_served_on_both_endpoints(tmp_path):
    client = make_client(tmp_path)
    for path in ("/api/agent-card", "/.well-known/agent-card.json"):
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "el-abid/english-teacher-agent"
        assert body["version"] == __version__
        assert body["owners"]["technical"]["role"]


def test_security_headers_are_set_on_every_response(tmp_path):
    client = make_client(tmp_path)
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_governance_page_is_served(tmp_path):
    client = make_client(tmp_path)
    response = client.get("/governance")
    assert response.status_code == 200
    assert 'id="agentCard"' in response.text
    assert "/static/governance.js" in response.text


# --------------------------------------------------------------------------- #
# Deployment artefacts
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name",
    [
        "Dockerfile",
        ".dockerignore",
        "docker-compose.yml",
        "CHANGELOG.md",
        "docs/GOVERNANCE.md",
        "docs/RUNBOOK.md",
        "docs/DEPLOYMENT.md",
    ],
)
def test_deployment_and_governance_documents_exist(name):
    assert (ROOT / name).is_file(), f"missing {name}"


def test_container_runs_as_non_root_and_mounts_persistent_data():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "USER " in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "/data" in dockerfile
    assert "ENGLISH_TEACHER_KILL_SWITCH_FILE" in compose
    assert "tutor-data" in compose
