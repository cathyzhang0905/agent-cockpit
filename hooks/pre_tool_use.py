#!/usr/bin/env python3
"""
Agent Cockpit — PreToolUse hook.

Decision守门人. Lifecycle:
  1. Read session-state.json to find current scenario (plan-worthy / trivial / off)
  2. If trivial or off → silent allow (Cockpit not active)
  3. β verification: ensure <cockpit-plan> block exists in transcript
     - If missing → deny tool call with reason "output plan first"
     - Claude will retry with plan
  4. Check if tool is in ASK_TOOLS list (D3 = 6 tools)
     - If yes → return permissionDecision: "ask" with formatted Cockpit reason
     - If no → silent allow

Per Decision R1 / Q5: fails silent on any internal error.
Per Decision D2: uses Claude Code's built-in permission dialog (no custom UI).
Per Decision D3: ASK_TOOLS = WebSearch/WebFetch/Task/Edit/Write/NotebookEdit.
Per Decision α/β: β = hard enforcement of plan via transcript verification.
"""
import json
import os
import re
import sys

LOG_DIR_NAME = ".cockpit"
SESSION_STATE_FILE = "session-state.json"

# Decision-worthy tools (D3) — these get Cockpit ask dialog
ASK_TOOLS = {"WebSearch", "WebFetch", "Task", "Edit", "Write", "NotebookEdit"}

# Pattern to find <cockpit-plan> blocks in transcript
PLAN_BLOCK_PATTERN = re.compile(r"<cockpit-plan>(.*?)</cockpit-plan>", re.DOTALL | re.IGNORECASE)


def read_session_state(cwd: str) -> dict:
    """Read session state. Returns empty dict on failure."""
    path = os.path.join(cwd, LOG_DIR_NAME, SESSION_STATE_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (IOError, OSError, json.JSONDecodeError):
        return {}


def has_recent_plan(transcript_path: str) -> bool:
    """β verification: check if <cockpit-plan> block exists in transcript."""
    if not transcript_path or not os.path.exists(transcript_path):
        # Can't verify → fail-safe to allow (don't block on missing transcript)
        return True

    try:
        with open(transcript_path, encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return True  # fail-safe

    matches = PLAN_BLOCK_PATTERN.findall(content)
    return len(matches) > 0


def format_choice(tool_name: str, tool_input: dict) -> str:
    """Format the agent's choice for display in Cockpit dialog reason."""
    if tool_name == "WebSearch":
        query = tool_input.get("query", "")
        return f'  query: "{query}"'

    if tool_name == "WebFetch":
        url = tool_input.get("url", "")
        prompt = tool_input.get("prompt", "")
        prompt_preview = prompt[:80] + ("..." if len(prompt) > 80 else "")
        return f'  url: {url}\n  extract: "{prompt_preview}"'

    if tool_name == "Task":
        sub = tool_input.get("subagent_type", "general-purpose")
        desc = tool_input.get("description", "")
        return f'  subagent: {sub}\n  task: "{desc}"'

    if tool_name == "Edit":
        path = tool_input.get("file_path", "")
        old_str = tool_input.get("old_string", "")
        old_preview = old_str[:60] + ("..." if len(old_str) > 60 else "")
        return f'  file: {path}\n  changing: "{old_preview}"'

    if tool_name == "Write":
        path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")
        return f'  file: {path}\n  content: ({len(content)} chars)'

    if tool_name == "NotebookEdit":
        path = tool_input.get("notebook_path", "")
        return f'  notebook: {path}'

    # Fallback for unknown tool
    return f'  {str(tool_input)[:200]}'


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    cwd = input_data.get("cwd") or os.getcwd()
    transcript_path = input_data.get("transcript_path", "")

    state = read_session_state(cwd)
    scenario = state.get("current_scenario", "trivial")

    # If scenario is trivial or Cockpit off → silent allow
    if scenario in ("trivial", "off"):
        sys.exit(0)

    # Plan-worthy mode: β verification first
    if not has_recent_plan(transcript_path):
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "🛂 Cockpit β-Verification: plan required\n"
                    "\n"
                    "This task is plan-worthy. You must output a <cockpit-plan> block "
                    "BEFORE calling any tool. Please output your plan first, then retry."
                ),
            },
        }
        print(json.dumps(output))
        sys.exit(0)

    # Plan exists — check if tool is in ask list
    if tool_name not in ASK_TOOLS:
        # Tool not in ask list → silent allow (Read/Grep/Glob/Bash etc.)
        sys.exit(0)

    # Decision marker — surface to user via permission dialog
    choice_text = format_choice(tool_name, tool_input)
    reason = (
        f"🛂 Cockpit Decision Point — {tool_name}\n"
        f"\n"
        f"Agent wants to:\n"
        f"{choice_text}\n"
        f"\n"
        f"Approve this choice? (Choose 'no' to redirect agent.)"
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        },
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
