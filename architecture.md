# Agent Cockpit — Architecture v0.1

**Status**: Design Complete（15/15 决策 nail 完）
**Date**: 2026-04-29
**Owner**: Cathy Zhang ([@cathyzhang0905](https://github.com/cathyzhang0905))
**Related**: [spec.md](spec.md)（产品 spec）+ [user-research.md](user-research.md)（用户证据）

---

## Table of Contents

1. [End-to-End Flow](#1-end-to-end-flow)
2. [File Structure](#2-file-structure)
3. [Runtime State Files](#3-runtime-state-files)
4. [Component-by-Component Reference](#4-component-by-component-reference)
5. [UX Matrix（5 个用户场景）](#5-ux-matrix5-个用户场景)
6. [Decision Log（15 个决策）](#6-decision-log)
7. [Open Questions for v0.2+](#7-open-questions-for-v02)

---

## 1. End-to-End Flow

```
┌───────────────────────────────────────────────────────────────┐
│ User 输入 prompt                                               │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ UserPromptSubmit hook                                         │
│                                                               │
│ Step 1: 读 ~/.claude/cockpit.json (Sub-Q2)                    │
│   ├─ mode = "off" → 跳过整个 Cockpit (sys.exit 0)              │
│   ├─ mode = "on"  → 跳过 Haiku，标记 plan-worthy=true，进 Step 3│
│   └─ mode = "auto" / 未设 → Step 2                            │
│                                                               │
│ Step 2: 调 Haiku judge (Sub-Q1, D4.5)                         │
│   input: user prompt                                          │
│   output: { decision: "plan"|"skip", reason: "..." }          │
│   ├─ "skip" (trivial) → Cockpit 全静音 (Sub-Q4 A)              │
│   │                       → 写 scenario_judge log             │
│   │                       → sys.exit 0                        │
│   └─ "plan" → Step 3                                          │
│                                                               │
│ Step 3: 写 scenario state 到 .cockpit/session-state.json      │
│         (用于 PreToolUse 知道当前 scenario)                    │
│                                                               │
│ Step 4: 注入 plan-first instruction (D1, D4)                  │
│   "请输出 <cockpit-plan>，2 档自适应                            │
│    Tier 1 (simple): steps + ETA                               │
│    Tier 2 (detailed): goal + steps + ETA + key decisions      │
│                                          + (optional) assumptions"│
│                                                               │
│ Step 5: 写 scenario_judge log (含 reason, debug 用)            │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ Claude 处理 prompt                                              │
│   if plan-worthy:                                             │
│     输出 <cockpit-plan>（informational，不需要 approve）          │
│     然后开始调 tool                                              │
│   else (trivial 已被跳过):                                       │
│     直接调 tool（无 plan）                                        │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼ Claude 调 tool
┌───────────────────────────────────────────────────────────────┐
│ PreToolUse hook                                               │
│                                                               │
│ Step 1: 读 .cockpit/session-state.json                         │
│         看本轮是 plan-worthy 还是 trivial                        │
│   ├─ trivial → silent allow (return 0，Cockpit 不介入)          │
│   └─ plan-worthy → Step 2                                     │
│                                                               │
│ Step 2: β-enforcement (α/β = β)                                │
│   读 transcript_path，找最近一次 user message 之后是否有          │
│   <cockpit-plan> 块                                            │
│   ├─ 没有 → return permissionDecision: "deny"                 │
│   │         + reason: "Output <cockpit-plan> first per Cockpit"│
│   │         (Claude 看到 deny 后会重新输出含 plan + 重试 tool)    │
│   └─ 有 → Step 3                                              │
│                                                               │
│ Step 3: 检查 tool name 是否在 ask list (D3)                    │
│   WebSearch | WebFetch | Task | Edit | Write | NotebookEdit   │
│   ├─ 是 → return permissionDecision: "ask" (D2)               │
│   │       + permissionDecisionReason: 格式化 Cockpit 文字       │
│   └─ 否 (Read/Grep/Glob/Bash/...) → silent allow              │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ Claude Code 内置 permission dialog 弹（D2）                     │
│   含 Cockpit 格式化 reason                                       │
│   user 按 y/n                                                  │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ Tool 执行 (or 阻拦 if user denied)                               │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ PostToolUse hook                                              │
│   写 tool_call log → .cockpit/[date].jsonl                    │
│   schema (Q3 = B, mirror disler):                             │
│     timestamp / session_id / tool_use_id / event_type /       │
│     tool_name / input / output_preview / cockpit_decision     │
│                                                               │
│   ★ F1 NEW: parse 最近的 <cockpit-thought> 块写 thought log     │
│   ★ F5 NEW: parse 最近的 <cockpit-assumption> 块写 assump log  │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────────────┐
│ ★ F1 NEW: Claude 输出 <cockpit-thought> 块（每个 tool 后）       │
│   Got:     [tool 返回的关键信息]                                │
│   Insight: [optional — 如果改变 mental model]                   │
│   Next:    [下一步 + 简短 why]                                  │
│                                                               │
│   不 block 执行——agent 输出后立即进下一个 tool call             │
│   用户在 Claude Code 主输出流自动看到，hook 顺手写 log           │
│                                                               │
│ ★ F5 NEW: Claude 在发现新 assumption 时输出                     │
│   <cockpit-assumption>                                        │
│   Assuming: [假设内容]                                          │
│   Why:      [为什么做这个假设]                                   │
│   Impact:   [假设错了会怎样]                                     │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼
                  (循环 PreToolUse → tool → PostToolUse → thought)
                          │
                          ▼ Claude 完成响应
┌───────────────────────────────────────────────────────────────┐
│ Stop hook                                                     │
│   if scenario was plan-worthy:                                │
│     parse transcript 找 <cockpit-brief>                        │
│     render 框 → output additionalContext                       │
│   else: 不 render (trivial 任务无 brief)                         │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. File Structure

```
agent-cockpit/
├── .claude-plugin/
│   └── plugin.json                # plugin 元信息
├── hooks/
│   ├── hooks.json                 # 4 个 hook 注册 + matcher
│   ├── user_prompt_submit.py      # ★ 主大脑：override → Haiku → 注入 + state
│   ├── pre_tool_use.py            # ★ scenario filter + β verify + tool ask
│   ├── post_tool_use.py           # JSONL log
│   └── stop.py                    # parse + render brief
├── skills/                         # 文档型，frontmatter `disable-model-invocation: true`
│   ├── plan-first/SKILL.md
│   ├── decision-marker/SKILL.md
│   ├── brief/SKILL.md
│   ├── thought/SKILL.md            # ★ F1 NEW: 教 Claude 每 tool call 后输出 thought
│   └── assumption/SKILL.md         # ★ F5 NEW: 教 Claude 在 plan + mid-execution 声明 assumption
├── commands/
│   └── cockpit.md                 # /cockpit on/off/auto
├── spec.md                        # 产品 spec
├── architecture.md                # 本文件
├── user-research.md               # 用户痛点证据
├── README.md                      # GitHub 主页（Day 7 写）
└── LICENSE                        # MIT
```

---

## 3. Runtime State Files

### 3.1 `~/.claude/cockpit.json`（global config，Sub-Q2 = C）

```jsonc
{
  "mode": "auto" | "on" | "off"
}
```

**含义**：
- `"auto"`（默认未设也算）→ 让 Haiku judge 决定每次任务
- `"on"` → 强制每次都走 plan-worthy 路径
- `"off"` → Cockpit 完全静音（hook 立即 return 0）

**修改方式**：用户跑 `/cockpit on/off/auto` slash command（commands/cockpit.md 实现），或手动编辑文件。

### 3.2 `[cwd]/.cockpit/[YYYY-MM-DD].jsonl`（per-day session log，Q3 = B mirror disler）

**3 种 entry type**：

#### 3.2.1 `scenario_judge`（UserPromptSubmit 写）
```jsonc
{
  "timestamp": "2026-04-29T14:30:15Z",
  "session_id": "sess_abc123",
  "event_type": "scenario_judge",
  "prompt_preview": "帮我调研 lindy.ai...",  // 截断 200 字
  "decision": "plan" | "skip",
  "reason": "Multi-source research with 3+ tool calls expected"
}
```

#### 3.2.2 `tool_call`（PostToolUse 写）
```jsonc
{
  "timestamp": "2026-04-29T14:30:20Z",
  "session_id": "sess_abc123",
  "tool_use_id": "toolu_01xyz",
  "event_type": "tool_call",
  "tool_name": "WebSearch",
  "tool_input": { "query": "lindy.ai funding 2026" },
  "output_preview": "Lindy raised $50M Series A...",  // 截断 500 字
  "output_truncated": true,
  "cockpit_decision": {
    "surfaced": true,                // PreToolUse 是否触发了 ask dialog
    "user_action": "approved"        // approved | denied | skipped
  }
}
```

#### 3.2.3 `session-state`（短期 state，per-session 可被覆盖）

Note: **不在 JSONL log 里**，是单独 `.cockpit/session-state.json`：
```jsonc
{
  "session_id": "sess_abc123",
  "last_prompt_at": "2026-04-29T14:30:15Z",
  "current_scenario": "plan-worthy" | "trivial",
  "plan_required": true | false
}
```
PreToolUse hook 读这个文件知道当前 scenario。

---

## 4. Component-by-Component Reference

### 4.1 `hooks/user_prompt_submit.py`（主大脑）

**Lifecycle**: 用户每次提交 prompt 时 fire

**职责**：
1. 读 user override mode（`~/.claude/cockpit.json`）
2. 如果 mode=off → 立即 exit 0（Cockpit 静音）
3. 如果 mode=auto → 调 Haiku judge
4. 根据 judge 结果决定是否注入 plan-first 指令
5. 写 scenario_judge log + session-state

**关键 input**（来自 stdin JSON）：
- `prompt` (用户输入文字)
- `cwd`
- `session_id`
- `transcript_path`

**关键 output**（stdout JSON）：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "[Cockpit Active] 请输出 <cockpit-plan>..."
  }
}
```
（仅 plan-worthy 时输出，trivial 时返回空）

**失败模式（Q5 = fail-silent）**：
- API key 缺失 → fallback 保守判 plan（避免漏掉重要任务）
- Haiku 调用失败/超时 → 同上
- log 写失败 → silent，不打扰主流程

### 4.2 `hooks/pre_tool_use.py`（决策守门人）

**Lifecycle**: Claude 准备调用任意 tool 前 fire（matcher 限定到 6 个 tool）

**职责**：
1. 读 session-state，看当前 scenario
2. trivial → silent allow
3. plan-worthy 时执行 β verify：检查 transcript 有无 `<cockpit-plan>` 块
4. 没有 → deny + 让 Claude 重新生成含 plan
5. 有 plan → 检查 tool 是否在 ask list
6. 在 → 返回 `permissionDecision: "ask"` + 格式化 reason

**关键 input**：
- `tool_name`
- `tool_input` (含 query/url/file_path 等)
- `transcript_path`

**关键 output**：
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask" | "deny" | "allow",
    "permissionDecisionReason": "🛂 Cockpit Decision Point — WebSearch\nAgent wants to: ..."
  }
}
```

**Reason 格式（D2）**：
```
🛂 Cockpit Decision Point — {tool_name}

Agent wants to:
  {格式化的 tool_input 关键字段}

Approve this choice? (Choose 'no' to redirect.)
```

### 4.3 `hooks/post_tool_use.py`（log 记录员）

**Lifecycle**: Tool 调用完成后 fire

**职责**：
- 写一条 `tool_call` entry 到 `.cockpit/[date].jsonl`
- schema 严格 mirror disler 字段命名

**不返回任何 decision**——纯 side-effect。

### 4.4 `hooks/stop.py`（brief 渲染员）

**Lifecycle**: Claude 完成响应（end_turn）时 fire

**职责**：
1. 读 transcript_path
2. parse 找最近的 `<cockpit-brief>` 块
3. 如果找到，框出来 render 给用户看
4. 没找到 → silent（trivial 任务不会有 brief）

**Brief 格式（D6 = 2 档自适应）**：
- Tier 1: `Done in ~Tmin. N decisions. Output: PATH`
- Tier 2: 4 字段 with `Recommend review`

### 4.5 `skills/*/SKILL.md`（文档型）

3 个 skill 都设 `disable-model-invocation: true`（Q6 = disable），意味着 Claude 不会自己 invoke 这些 skill——它们存在的目的是**给读 plugin 的人解释 Cockpit 的产品哲学**。

行为完全由 hooks 实现，不依赖 skill auto-invocation。

### 4.6 `commands/cockpit.md`

实现 `/cockpit on / off / auto` 三个 subcommand，写 `~/.claude/cockpit.json`。

v0.1 简化版：可能仅作占位，让用户手动编辑 cockpit.json。完整 slash command 实现 v0.2 完成。

---

## 5. UX Matrix（5 个用户场景）

| 场景 | UserPromptSubmit | Claude 输出 | PreToolUse 行为 | Stop |
|---|---|---|---|---|
| **A. trivial 任务**（"今天天气"）| Haiku→skip，不注入 | 直接调 tool | silent allow 全部 tool | 无 brief |
| **B. plan-worthy simple**（"读 README 总结要点"）| Haiku→plan，注入指令 | 输出 Tier 1 plan（steps+ETA）| ask 命中的 tool；其他 silent | render Tier 1 brief |
| **C. plan-worthy detailed**（"调研 lindy.ai"）| 同 B | 输出 Tier 2 plan（goal+steps+key decisions+...）| 同 B | render Tier 2 brief |
| **D. user `/cockpit off`** | 跳过 Haiku，跳过注入 | 直接调 tool | silent allow 全部 | 无 brief |
| **E. user `/cockpit on`** | 跳过 Haiku，强制注入 plan 指令 | 输出 plan（不管 Haiku 怎么想）| ask 命中的 tool | render brief |

---

## 6. Decision Log

15 个决策按 phase 分组。每条记录：**问题 / 选项 / 选择 / 理由 / 链接到产生这个决策的对话脉络**。

### Phase 1: Plan-First 主架构

#### D1 — Plan-First 实现机制
- **问题**：怎么 enforce "Claude 必须先输出 plan 再调 tool"？
- **选项**：
  - A: UserPromptSubmit 注入指令（soft enforcement）
  - B: PreToolUse 验证 plan 存在（hard enforcement）
  - C: A+B 双保险
  - D: 手动触发模式（用户 opt-in）
  - E: Skill model-invocable（Claude 自判）
- **选择**：C（最初）→ 经过 friction option ① → α/β = β 后，等价于 **A + B（无 user approval）**
- **理由**：humanism thesis 要求决策不可绕过。soft enforcement 偶尔漏判 plan；hard enforcement 通过 PreToolUse 验证保证 100%

#### D1.5 — Scenario Detection
- **问题**：怎么判断 "这个任务需要 plan-first"？
- **选项**：①关键词启发式 / ②小模型 LLM 判 / ③Lazy 触发 / ④Tool 类别 / ⑤user opt-in / ⑥Hybrid
- **选择**：**②+⑤**（LLM judge 默认 + user override commands）
- **理由**：经典 "smart default + user authority" 模式。Haiku 准确率 90%+，user override 提供 escape hatch

#### Sub-Q1 — LLM 模型
- **问题**：用什么模型做 scenario judge？
- **选项**：A Haiku / B Sonnet / C GPT-4o-mini / D Gemini Flash / E 本地 / F 启发式
- **选择**：**A Haiku 4.5**
- **理由**：Anthropic "Building Effective Agents" 推荐 Haiku 做 routing；和 Claude Code 同生态；user 已有 ANTHROPIC_API_KEY；速度（~500ms-1s）+ 成本（~$0.0001/call）合理

#### Friction Option — Plan Approval
- **问题**：scenario filter 命中 plan-worthy 后，plan 输出还需要 user approve 吗？
- **选项**：①LLM judge 替代 approval / ②Decision Markers 静默化 / ③Decision Markers 精细化 / ④Plan 自动 approve（trust 模式）
- **选择**：**①**（LLM judge 替代 plan approval）
- **理由**：Haiku 已经替代了 "是否 plan-worthy" 元决策；plan 改成 informational（不 block）；保留 Decision Markers 做事中介入；总 friction 比 plan approval + decision markers 低 33%

#### α/β — Plan Output Enforcement
- **问题**：选 ① 之后，plan 是否还要硬保证输出？
- **选项**：α 不验证（soft，~95% 可靠）/ β 验证（hard，100%）
- **选择**：**β**（PreToolUse 验证 transcript 有 plan 块）
- **理由**：humanism thesis 要求"决策不可绕过"。α 5% 漏判等于产品哲学有 5% 概率不成立；β 多 30 行代码、偶尔有 deny+retry 卡顿，但 100% 守住

### Phase 2: State / 配置

#### Sub-Q2 — State 持久化
- **问题**：user override 状态存哪？
- **选项**：A 不持久化 / B per-session / C global / D env var
- **选择**：**C global**（`~/.claude/cockpit.json`）
- **理由**：跨 session 持久（"我在 Cockpit 烦死了，关了"应该全局生效）；用户可手动编辑

#### Sub-Q3 — Slash Command 形态
- **问题**：user override 用什么 command？
- **选项**：A session-level only / B per-prompt only / C 两者都有
- **选择**：**A session-level only**（`/cockpit on/off/auto`）
- **理由**：简单直观；per-prompt override 实际意义弱（plan-first 这种行为天然是 session-级）

#### Sub-Q4 — Filter Scope
- **问题**：scenario filter（trivial vs plan-worthy）影响范围？
- **选项**：A gates 全部 Cockpit / B 只 gate plan-first，DM 永远 on / C 独立配置
- **选择**：**A gates 全部**（trivial 任务完全静音）
- **理由**：trivial 任务（"hi"、"today weather"）完全静音是用户体验底线；DM 在 trivial 任务里弹 = 烦人

### Phase 3: Decision Markers

#### D2 — Decision Marker UX
- **问题**：怎么把决策点显性化给用户？
- **选项**：A 内置 dialog / B Deny+引导 / C 自建 ANSI UI / D 通知 only / E Side channel
- **选择**：**A 内置 permission dialog**（`permissionDecision: "ask"` + 格式化 reason）
- **理由**：复用 Claude Code 现成 UI，0 工作量；reason 字段可塞富文本；C 选项的"自建 UI"实际受 TTY 限制，效果有限

#### D3 — Decision-worthy Tools
- **问题**：哪些 tool 触发 decision marker？
- **选项**：A 信息搜集类 / B 极窄（仅 web）/ C 全部 / D Risk-based / E 用户配置
- **选择**：**D Risk-based** + 具体清单：
  - ✅ ask: WebSearch | WebFetch | Task | Edit | Write | NotebookEdit
  - ❌ silent: Bash | Read | Grep | Glob | AskUserQuestion | ExitPlanMode | TodoWrite | mcp__*
- **理由**：Cockpit 介入 = "commit to a direction"（研究 commit + 写出 commit）；探索类（Read/Grep/Glob）pass through；Bash 让 Claude Code 自己 permission 系统处理（避免重叠）；mcp__* 因为 server 行为差异大，v0.1 默认不介入

### Phase 4: 产物字段

#### D4 — Plan 字段格式
- **问题**：`<cockpit-plan>` 含什么字段？
- **选项**：A 极简 3 字段 / B 标准 5 字段 / C 完整 7 字段 / D flat steps / E 自适应
- **选择**：**E 2 档自适应（Claude 自判）**
- **理由**：trivial → 不出 plan（被 filter 隔离）；plan-worthy 内部分简单 / 详细 2 档；Claude 根据任务复杂度自适应；3 档边界模糊；alternatives 字段易 hallucinate（risk）

#### D4.5 — Haiku Prompt Design
- **问题**：Haiku judge 的 prompt 怎么写？
- **选项**：Conservative / Aggressive / Balanced
- **选择**：**Conservative + 5 explicit triggers + reason logging**
  - 5 triggers: 深度研究 / 外部多次搜集 / 文件修改 / 长任务 / 多步多决策
  - "When ambiguous lean skip" 兜底
  - JSON 输出含 reason，写 log 用于 post-launch tune
- **理由**：v0.1 起步偏保守不烦人；reason logging 让 prompt 后续可数据驱动迭代

#### D6 — Brief 字段格式
- **问题**：`<cockpit-brief>` 含什么字段？
- **选项**：A 极简 / B 标准 / C 详细 / 2 档自适应
- **选择**：**2 档自适应（mirror plan 的 tier 选择）**
  - Tier 1: count + outputs + time（一行）
  - Tier 2: count + outputs + time + **recommend review**（4 字段）
- **理由**：保持产物对称（plan 简单 → brief 也简单）；recommend review 是 Tier 2 灵魂——agent 主动 flag 风险点

#### Q3/D7 — JSONL Schema
- **问题**：log 文件 entry 字段密度？
- **选项**：A 简化 5 字段 / B mirror disler / C 完整含 metadata
- **选择**：**B mirror disler**（A + session_id + tool_use_id + cockpit_decision）
- **理由**：spec.md §1 已承诺 disler 兼容；A 失去这个；C 的 alternatives 字段 hallucination risk

### Phase 5b: FM2 三件套（2026-04-29 下午添加）

#### F1 — Thinking Checkpoint
- **问题**：Agent 在 tool call 之间的"思考"对用户不可见——尤其深度研究 / 数据分析场景
- **选项**：A 每 tool call / B 仅方向变化 / C 每 N 批量 / D 自适应
- **选择**：**A 每 tool call** + 3 字段（Got / Insight / Next）+ hook 顺手写 log
- **理由**：Owner 明确说"每次调用拿到了什么/怎么思考的/下一步"——A 最直接命中；3 字段比 4 字段少废话；Insight 是 optional（无 surprise 时省）

#### F3 — Read 可见化（解法变了）
- **问题**：Read/Grep/Glob 决策原本不可见，数据分析场景缺
- **选项**：A 全 ask / B First-Read only / C cwd 边界 / D 不 ask 通过 F1 实现
- **选择**：**D 不加 ask list**——通过 F1 的 Got 字段自然实现可见性
- **理由**：Owner 说"不打扰用户，用户想停自己停"。F1 thought 块里 Got 字段已 capture "agent 读了什么"——再加 ask 是双重实现 + 烦

#### F5 — Assumption Marker
- **问题**：数据分析里 agent 隐式 assumption（"按 last-30d-orders 分 segment"）不显性
- **选项 (Q1)**：A plan 一次声明 / B 独立 block 任意时刻 / C A+B 双轨
- **选项 (Q2)**：4 字段 / 3 字段 / 2 字段
- **选项 (Q3)**：every assumption / only non-trivial
- **选择**：**Q1=C 双轨 + Q2=B 3 字段（Assuming/Why/Impact）+ Q3=B only non-trivial**
- **理由**：数据分析最常见 pattern 是看到数据后才意识到 assumption（mid-execution 也要 declare）；3 字段够 Impact 字段对用户决定要不要 push back 关键；non-trivial 防止 agent 凑废话（"假设 utf-8 编码"这种）

### Phase 5d: Runtime 行为 detail（2026-04-29 晚 add）

#### R1 — Haiku failure fallback
- **问题**：Haiku 调用失败（网络断 / API key 失效 / timeout）时怎么办？
- **选项**：A Conservative（默认判 plan-worthy）/ B Permissive（默认判 trivial）
- **选择**：**A Conservative**
- **理由**：fail-safe——safety over speed；user 看到"咦今天每次都触发 plan"会去 check API key；漏掉 trivial 影响小，漏掉 plan-worthy 影响大

#### R2 — `/cockpit` slash command v0.1 实现度
- **问题**：v0.1 是占位还是 minimal 还是 full？
- **选项**：A Placeholder / B Minimal（on/off/auto 三命令能用）/ C Full（含 status）
- **选择**：**B Minimal**
- **理由**：A 让 user 手动编辑文件不专业；C 来不及；B 是 v0.1 user-facing 完整体验的最小 viable 实现

#### R3 — Day 7 Demo task 选择
- **状态**：**暂缓**——demo 任务应该 informed by Day 4-7 dogfood 数据，不预定
- **候选**：A wechat-radar 数据分析 / B 调研 AI 公司 / C 写 PRD
- **决策时机**：Day 7 dogfood 完后再选

### Phase 5c: Skill / 失败模式

#### Q4/D5 — `<cockpit-decision>` 块
- **问题**：Claude 是否需要主动 declare 决策块？
- **选项**：drop / optional / mandatory
- **选择**：**drop**
- **理由**：选了 D2-A 之后，hook 直接从 `tool_input` 提取参数生成 reason，不需要 Claude 多输出；保持 Claude 输出干净；避免 token 浪费

#### Q5/D8 — Hook 失败模式
- **问题**：hook 报错时怎么处理？
- **选项**：fail-silent（exit 0 不报错给 Claude）/ fail-loud（exit 1 报错）
- **选择**：**fail-silent**
- **理由**：hook 不能成为 Claude 的 single point of failure；用户可看 stderr debug；core 行为优先于 Cockpit 增强行为

#### Q6/D9 — Skill Model-invocable
- **问题**：3 个 SKILL.md 是否允许 Claude 自己 invoke？
- **选项**：disable-model-invocation: true / false
- **选择**：**disable**
- **理由**：Cockpit 行为应该 100% hook 决定；Claude 自由 invoke skill 会和 hook 行为打架（如 trivial 任务被 Claude 自己 trigger plan-first）；用户已有 `/cockpit on` 作为强制 plan 的 escape hatch

---

## 7. Open Questions for v0.2+

下面问题在 v0.1 design phase **不解决**，留给 v0.2+ 处理：

### 7.1 Override 后的 agent resume
- **问题**：用户 deny 一个 tool call 后，agent 怎么 resume？
- **v0.1**：直接 abort，agent 重试
- **v0.2 idea**：让 agent 接受 user 的 redirect 输入（"换个 query 用 X"），然后局部 re-run 那一步

### 7.2 `/cockpit` slash command 完整实现
- **v0.1**：占位为主，用户可能要手动编辑 `~/.claude/cockpit.json`
- **v0.2**：完整实现 on/off/auto + status（看当前模式 + 最近 5 次 Haiku judge 历史）+ verbose/silent

### 7.3 Decision pattern learning
- **v0.2 idea**："你过去 30 次里 override 了 7 次同类 decision，要不要加 default rule 自动 deny 这种？"
- 需要的数据：JSONL log 里 user_action + agent_choice 对（已经在 Q3=B 里 capture 了）

### 7.4 Web dashboard 集成
- **v0.1**：JSONL log 兼容 disler，用户可手动 import
- **v0.2 idea**：直接把 log 实时 push 到 disler 的 Bun server endpoint

### 7.5 跨 AI tool 支持
- **v0.1**：仅 Claude Code
- **v0.2 idea**：Cursor / Devin / OpenAI Agents SDK adapter（每个有自己的 hook 机制）

### 7.6 Multi-agent orchestration
- **v0.1**：Task subagent 仅在 ask list 里（每次 spawn 都弹 dialog）
- **v0.2 idea**：subagent 内部行为也 Cockpit 化（递归 oversight）

### 7.7 Haiku judge tune
- **v0.1**：起步 conservative + 5 trigger
- **v0.2 idea**：基于 log 里 scenario_judge 的 reason 分布，迭代 prompt（哪些 trigger 误判率高？哪些场景 Haiku 漏判？）

### 7.8 Mid-task check-in（FM2 P1）
- **问题**：长任务跑到一半，用户没机会"等等，方向偏了"打断
- **v0.2 idea**：每 5 个 tool call 后 agent 主动 pause "做了 X 发现 Y，继续按原 plan 还是调整？"

### 7.9 Confidence scoring（FM2 P1）
- **v0.2 idea**：agent 自评每步 high/medium/low confidence，写进 thought 块或 brief

### 7.10 Reverse trace（FM3 P2）
- **v0.2 idea**：log 多一层 causality 字段——"这个输出来自决策 X + 决策 Y + assumption Z"
- 让用户从输出反推决策链

### 7.11 Override redirect（v0.1 局限性）
- **v0.1 限制**：用户 deny tool call 后 agent 重试/abort，**没法让 user 直接 redirect**（"换个 query 用 X"）
- **v0.2 idea**：deny dialog 加 "redirect" 选项，让 user 输入修改后的参数，agent 用新参数 retry

---

## 附录：Architecture 演进 timeline

| 时间 | 事件 |
|---|---|
| 2026-04-29 12:00 | spec.md v0.1 draft（Cathy approved） |
| 2026-04-29 13:00 | 用户证据收集（user-research.md） |
| 2026-04-29 14:00 | unilateral ship 13 个文件 → 被 Cathy archive，重新 design |
| 2026-04-29 15:00-17:00 | 15 个决策逐个 close（D1 → Q7） |
| 2026-04-29 17:30 | architecture.md v0.1 sealed（本文件） |
| 2026-04-30+ | Day 3 implementation（按本文件 reference 写代码）|
