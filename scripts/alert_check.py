"""Check the email alert setup, optionally send a test mail.

    uv run python scripts/alert_check.py
    uv run python scripts/alert_check.py --send
"""

from __future__ import annotations

import argparse
import os

from english_teacher import alerts
from english_teacher.config import load_env_file
from english_teacher.observability import EventStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Email alert check")
    parser.add_argument("--send", action="store_true", help="send a real test email")
    parser.add_argument(
        "--db", default=os.getenv("ENGLISH_TEACHER_EVENTS_DB") or "events.sqlite"
    )
    args = parser.parse_args(argv)

    load_env_file()
    status = alerts.status(EventStore(args.db))
    password = alerts.smtp_password()

    print(f"email configured: {status['email_configured']}")
    print(f"recipient:        {status['recipient'] or '(no ALERT_EMAIL_TO / MAIL_DEFAULT_SENDER)'}")
    print(f"from:             {alerts.sender()}")
    print(f"smtp host:        {alerts.smtp_host() or '(no ALERT_SMTP_HOST / MAIL_SERVER)'}")
    print(f"smtp port:        {alerts.smtp_port()}")
    print(f"smtp tls mode:    {alerts.smtp_tls()}")
    print(f"smtp user:        {alerts.smtp_user() or '(anonymous relay)'}")
    print(f"smtp password:    {'set (' + str(len(password)) + ' chars)' if password else 'MISSING'}")
    print(f"daily budget:     {status['daily_token_budget'] or 'off'}")
    print(f"tokens today:     {status['tokens_today']}")
    print(f"errors today:     {status['errors_today']}")

    if not args.send:
        print("\nAdd --send to deliver a test email.")
        return 0

    if not status["email_configured"]:
        print("\nCannot send: set a recipient and MAIL_SERVER (or ALERT_EMAIL_TO + ALERT_SMTP_HOST).")
        return 1

    ok = alerts.send_email(
        "[English tutor] test alert",
        "If you can read this, email alerts work.\n\n"
        "The tutor sends mail when the daily token budget is crossed "
        "or when a turn fails.\n",
    )
    print("\ntest email: " + ("sent" if ok else "FAILED (check host, port, TLS mode, app password)"))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
