"""Terminal chat loop that drives the graph's interrupts."""

from __future__ import annotations

import argparse
import os
import sys
import uuid

from langgraph.types import Command

from .cefr import LEVELS
from .config import load_env_file, load_settings
from .graph import compile_graph, initial_state, make_checkpointer
from .tracing import flush, trace_config


def _interrupt_prompt(state: dict) -> str | None:
    interrupts = state.get("__interrupt__") or ()
    if not interrupts:
        return None
    value = getattr(interrupts[0], "value", interrupts[0])
    if isinstance(value, dict):
        return str(value.get("prompt", ""))
    return str(value)


def chat(
    level: str = "",
    name: str = "",
    goal: str = "",
    thread: str | None = None,
    model: str | None = None,
) -> int:
    if model:
        os.environ["ENGLISH_TEACHER_MODEL"] = model
    settings = load_settings()
    graph = compile_graph(make_checkpointer(settings.db_path))
    thread_id = thread or f"student-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    config.update(trace_config(thread_id, user_id=name, tags=("cli", level or "auto")))

    print(f"English teacher agent · model={settings.model} · thread={thread_id}")
    print("Type 'quit' to stop. The graph checkpoints every turn.\n")

    try:
        state = graph.invoke(initial_state(name, level, goal), config)
    except Exception as exc:  # noqa: BLE001 - surface provider/auth errors to the student
        print(f"Could not start the session: {exc}", file=sys.stderr)
        print(
            "Check ENGLISH_TEACHER_MODEL and your provider API key (.env).",
            file=sys.stderr,
        )
        return 1

    while True:
        prompt = _interrupt_prompt(state)
        if prompt is None:
            break

        print(f"\nMs. Rivera:\n{prompt}\n")
        try:
            reply = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[session paused]")
            return 0

        if reply.lower() in {"quit", "exit", ":q"}:
            print("[session paused]")
            return 0
        if not reply:
            print("(empty message, ask again)")
            continue

        try:
            state = graph.invoke(Command(resume=reply), config)
        except Exception as exc:  # noqa: BLE001 - keep the session alive, explain the failure
            print(f"\nThe tutor could not continue: {exc}", file=sys.stderr)
            return 1

        level_now = state.get("level")
        if level_now:
            done = int(state.get("lessons_completed", 0))
            print(f"\n[level {level_now} · {done} topics completed · thread {thread_id}]")

    final = state.get("teacher_message")
    if final and state.get("graduated"):
        print(f"\nMs. Rivera:\n{final}")
    print(f"\nSession ended (level {state.get('level')}, phase {state.get('phase')}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CEFR English teacher agent")
    parser.add_argument("--level", choices=LEVELS, default="", help="starting CEFR level")
    parser.add_argument("--name", default="", help="student name")
    parser.add_argument("--goal", default="", help="why the student is learning English")
    parser.add_argument("--thread", default=None, help="resume an existing session id")
    parser.add_argument("--model", default=None, help="override ENGLISH_TEACHER_MODEL")
    args = parser.parse_args(argv)

    load_env_file()
    try:
        return chat(args.level, args.name, args.goal, args.thread, args.model)
    finally:
        flush()


if __name__ == "__main__":
    raise SystemExit(main())
