"""Email alerts: configured only when asked, deduplicated, never fatal."""

from __future__ import annotations

import pytest

from english_teacher import alerts
from english_teacher.observability import EventStore


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "ALERT_EMAIL_TO",
        "ALERT_SMTP_HOST",
        "ALERT_SMTP_PORT",
        "ALERT_SMTP_USER",
        "ALERT_SMTP_PASSWORD",
        "ALERT_EMAIL_FROM",
        "ALERT_SMTP_TLS",
        "MAIL_SERVER",
        "MAIL_PORT",
        "MAIL_USE_TLS",
        "MAIL_USE_SSL",
        "MAIL_USERNAME",
        "MAIL_PASSWORD",
        "MAIL_DEFAULT_SENDER",
        "ENGLISH_TEACHER_DAILY_TOKEN_BUDGET",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def store(tmp_path):
    return EventStore(tmp_path / "events.sqlite")


def configure_email(monkeypatch, to="teacher@example.com"):
    monkeypatch.setenv("ALERT_EMAIL_TO", to)
    monkeypatch.setenv("ALERT_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("ALERT_SMTP_USER", "bot@example.com")
    monkeypatch.setenv("ALERT_SMTP_PASSWORD", "secret")


def configure_mail(monkeypatch):
    """The Flask-Mail names, password coming from the OS environment."""
    monkeypatch.setenv("MAIL_SERVER", "smtp.gmail.com")
    monkeypatch.setenv("MAIL_PORT", "587")
    monkeypatch.setenv("MAIL_USE_TLS", "True")
    monkeypatch.setenv("MAIL_USERNAME", "mar.elabid@gmail.com")
    monkeypatch.setenv("MAIL_PASSWORD", "app-password")
    monkeypatch.setenv("MAIL_DEFAULT_SENDER", "mar.elabid@gmail.com")


def test_disabled_without_the_environment(store):
    assert alerts.email_configured() is False
    assert alerts.send_email("subject", "body") is False
    assert alerts.check_token_budget(store, background=False) is False


def test_mail_star_names_are_enough(monkeypatch):
    configure_mail(monkeypatch)

    assert alerts.email_configured() is True
    assert alerts.recipient() == "mar.elabid@gmail.com"
    assert alerts.smtp_host() == "smtp.gmail.com"
    assert alerts.smtp_port() == 587
    assert alerts.smtp_user() == "mar.elabid@gmail.com"
    assert alerts.smtp_password() == "app-password"
    assert alerts.sender() == "mar.elabid@gmail.com"
    assert alerts.smtp_tls() == "starttls"


def test_alert_names_win_over_mail_names(monkeypatch):
    configure_mail(monkeypatch)
    monkeypatch.setenv("ALERT_EMAIL_TO", "teacher@example.com")
    monkeypatch.setenv("ALERT_SMTP_TLS", "ssl")

    assert alerts.recipient() == "teacher@example.com"
    assert alerts.smtp_tls() == "ssl"


def test_mail_use_tls_false_means_plain_smtp(monkeypatch):
    configure_mail(monkeypatch)
    monkeypatch.setenv("MAIL_USE_TLS", "False")

    assert alerts.smtp_tls() == "none"


def test_missing_password_still_counts_as_configured(monkeypatch):
    """A relay without auth is valid; login is skipped when the user is empty."""
    monkeypatch.setenv("MAIL_SERVER", "localhost")
    monkeypatch.setenv("MAIL_DEFAULT_SENDER", "tutor@example.com")

    assert alerts.email_configured() is True
    assert alerts.smtp_user() == ""
    assert alerts.smtp_password() == ""


def test_budget_alerts_once_per_day(store, monkeypatch):
    configure_email(monkeypatch)
    monkeypatch.setenv("ENGLISH_TEACHER_DAILY_TOKEN_BUDGET", "100")
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        alerts, "send_email", lambda subject, body: sent.append((subject, body)) or True
    )
    store.record("llm", "chat", input_tokens=80, output_tokens=40)

    assert alerts.check_token_budget(store, background=False) is True
    assert "120%" in sent[0][0]
    assert "120 of the 100" in sent[0][1]
    assert alerts.check_token_budget(store, background=False) is False
    assert store.recent(kind="alert"), "the alert is also logged locally"


def test_budget_under_the_limit_stays_quiet(store, monkeypatch):
    configure_email(monkeypatch)
    monkeypatch.setenv("ENGLISH_TEACHER_DAILY_TOKEN_BUDGET", "10000")
    sent: list[str] = []
    monkeypatch.setattr(alerts, "send_email", lambda subject, body: sent.append(subject) or True)
    store.record("llm", "chat", input_tokens=10, output_tokens=10)

    assert alerts.check_token_budget(store, background=False) is False
    assert sent == []


def test_error_alert_respects_the_cooldown(store, monkeypatch):
    configure_email(monkeypatch)
    sent: list[str] = []
    monkeypatch.setattr(alerts, "send_email", lambda subject, body: sent.append(subject) or True)

    assert alerts.alert_error(store, "message", "RuntimeError: boom", background=False) is True
    assert alerts.alert_error(store, "message", "RuntimeError: boom", background=False) is False
    assert alerts.alert_error(store, "start_session", "boom", background=False) is True
    assert len(sent) == 2


def test_status_reports_what_the_dashboard_needs(store, monkeypatch):
    configure_email(monkeypatch)
    monkeypatch.setenv("ENGLISH_TEACHER_DAILY_TOKEN_BUDGET", "5000")
    store.record("llm", "chat", input_tokens=10, output_tokens=5)

    status = alerts.status(store)
    assert status["email_configured"] is True
    assert status["recipient"] == "teacher@example.com"
    assert status["daily_token_budget"] == 5000
    assert status["tokens_today"] == 15
