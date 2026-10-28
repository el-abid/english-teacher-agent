"""Operational governance: SemVer, Agent Card state and the kill switch.

The kill switch is deliberately small and file-backed. A local operator or the
admin API can suspend mutating traffic without restarting the process, and the
``ENGLISH_TEACHER_KILL_SWITCH`` environment variable remains a break-glass
override that no API call can clear.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

KILL_SWITCH_ENV = "ENGLISH_TEACHER_KILL_SWITCH"
KILL_SWITCH_REASON_ENV = "ENGLISH_TEACHER_KILL_SWITCH_REASON"
KILL_SWITCH_FILE_ENV = "ENGLISH_TEACHER_KILL_SWITCH_FILE"
ADMIN_TOKEN_ENV = "ENGLISH_TEACHER_ADMIN_TOKEN"
_TRUTHY = {"1", "true", "yes", "on"}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def kill_switch_path(db_path: str | None = None) -> Path:
    """Explicit override, otherwise a sibling of the sessions database."""
    override = os.getenv(KILL_SWITCH_FILE_ENV, "").strip()
    if override:
        return Path(override)
    return Path(db_path or "sessions.sqlite").with_name("kill-switch.json")


def admin_token() -> str:
    """The configured admin secret. Empty means the admin API is disabled."""
    return os.getenv(ADMIN_TOKEN_ENV, "").strip()


def token_matches(expected: str, provided: str) -> bool:
    """Constant-time comparison; an empty expected token never matches."""
    if not expected or not provided:
        return False
    return hmac.compare_digest(expected, provided)


class KillSwitch:
    """File-backed suspension state shared by the API, the CLI and operators."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else kill_switch_path()
        self._lock = threading.Lock()

    def _read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _env_active(self) -> bool:
        return os.getenv(KILL_SWITCH_ENV, "").strip().lower() in _TRUTHY

    def status(self) -> dict[str, Any]:
        stored = self._read()
        env_active = self._env_active()
        file_active = bool(stored.get("active"))
        active = file_active or env_active

        reason = str(stored.get("reason", "") or "")
        source = "file" if file_active else "none"
        if env_active:
            reason = os.getenv(KILL_SWITCH_REASON_ENV, "").strip() or (
                f"{KILL_SWITCH_ENV} is set"
            )
            source = "env"
        elif not file_active:
            reason = ""

        return {
            "active": active,
            "reason": reason,
            "actor": str(stored.get("actor", "") or ""),
            "since": str(stored.get("since", "") or "") if active else "",
            "source": source,
            "env_override": env_active,
        }

    def set(self, active: bool, *, reason: str = "", actor: str = "") -> dict[str, Any]:
        """Persist a new state. The environment override still wins on read."""
        moment = _now()
        payload = {
            "active": bool(active),
            "reason": reason.strip()[:300],
            "actor": actor.strip()[:80],
            "since": moment if active else "",
            "updated_at": moment,
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        return self.status()


def main(argv: list[str] | None = None) -> int:
    """Operator CLI: ``english-teacher-governance status|on|off``."""
    parser = argparse.ArgumentParser(description="Language teacher kill switch")
    parser.add_argument(
        "--file",
        default=None,
        help=f"state file (default: ${KILL_SWITCH_FILE_ENV} or kill-switch.json)",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="print the current state as JSON")
    for name, help_text in (("on", "suspend mutating traffic"), ("off", "resume traffic")):
        action = subparsers.add_parser(name, help=help_text)
        action.add_argument("--reason", default="", help="why the switch is changing")
        action.add_argument("--actor", default="operator", help="who made the change")

    args = parser.parse_args(argv)
    switcher = KillSwitch(args.file)

    if args.command in {"on", "off"}:
        switcher.set(
            args.command == "on",
            reason=args.reason,
            actor=args.actor,
        )
    elif args.command not in {None, "status"}:
        parser.error(f"unknown command: {args.command}")

    status = switcher.status()
    status["store"] = str(switcher.path)
    print(json.dumps(status, indent=2, ensure_ascii=False))
    if status["active"] and args.command == "off":
        print(
            f"{KILL_SWITCH_ENV} is set; the switch stays active until it is unset.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
