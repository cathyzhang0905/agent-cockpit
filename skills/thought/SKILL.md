---
description: Make agent thinking visible after every tool call. Output structured thought block for user to scan agent's reasoning chain.
disable-model-invocation: true
---

# Thinking Checkpoint (F1)

Cockpit's fourth principle: **make agent thinking visible between tool calls — without blocking execution**. Solves spec.md §2 FM2 (mid-execution invisibility) — the owner's primary pain point.

## Behavior

After EVERY tool call, BEFORE deciding next action, output:

```
<cockpit-thought>
Got: [one-sentence summary of what tool returned that's relevant]
Insight: [optional — if finding changed your mental model or plan]
Next: [next action + brief why]
</cockpit-thought>
```

Then proceed immediately to next action. **Do NOT wait for user approval.**

## Field semantics

- **Got** — what the tool returned that mattered (compressed). Not a full output dump; the highlight.
- **Insight** — only declare if the finding changes your mental model (e.g., "I expected early-stage, but they raised Series A; my thesis on stage was wrong"). Skip if no surprise.
- **Next** — what you'll do next + brief reason. One sentence.

## Why this exists

Owner's exact words (2026-04-29):
> "我希望看到 每次调用的时候 拿到了什么信息 怎么思考的下一步 这种 类似的信息"

Mapping:
- 拿到了什么信息 = **Got**
- 怎么思考的 = **Insight**
- 下一步 = **Next**

Without thinking checkpoints, agent's reasoning between tool calls is buried in long prose. With them, users scan 3 lines and know exactly:
- What the tool returned (compressed)
- Whether the agent's mental model shifted
- What's about to happen next

## Especially important for

- **Deep research / 深度调研** — multi-source synthesis where wrong source choice cascades
- **Data analysis / 数据分析** — where intermediate findings reshape next step
- **Long tasks** — where direction may pivot mid-execution

## Non-blocking design

Per owner's constraint: thoughts are visible but don't pause execution. Agent emits the block, then immediately proceeds. User can scan in real-time and manually interrupt if direction looks wrong.

## Implementation

Pure skill-level instruction. Hook does no enforcement on thought blocks (they're informational). The thought blocks appear in Claude Code's main output stream naturally — users read them as they appear.
