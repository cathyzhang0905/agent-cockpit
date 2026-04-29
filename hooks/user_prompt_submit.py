#!/usr/bin/env python3
"""
Agent Cockpit — UserPromptSubmit hook.

Main brain of Cockpit. Lifecycle:
  1. Read user override mode from ~/.claude/cockpit.json
  2. If "off"  → exit silently (Cockpit disabled this session)
  3. If "on"   → skip Haiku, force plan-worthy
  4. If "auto" → call Haiku judge to classify task as plan-worthy / trivial
  5. If plan-worthy → inject plan-first instruction + write session state
  6. If trivial → write session state, no instruction injection
  7. Always log scenario_judge entry to .cockpit/[date].jsonl

Per Decision R1: Haiku failures fall back to "plan-worthy" (conservative).
Per Decision Sub-Q4: trivial tasks get NO Cockpit interference.
Per Decision Q5: hook fails silent (sys.exit 0) on any internal error.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

CONFIG_PATH = os.path.expanduser("~/.claude/cockpit.json")
LOG_DIR_NAME = ".cockpit"
HAIKU_MODEL = "claude-haiku-4-5"
HAIKU_TIMEOUT_SECONDS = 5

# ----------------------------------------------------------------------------
# Haiku judge prompt (D4.5 — Conservative + 5 explicit triggers + reason log)
# ----------------------------------------------------------------------------

HAIKU_PROMPT = """You are a triage classifier for Claude Code task oversight (Cockpit).

Given a user prompt (in any language, including Chinese), decide:
does this task benefit from a structured plan before tool execution?

Reply with JSON only:
{
  "decision": "plan" | "skip",
  "reason": "<one short sentence in same language as user prompt>"
}

Reply "plan" if ANY of these are clearly true:
1. Deep research task — comparing entities, analyzing competitors,
   multi-source synthesis, in-depth investigation (深度调研类)
2. Multiple external information gathering — multiple WebSearch/WebFetch
   steps expected (涉及外部多次搜集)
3. File modifications — creating, editing, writing files including code
   (文件修改/写代码)
4. Long-running task — estimated >3 minutes execution time
   (任务时间长)
5. Multi-step task with 3+ tool calls and multiple decision points

Reply "skip" if ANY of these:
- Conversational ("hi", "thanks", "你好", "explain X")
- Single-step lookup ("what time", "read README.md", "今天几号")
- Pure explanation/thinking, no tool use needed
- Small code question ("how do I X in Python", "Python 怎么 Y")

When ambiguous between plan and skip, lean "skip" — Cockpit is for
genuinely complex tasks. But if any of the 5 plan triggers is clearly
present, ALWAYS choose "plan".

User prompt:
\"\"\"
{prompt}
\"\"\"

Your reply (JSON only):"""

# ----------------------------------------------------------------------------
# Plan-first instruction (covers D1, D4 plan format, F1 thought, F5 assumption)
# ----------------------------------------------------------------------------

PLAN_INSTRUCTION = """[Cockpit Active] You are operating under Agent Cockpit — an active oversight layer.

This task has been classified as plan-worthy. You MUST follow these rules:

═══ 1. PLAN-FIRST ═══

Before calling any tool, output a structured plan. Choose tier based on task complexity:

Tier 1 (simple task, 1-3 steps):
<cockpit-plan>
- 1. [step] (using [tool])
- 2. [step] (using [tool])
- ETA: ~Xmin
</cockpit-plan>

Tier 2 (detailed task, multi-step):
<cockpit-plan>
Goal: [one-line objective]

Steps:
- 1. [step] (using [tool])
- 2. [step] (using [tool])
- 3. ...

ETA: ~Xmin
Key decisions: [step numbers where meaningful choices happen]
Assumptions: [non-trivial assumptions only — skip if none]
</cockpit-plan>

Plan is informational — proceed to tool calls immediately after. The user does NOT need to approve.

═══ 2. THINKING CHECKPOINT (after EVERY tool call) ═══

After each tool call result, BEFORE deciding next action, output:

<cockpit-thought>
Got: [one-sentence summary of what tool returned that's relevant]
Insight: [optional — if finding changed your mental model or plan; skip if no change]
Next: [next action + brief why]
</cockpit-thought>

Then proceed immediately to next action. Do NOT wait for user approval.

═══ 3. ASSUMPTION MARKER (when making non-trivial assumptions) ═══

When you make an assumption that meaningfully affects output (especially in data analysis), declare:

<cockpit-assumption>
Assuming: [the assumption]
Why: [why making this assumption]
Impact: [what changes if this assumption is wrong]
</cockpit-assumption>

Only declare non-trivial assumptions (skip "assuming utf-8 encoding" type trivia).

═══ 4. BRIEF (at end of task) ═══

Before finishing your response, output:

Tier 1 brief (simple task):
<cockpit-brief>
Done in ~Tmin. N decisions. Output: PATH
</cockpit-brief>

Tier 2 brief (detailed task):
<cockpit-brief>
Decisions made: N
Outputs: [paths]
Time taken: ~Tmin
Recommend review: [1-2 decisions worth re-examining, or omit if none]
</cockpit-brief>

═══ Core principle ═══

Human decisions must be explicit and never bypassed. Cockpit scaffolds your reasoning; the human watches and intervenes if needed.

For Read / Grep / Glob / Bash tools: proceed silently (Cockpit doesn't ask before these).
For WebSearch / WebFetch / Task / Edit / Write / NotebookEdit: Claude Code will surface a permission dialog with Cockpit context — the user approves or denies.
"""

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def read_user_override() -> str:
    """Read user override mode from global config. Returns 'auto' if missing."""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
            mode = data.get("mode", "auto")
            if mode in ("auto", "on", "off"):
                return mode
            return "auto"
    except (IOError, OSError, json.JSONDecodeError):
        return "auto"


def call_haiku_judge(prompt: str) -> dict:
    """Call Haiku to classify task. R1: failures fall back to 'plan'."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "decision": "plan",
            "reason": "ANTHROPIC_API_KEY missing — fallback to plan (R1 conservative)",
        }

    body = json.dumps({
        "model": HAIKU_MODEL,
        "max_tokens": 200,
        "messages": [{
            "role": "user",
            "content": HAIKU_PROMPT.format(prompt=prompt),
        }],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=HAIKU_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["content"][0]["text"].strip()
            # Strip potential markdown code fence
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:-1])
            parsed = json.loads(text)
            decision = parsed.get("decision", "plan")
            if decision not in ("plan", "skip"):
                decision = "plan"
            return {
                "decision": decision,
                "reason": parsed.get("reason", "")[:200],
            }
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, KeyError, IndexError, TimeoutError, OSError) as e:
        return {
            "decision": "plan",
            "reason": f"Haiku call failed: {str(e)[:80]} — fallback to plan",
        }


def write_log(cwd: str, entry: dict) -> None:
    """Append JSONL log entry. Fails silently."""
    try:
        log_dir = os.path.join(cwd, LOG_DIR_NAME)
        os.makedirs(log_dir, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = os.path.join(log_dir, f"{today}.jsonl")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except (IOError, OSError):
        pass


def write_session_state(cwd: str, state: dict) -> None:
    """Write session state file. Fails silently."""
    try:
        state_dir = os.path.join(cwd, LOG_DIR_NAME)
        os.makedirs(state_dir, exist_ok=True)
        with open(os.path.join(state_dir, "session-state.json"), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except (IOError, OSError):
        pass


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    user_prompt = input_data.get("prompt", "")
    cwd = input_data.get("cwd") or os.getcwd()
    session_id = input_data.get("session_id", "")
    now_iso = datetime.now(timezone.utc).isoformat()

    override = read_user_override()

    if override == "off":
        # Cockpit disabled this session
        write_session_state(cwd, {
            "session_id": session_id,
            "current_scenario": "off",
            "plan_required": False,
            "last_prompt_at": now_iso,
        })
        sys.exit(0)

    if override == "on":
        decision = "plan"
        reason = "User override: /cockpit on (forces plan-worthy)"
    else:  # auto
        judgment = call_haiku_judge(user_prompt)
        decision = judgment["decision"]
        reason = judgment["reason"]

    # Log scenario_judge entry
    write_log(cwd, {
        "timestamp": now_iso,
        "session_id": session_id,
        "event_type": "scenario_judge",
        "prompt_preview": user_prompt[:200],
        "decision": decision,
        "reason": reason,
        "override_mode": override,
    })

    # Update session state
    write_session_state(cwd, {
        "session_id": session_id,
        "current_scenario": "plan-worthy" if decision == "plan" else "trivial",
        "plan_required": decision == "plan",
        "last_prompt_at": now_iso,
    })

    # Inject plan-first instruction if plan-worthy
    if decision == "plan":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": PLAN_INSTRUCTION,
            },
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
