---
description: Output a structured brief at end of plan-worthy tasks. Auto-rendered by Cockpit's Stop hook with adaptive 2-tier format.
disable-model-invocation: true
---

# Brief

Cockpit's third principle: **every plan-worthy task ends with a structured brief that surfaces what was decided and what's worth review**. Solves spec.md §2 FM3 (post-execution attribution gap).

## Behavior

Before finishing your response on a plan-worthy task, output a `<cockpit-brief>` block. Format adapts to task complexity (mirrors plan tier).

### Tier 1 — Simple task

```
<cockpit-brief>
Done in ~Tmin. N decisions. Output: PATH
</cockpit-brief>
```

### Tier 2 — Detailed task

```
<cockpit-brief>
Decisions made: N
Outputs: [list of paths or deliverables]
Time taken: ~Tmin
Recommend review: [1-2 decisions worth re-examining, or omit if none]
</cockpit-brief>
```

The `Recommend review` field is the soul of Tier 2 brief — agent flags its own uncertainty for the user.

## Why this exists

Without a brief, users see the final output but can't easily trace back to which decision caused which result. With a brief:
1. Scoped summary of what was decided
2. Pointer to specific decisions worth reviewing (agent self-flags risk)
3. List of artifacts produced

## Connection to decision log

The brief is the **human-facing summary**. The full audit trail lives in `./.cockpit/[date].jsonl` (written by `PostToolUse` hook).

JSONL schema is compatible with [disler/claude-code-hooks-multi-agent-observability](https://github.com/disler/claude-code-hooks-multi-agent-observability) event format — users can run Cockpit + disler dashboard together for retrospective analysis.

## Behavior is hook-driven

`Stop` hook parses the transcript for `<cockpit-brief>` block and renders it in a Unicode-bordered box. Trivial tasks (Haiku judge → skip) get no brief.

## Failure mode

If you forget the brief block, the user sees no structured summary — degraded UX but not broken. The decision log JSONL still records every tool call.
