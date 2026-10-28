"""Email alerts when the tutor burns tokens or fails.

Two naming schemes are accepted. The app's own ``ALERT_*`` names win when both
are set; otherwise the Flask-Mail style ``MAIL_*`` names are used, so an existing
``.env`` works unchanged:

    ALERT_EMAIL_TO / MAIL_DEFAULT_SENDER or MAIL_USERNAME
    ALERT_SMTP_HOST / MAIL_SERVER
    ALERT_SMTP_PORT / MAIL_PORT
    ALERT_SMTP_USER / MAIL_USERNAME
    ALERT_SMTP_PASSWORD / MAIL_PASSWORD
    ALERT_EMAIL_FROM / MAIL_DEFAULT_SENDER or MAIL_USERNAME
    ALERT_SMTP_TLS / MAIL_USE_TLS       ("True" -> starttls, "False" -> plain)

``MAIL_PASSWORD`` is often kept out of ``.env`` and exported by the OS instead.
That works: ``load_env_file`` never overwrites a variable that already exists.

    ENGLISH_TEACHER_DAILY_TOKEN_BUDGET=200000   # 0 disables the budget alert

Without a recipient and a host nothing is sent and no network call is made.
Sending happens on a daemon thread so a slow SMTP server can never delay a
student turn, and no failure there is ever raised to the caller.
"""

from __future__ import annotations

import os
import smtplib
import threading
from email.message import EmailMessage
from typing import Any

from .observability import EventStore

ERROR_COOLDOWN_MINUTES = 15


def _first(*names: str, default: str = "") -> str:
    """First non-empty value among the given environment names."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def recipient() -> str:
    return _first("ALERT_EMAIL_TO", "MAIL_DEFAULT_SENDER", "MAIL_USERNAME")


def smtp_host() -> str:
    return _first("ALERT_SMTP_HOST", "MAIL_SERVER")


def smtp_port() -> int:
    raw = _first("ALERT_SMTP_PORT", "MAIL_PORT", default="587")
    try:
        return int(raw)
    except ValueError:
        return 587


def smtp_user() -> str:
    return _first("ALERT_SMTP_USER", "MAIL_USERNAME")


def smtp_password() -> str:
    return _first("ALERT_SMTP_PASSWORD", "MAIL_PASSWORD")


def sender() -> str:
    return _first("ALERT_EMAIL_FROM", "MAIL_DEFAULT_SENDER", "MAIL_USERNAME", default="alerts@localhost")


def smtp_tls() -> str:
    """starttls, ssl or none. Explicit ALERT_SMTP_TLS wins over MAIL_USE_TLS."""
    explicit = os.getenv("ALERT_SMTP_TLS", "").strip().lower()
    if explicit in {"starttls", "ssl", "none"}:
        return explicit

    use_tls = os.getenv("MAIL_USE_TLS", "").strip().lower()
    if use_tls in {"0", "false", "no", "off"}:
        return "none"
    if os.getenv("MAIL_USE_SSL", "").strip().lower() in {"1", "true", "yes", "on"}:
        return "ssl"
    return "starttls"


def email_configured() -> bool:
    return bool(recipient() and smtp_host())


def daily_token_budget() -> int:
    try:
        return max(0, int(os.getenv("ENGLISH_TEACHER_DAILY_TOKEN_BUDGET", "0")))
    except ValueError:
        return 0


def _build_message(subject: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender()
    message["To"] = recipient()
    message.set_content(body)
    return message


def send_email(subject: str, body: str) -> bool:
    """Send one mail. Returns False when unconfigured or on any failure."""
    if not email_configured():
        return False

    host = smtp_host()
    port = smtp_port()
    user = smtp_user()
    password = smtp_password()
    mode = smtp_tls()
    message = _build_message(subject, body)

    try:
        if mode == "ssl":
            with smtplib.SMTP_SSL(host, port, timeout=10) as client:
                if user:
                    client.login(user, password)
                client.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as client:
                if mode != "none":
                    client.starttls()
                if user:
                    client.login(user, password)
                client.send_message(message)
    except Exception:  # noqa: BLE001 - alerting must never break the app
        return False
    return True


def _send_async(subject: str, body: str) -> None:
    threading.Thread(target=send_email, args=(subject, body), daemon=True).start()


def _send(store: EventStore, key: str, subject: str, body: str, *, background: bool) -> bool:
    store.mark_alert(key)
    store.record("alert", subject[:60], status="ok", detail=body[:400])
    if background:
        _send_async(subject, body)
        return True
    return send_email(subject, body)


def check_token_budget(store: EventStore, *, background: bool = True) -> bool:
    """Alert once per day when the token budget is crossed."""
    budget = daily_token_budget()
    if budget <= 0:
        return False

    used = store.tokens_today()
    if used < budget:
        return False

    day = store.totals()["since"][:10]
    key = f"budget:{day}"
    if store.last_alert(key) is not None:
        return False
    if not email_configured():
        store.record(
            "alert",
            "token budget reached (email not configured)",
            status="warn",
            detail=f"{used} tokens used, budget {budget}",
        )
        return False

    percent = round(used / budget * 100)
    return _send(
        store,
        key,
        f"[English tutor] daily token budget {percent}% used",
        f"The tutor used {used:,} of the {budget:,} daily token budget "
        f"({percent}%). Today's estimated cost: ${store.totals()['cost_usd']:.4f}.\n\n"
        f"Rows: http://127.0.0.1:8000/dashboard\n",
        background=background,
    )


def alert_error(
    store: EventStore,
    name: str,
    detail: str,
    *,
    background: bool = True,
) -> bool:
    """Alert on a failed turn, at most once per 15 minutes per failure point."""
    key = f"error:{name}"
    if not store.alert_cooldown_over(key, ERROR_COOLDOWN_MINUTES):
        return False
    if not email_configured():
        return False
    return _send(
        store,
        key,
        f"[English tutor] failure in {name}",
        f"{name} failed.\n\n{detail[:1500]}\n\nDashboard: http://127.0.0.1:8000/dashboard\n",
        background=background,
    )


def status(store: EventStore) -> dict[str, Any]:
    """What the dashboard shows about alerting."""
    budget = daily_token_budget()
    errors_today = store.totals()["errors"]
    return {
        "email_configured": email_configured(),
        "recipient": recipient(),
        "daily_token_budget": budget,
        "tokens_today": store.tokens_today(),
        "errors_today": errors_today,
    }
