#!/usr/bin/env python3
"""
Agent Cockpit — Stop hook.

Renders <cockpit-brief> block from transcript at end of plan-worthy tasks.
Trivial tasks get no brief (per Sub-Q4: filter gates all of Cockpit).

Fails silent on any error (Decision Q5).
"""
import json
import os
import re
import sys

LOG_DIR_NAME = ".cockpit"
SESSION_STATE_FILE = "session-state.json"

BRIEF_PATTERN = re.compile(
    r"<cockpit-brief>(.*?)</cockpit-brief>",
    re.DOTALL | re.IGNORECASE,
)


def read_session_state(cwd: str) -> dict:
    path = os.path.join(cwd, LOG_DIR_NAME, SESSION_STATE_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, json.JSONDecodeError):
        return {}


def render_brief(brief_body: str) -> str:
    """Wrap brief body in a Unicode-bordered box."""
    lines = [line.rstrip() for line in brief_body.strip().splitlines() if line.strip()]
    if not lines:
        return ""

    inner_width = max(max(len(line) for line in lines), 40)
    title = "🛂 Cockpit Brief "
    top = "╭─ " + title + "─" * max(0, inner_width - len(title) - 2) + "╮"
    bottom = "╰" + "─" * (inner_width + 2) + "╯"

    framed = [top]
    for line in lines:
        padding = " " * (inner_width - len(line))
        framed.append(f"│ {line}{padding} │")
    framed.append(bottom)
    return "\n".join(framed)


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    cwd = input_data.get("cwd") or os.getcwd()
    transcript_path = input_data.get("transcript_path", "")

    # Only render brief for plan-worthy scenarios
    state = read_session_state(cwd)
    scenario = state.get("current_scenario", "trivial")
    if scenario != "plan-worthy":
        sys.exit(0)

    if not transcript_path or not os.path.exists(transcript_path):
        sys.exit(0)

    try:
        with open(transcript_path, encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        sys.exit(0)

    matches = BRIEF_PATTERN.findall(content)
    if not matches:
        # No brief output by Claude — silent (don't push noise)
        sys.exit(0)

    brief_body = matches[-1].strip()
    rendered = render_brief(brief_body)
    if not rendered:
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": "\n" + rendered + "\n",
        },
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
