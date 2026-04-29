# Agent Cockpit

> **Active oversight layer for Claude Code agents.**

Forces agents to declare their plan before acting. Surfaces every micro-decision for human review. Makes agent thinking visible during execution. Pauses on critical choices so you can override.

```
> "AI tools are honestly unusable without running in yolo mode.
>  You have to baby every single little command. It is utterly miserable and awful."
> — Hacker News, 255 points
```

**Cockpit is the middle ground between "yolo" and "baby every command".**

---

## Why this exists

When you delegate a task to an AI agent, you lose access to its decision-making at exactly the moments when you most need to be involved.

Three failure modes this creates:

1. **Pre-execution blindness** — You hit Enter; you don't know what the agent is about to do until it's already doing it.
2. **Mid-execution invisibility** — Agent makes 5-50 micro-decisions per task (which tool, which source, what assumption). All invisible. Each one shapes the output silently.
3. **Post-execution attribution gap** — When output is wrong, you can't trace it back to the decision that caused it.

Cockpit's five core functions map directly:

| Failure mode | Cockpit solution |
|---|---|
| ① Pre-execution blindness | **Plan-First** — agent declares plan; β verification ensures plan exists before any tool runs |
| ② Mid-execution invisibility | **Decision Markers** (6 commit tools) + **Thinking Checkpoint** (every tool) + **Assumption Marker** (data analysis) |
| ③ Post-execution attribution gap | **Brief** — agent flags decisions worth review + **JSONL log** (mirror disler schema) |

---

## Design principle

**The human decision step must be explicit and never bypassed.**

This is humanism implemented at the product layer. The agent never makes a hidden decision; the human is always one keystroke away from intervention.

---

## Relationship to existing observability tools

Cockpit is **complementary**, not competitive, with existing Claude Code observability:

| Tool | What it does | What Cockpit adds |
|---|---|---|
| [disler/claude-code-hooks-multi-agent-observability](https://github.com/disler/claude-code-hooks-multi-agent-observability) | Real-time event dashboard for what happened | Active oversight for what's about to happen + thinking visibility |
| [simple10/agents-observe](https://github.com/simple10/agents-observe) | Multi-agent hierarchy visualization | Pre-execution decision review + assumption markers |

Cockpit's `./.cockpit/[date].jsonl` decision log uses an **event schema compatible with disler's**, so you can run both: Cockpit for active control, dashboards for retrospective analysis.

---

## Install

### Prerequisites

- Claude Code installed and authenticated
- `ANTHROPIC_API_KEY` environment variable set (for Haiku scenario classifier)

### Local development install

```bash
git clone https://github.com/cathyzhang0905/agent-cockpit.git
cd agent-cockpit
chmod +x hooks/*.py
```

Then run Claude Code with the plugin:

```bash
claude --plugin-dir /path/to/agent-cockpit
```

### Verify install

In Claude Code, run:
```
/cockpit status
```
Should show your current mode (default: auto).

---

## How it works

### Cockpit mode (one of three)

```bash
/cockpit auto    # Default — Haiku judge classifies each prompt
/cockpit on      # Force plan-first for ALL tasks this session
/cockpit off     # Disable Cockpit entirely (silent, no overhead)
```

Mode persists in `~/.claude/cockpit.json` across sessions.

### What happens for each task type

**Trivial task** (e.g., "today's weather"):
- Haiku judge → skip
- Zero Cockpit interference. No plan, no dialogs, no brief.

**Plan-worthy task** (e.g., "research lindy.ai"):
1. Haiku judge → plan
2. Agent outputs `<cockpit-plan>` block (informational; β-verified)
3. Before each WebSearch/WebFetch/Task/Edit/Write/NotebookEdit:
   ```
   🛂 Cockpit Decision Point — WebSearch
   Agent wants to:
     query: "lindy.ai funding 2026"
   Approve this choice? (Choose 'no' to redirect agent.)
   ```
4. After each tool call, agent outputs `<cockpit-thought>`:
   ```
   Got: Lindy raised $50M Series A March 2026
   Insight: Mid-stage, not early — earlier hypothesis wrong
   Next: Fetch about page to confirm vision-thesis match
   ```
5. When making non-trivial assumptions:
   ```
   <cockpit-assumption>
   Assuming: user_segment by last_30d_orders bucketed
   Why: No explicit segment field in data
   Impact: Distribution may not support clean tertiles
   </cockpit-assumption>
   ```
6. End of task — Cockpit Brief in framed box:
   ```
   ╭─ 🛂 Cockpit Brief ────────────────────────╮
   │ Decisions made: 5                         │
   │ Outputs: ./lindy_profile.md               │
   │ Time taken: ~3 min                        │
   │ Recommend review: Step 3 (vision mismatch │
   │   with thesis is the key finding)         │
   ╰───────────────────────────────────────────╯
   ```

### What's logged

Every tool call → `./.cockpit/[date].jsonl`:
```jsonc
{
  "timestamp": "2026-04-29T...",
  "session_id": "...",
  "tool_use_id": "...",
  "event_type": "tool_call",
  "tool_name": "WebSearch",
  "tool_input": {"query": "..."},
  "output_preview": "...",
  "cockpit_decision": {
    "surfaced": true,
    "user_action": "approved"
  }
}
```

Plus `scenario_judge` entries from Haiku classifier.

---

## Configuration

`~/.claude/cockpit.json`:
```json
{ "mode": "auto" }
```

Hook behavior is configured in `hooks/hooks.json` (matchers + script paths). Edit the `PreToolUse` matcher to extend / restrict which tools trigger Cockpit dialogs.

---

## v0.1 scope

✅ Plan-First (β hard enforcement)
✅ Decision Markers (6 commit-direction tools)
✅ Thinking Checkpoint (every tool call, 3-field structured)
✅ Assumption Marker (data analysis, dual-track plan + mid-execution)
✅ Brief (2-tier adaptive)
✅ JSONL log (mirror disler schema)
✅ Haiku scenario filter + user override
✅ `/cockpit on/off/auto` slash command

**v0.1 solves ~83% of original spec promise** (FM1: 85%, FM2: 85%, FM3: 80%). See [v01-completion-analysis.md](v01-completion-analysis.md) for honest gap analysis.

---

## v0.2+ Roadmap

- Override redirect (deny + user-provided alternative)
- `/cockpit status` full with recent Haiku decisions
- Pattern learning ("you've overridden type X 7 times, set rule?")
- Optional web dashboard or direct export to disler
- Cross-AI support (Cursor / Devin / OpenAI Agents SDK)
- Mid-task check-in (every N tool calls, agent pauses)
- Confidence scoring per tool call

See `archived/architecture.md` §7 for complete roadmap.

---

## Documentation

- [spec.md](spec.md) — Product spec (what + why)
- [architecture.md](architecture.md) — Implementation architecture (how + why this way), includes 21-decision Decision Log
- [user-research.md](user-research.md) — Real user voice quotes from HN / V2EX validating the pain
- [v01-completion-analysis.md](v01-completion-analysis.md) — Honest assessment of what v0.1 solves vs spec promise

---

## Acknowledgments

- [disler/claude-code-hooks-multi-agent-observability](https://github.com/disler/claude-code-hooks-multi-agent-observability) — established the hook-based observability pattern (1.4k stars)
- [simple10/agents-observe](https://github.com/simple10/agents-observe) — inspired multi-agent hierarchy thinking (510 stars)
- Microsoft HAX Toolkit / Saleema Amershi's [18 Human-AI Interaction Guidelines](https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/) — design language for human-AI teaming
- Anthropic ["Building Effective Agents"](https://www.anthropic.com/engineering/building-effective-agents) — agent system design framework

Special call-out: Anthropic shipped Claude Code with a `userPromptKeywords.ts` regex that scans user messages for frustration words (per source leak analysis). They detect frustration. **Cockpit prevents it.**

---

## License

MIT — see [LICENSE](LICENSE).
