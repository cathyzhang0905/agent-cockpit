---
description: Configure Agent Cockpit mode — toggle plan-first behavior on/off/auto.
---

# /cockpit — Configure Agent Cockpit

The user invoked `/cockpit` with arguments: $ARGUMENTS

Parse the arguments and update `~/.claude/cockpit.json` accordingly.

## Valid arguments

- `on` — Force plan-first behavior for ALL tasks this session (override Haiku judge)
- `off` — Disable Cockpit entirely (no plan injection, no decision dialogs, silent)
- `auto` (or empty) — Default mode: Haiku judge classifies each prompt as plan-worthy or trivial
- `status` — Show current mode

## Implementation

Use Bash to read or write the config file.

### If $ARGUMENTS is `status`:
```bash
if [ -f ~/.claude/cockpit.json ]; then
  cat ~/.claude/cockpit.json
else
  echo '{"mode": "auto"}  (default — file does not exist yet)'
fi
```
Then format the output for the user as: `🛂 Cockpit mode: [MODE]`

### If $ARGUMENTS is `on`, `off`, `auto`, or empty:

Translate empty → `auto`. If $ARGUMENTS is something else, tell user the valid options and stop.

```bash
mkdir -p ~/.claude
echo '{"mode": "MODE_HERE"}' > ~/.claude/cockpit.json
```

Where `MODE_HERE` is the validated argument. Then confirm to the user:

```
🛂 Cockpit mode set to: MODE_HERE

What this means:
- on  → Every task forces a plan-first flow + decision dialogs
- off → Cockpit silent (no plan injection, no dialogs, no brief)
- auto → Haiku judge classifies each prompt; only plan-worthy tasks get Cockpit treatment
```

## Common mistakes to handle

- If the user types `/cockpit ON` (uppercase) → normalize to lowercase
- If the user types `/cockpit help` → show valid arguments list
- If the user types something nonsense → reply with valid options, do NOT modify config
