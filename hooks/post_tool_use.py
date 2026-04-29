#!/usr/bin/env python3
"""
Agent Cockpit — PostToolUse hook.

Records every tool call to .cockpit/[date].jsonl.
Schema mirrors disler/claude-code-hooks-multi-agent-observability event format
(Decision Q3/D7 = B), so users can run Cockpit + disler dashboard together.

Fails silent on any error (Decision Q5).
"""
import json
import os
import sys
from datetime import datetime, timezone

LOG_DIR_NAME = ".cockpit"
SESSION_STATE_FILE = "session-state.json"


def read_session_state(cwd: str) -> dict:
    path = os.path.join(cwd, LOG_DIR_NAME, SESSION_STATE_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, json.JSONDecodeError):
        return {}


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    cwd = input_data.get("cwd") or os.getcwd()
    state = read_session_state(cwd)
    scenario = state.get("current_scenario", "trivial")

    # Build tool_call entry
    raw_output = input_data.get("tool_output", "")
    if not isinstance(raw_output, str):
        try:
            raw_output = json.dumps(raw_output, ensure_ascii=False)
        except (TypeError, ValueError):
            raw_output = str(raw_output)

    output_preview = raw_output[:500]
    output_truncated = len(raw_output) > 500

    tool_name = input_data.get("tool_name", "")
    # Decision metadata: surfaced if scenario was plan-worthy AND tool is in ask list
    ask_tools = {"WebSearch", "WebFetch", "Task", "Edit", "Write", "NotebookEdit"}
    surfaced = (scenario == "plan-worthy") and (tool_name in ask_tools)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": input_data.get("session_id", ""),
        "tool_use_id": input_data.get("tool_use_id", ""),
        "event_type": "tool_call",
        "tool_name": tool_name,
        "tool_input": input_data.get("tool_input", {}),
        "output_preview": output_preview,
        "output_truncated": output_truncated,
        "cockpit_decision": {
            "surfaced": surfaced,
            # user_action is unknown to PostToolUse since dialog already resolved.
            # If tool ran, it was approved. (deny path doesn't reach PostToolUse.)
            "user_action": "approved" if surfaced else "skipped",
        },
    }

    # Append to log
    try:
        log_dir = os.path.join(cwd, LOG_DIR_NAME)
        os.makedirs(log_dir, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = os.path.join(log_dir, f"{today}.jsonl")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except (IOError, OSError):
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
