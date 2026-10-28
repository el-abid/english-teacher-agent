"""Manual live smoke test against the configured model. Not collected by pytest."""

from __future__ import annotations

import sys

from langgraph.types import Command

from english_teacher.graph import compile_graph, initial_state


def main() -> int:
    thread = sys.argv[1] if len(sys.argv) > 1 else "live-smoke"
    graph = compile_graph()
    config = {"configurable": {"thread_id": thread}}

    state = graph.invoke(initial_state("Yassine", "B1", "pass the bac"), config)
    prompt = state["__interrupt__"][0].value["prompt"]
    print("=== placement ===")
    print(prompt[:900])

    state = graph.invoke(Command(resume="1B 2A 3A"), config)
    print("\n=== first lesson ===")
    print(state["__interrupt__"][0].value["prompt"][:900])
    print("\n=== state ===")
    print(
        {
            "level": state["level"],
            "phase": state["phase"],
            "lessons": state["lessons_completed"],
            "mastery": {k: round(v["score"] * 100) for k, v in state["mastery"].items()},
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
