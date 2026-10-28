"""Check Langfuse credentials and print the traces this agent produced.

Usage:
    uv run python scripts/langfuse_check.py
    uv run python scripts/langfuse_check.py --send
    uv run python scripts/langfuse_check.py --session web-3656f1da0347

``--send`` emits one throwaway span first, which proves ingestion works before
you run a lesson. ``--session`` narrows the listing to one browser session.
"""

from __future__ import annotations

import argparse
import os

from english_teacher.config import load_env_file
from english_teacher.tracing import tracing_configured


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Langfuse health check for the tutor")
    parser.add_argument("--send", action="store_true", help="send one test span first")
    parser.add_argument("--session", default="", help="only this Langfuse session id")
    parser.add_argument("--limit", type=int, default=10, help="how many rows to print")
    args = parser.parse_args(argv)

    load_env_file()
    if not tracing_configured():
        print("Langfuse keys not found in the environment or in .env.")
        print(r"Create english-teacher-agent\.env and add the two lines:")
        print("  LANGFUSE_PUBLIC_KEY=pk-lf-...")
        print("  LANGFUSE_SECRET_KEY=sk-lf-...")
        print("Then restart `uv run english-teacher-web` and rerun this script.")
        return 1

    from langfuse import get_client

    client = get_client()
    host = os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"
    print(f"host:  {host}")

    if not client.auth_check():
        print("auth:  FAILED - wrong key pair, or the host is unreachable.")
        return 2
    print("auth:  ok")

    if args.send:
        with client.start_as_current_observation(
            name="langfuse-check",
            as_type="span",
            input={"source": "scripts/langfuse_check.py"},
            output={"ok": True},
        ):
            pass
        client.flush()
        print("sent:  one test span")

    page = client.api.observations.get_many(
        limit=args.limit,
        session_id=args.session or None,
    )
    rows = list(getattr(page, "data", []) or [])
    if not rows:
        print("\nNo observations yet. Run a lesson (or use --send), then rerun.")
        return 0

    print(f"\n{len(rows)} observation(s), newest first:")
    for row in rows:
        trace_id = getattr(row, "trace_id", "") or ""
        name = getattr(row, "name", "?")
        kind = getattr(row, "type", "?")
        session = getattr(row, "session_id", "") or ""
        print(f"- {name} [{kind}] trace={trace_id} session={session}")
        url = client.get_trace_url(trace_id=trace_id) if trace_id else None
        if url:
            print(f"  {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
