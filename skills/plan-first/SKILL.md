---
description: Force agent to declare structured plan before tool execution. Activated by Cockpit's UserPromptSubmit hook for plan-worthy tasks.
disable-model-invocation: true
---

# Plan-First

Cockpit's first principle: **before any tool call, the agent declares a structured plan**. This solves spec.md §2 FM1 (pre-execution blindness).

## Behavior

For plan-worthy tasks (filtered by Haiku judge in UserPromptSubmit hook), agent must output a `<cockpit-plan>` block before any tool call. Format adapts to task complexity (2 tiers).

### Tier 1 — Simple task (1-3 steps)

```
<cockpit-plan>
- 1. [step] (using [tool])
- 2. [step] (using [tool])
- ETA: ~Xmin
</cockpit-plan>
```

### Tier 2 — Detailed task (multi-step)

```
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
```

## Why this exists

Without Plan-First, users hit Enter and don't know what the agent is about to do until it's already executing. With Plan-First, users see the approach before any tool runs and catch wrong assumptions before they propagate.

## Behavior is hook-driven

This skill is loaded automatically by Cockpit's `UserPromptSubmit` hook. Claude doesn't invoke it manually. The hook also performs **β verification** in `PreToolUse`: if no `<cockpit-plan>` block exists when first tool call arrives, the tool call is denied with reason "Output cockpit-plan first" — Claude retries with plan included.

## Plan is informational, not gating

Per design decision Friction Option ① and α/β = β:
- Plan **must** be output (β-enforced via PreToolUse deny)
- User **does not** approve plan (Haiku judge already classified it as plan-worthy)
- Agent proceeds to tool calls immediately after plan

User's authority over plan-worthy classification is via `/cockpit on/off/auto` slash command (controls global mode).
