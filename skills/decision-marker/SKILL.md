---
description: Surface meaningful agent micro-decisions to the user before tool execution. Triggered by Cockpit's PreToolUse hook for decision-worthy tools.
disable-model-invocation: true
---

# Decision Marker

Cockpit's second principle: **surface every meaningful micro-decision before the agent commits to it**. This solves spec.md §2 FM2 (mid-execution invisibility) for the 6 decision-worthy tools.

## Behavior (handled entirely by hook)

For 6 decision-worthy tools (D3 decision):
- **WebSearch** — query selection
- **WebFetch** — URL + extraction prompt
- **Task** — subagent delegation
- **Edit** — file modification
- **Write** — file creation
- **NotebookEdit** — notebook modification

The PreToolUse hook intercepts the tool call and returns `permissionDecision: "ask"` with a Cockpit-formatted reason. Claude Code's built-in permission dialog displays the reason — user approves or denies.

## Tools NOT in the ask list

These get silent allow (no Cockpit dialog):
- **Read / Grep / Glob** — exploration tools, decisions visible via thought block (F1)
- **Bash** — Claude Code's own permission system handles destructive ones
- **AskUserQuestion / ExitPlanMode / TodoWrite** — workflow tools, not decision points
- **mcp__\*** — MCP server tools, behavior varies, v0.1 not intercepted

## Why these 6, not all

Per Decision D3 (Risk-based filtering): Cockpit intervenes at "commit-direction" moments (research commit + write commit), not at exploration moments. Bash is excluded because Claude Code's existing permission system already handles destructive shell commands — Cockpit asking would create UI overlap.

## Reason text format

```
🛂 Cockpit Decision Point — {tool_name}

Agent wants to:
  {formatted choice — query / url / file_path / etc.}

Approve this choice? (Choose 'no' to redirect agent.)
```

The hook extracts the relevant fields from `tool_input` (no agent declaration needed — `<cockpit-decision>` block was dropped per Q4=drop).

## User actions

- **Approve** → tool call proceeds
- **Deny** → tool call blocked. v0.1 abort behavior; v0.2 will support redirect.

## Behavior is hook-driven

Claude does not invoke this skill manually. It exists as documentation of Cockpit's principle. Actual behavior lives in `hooks/pre_tool_use.py`.
