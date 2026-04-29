---
description: Make non-trivial agent assumptions explicit during execution. Critical for data analysis where implicit assumptions shape conclusions.
disable-model-invocation: true
---

# Assumption Marker (F5)

Cockpit's fifth principle: **make implicit assumptions explicit when they meaningfully affect output**. Solves spec.md §2 FM2 specifically for data analysis scenarios.

## Behavior — dual-track

### Track 1: Plan-time declaration

Include known assumptions in the `<cockpit-plan>` block's `Assumptions:` field at task start.

### Track 2: Mid-execution declaration

When you discover or make a non-trivial assumption mid-task (most common after seeing data), output a standalone block:

```
<cockpit-assumption>
Assuming: [the specific assumption]
Why: [why making this assumption — what data or context drove it]
Impact: [what changes if the assumption is wrong]
</cockpit-assumption>
```

## Frequency: only non-trivial

Declare assumptions that **meaningfully affect conclusions**. Skip trivia like:
- "Assuming UTF-8 encoding"
- "Assuming no NaN values"
- "Assuming integer overflow won't happen"

DO declare:
- "Assuming user_segment defined as last 30 days orders bucketed (high/mid/low) — data has no explicit segment field"
- "Assuming missing payment_status means failed (not pending) — no docs available"
- "Assuming cohort grouped monthly not weekly — stronger signal at month level"

The litmus test: **if this assumption is wrong, would the user's interpretation of the result change?** If yes, declare. If no, skip.

## Why this exists

Data analysis tasks are full of implicit choices that shape conclusions:
- Which slice dimension
- How to handle missing values
- What proxy to use when explicit field unavailable
- What grouping cadence

Without assumption markers, these are invisible — user sees the chart but doesn't know what assumption made it look that way. With markers, user can push back early ("wait, why did you bucket by 30 days? I want 90 days").

## Especially important for

- **Data analysis** — assumptions in slicing / grouping / methodology
- **Deep research** — assumptions about source authority / recency
- **Code modifications** — assumptions about user intent / API contract

## Non-blocking design

Like thought blocks, assumption markers are visible but don't pause execution. Agent declares, user reads in real-time, agent proceeds.

## Implementation

Pure skill-level instruction. The blocks appear in Claude Code's output stream and persist in transcript for later audit. v0.2 may add specialized parsing/logging.
