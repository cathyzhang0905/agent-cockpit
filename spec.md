# Agent Cockpit — Spec v0.1

**Status**: Draft v0.1
**Date**: 2026-04-29
**Owner**: Cathy Zhang ([@cathyzhang0905](https://github.com/cathyzhang0905))
**Target ship**: 2026-05-06（7 天后）

---

## 1. Positioning

**Agent Cockpit 是 Claude Code agent 的"主动监督层"（active oversight layer）。**

现有的观察工具（[disler/claude-code-hooks-multi-agent-observability](https://github.com/disler/claude-code-hooks-multi-agent-observability)、[simple10/agents-observe](https://github.com/simple10/agents-observe)）擅长**观察**——记录 agent 做了什么。**Cockpit 是它们之上的一层：它强制 agent 在行动前先声明计划，把每一个微决策 surface 给人审阅，在关键选择点暂停让你 override（推翻 / 修改）。**

围绕一个核心原则设计：**人的决策步骤必须显性化、不可绕过**。这是"以人为本"（humanism）哲学在产品层的具体实现。

Cockpit 和现有 observability 工具是**互补关系**——Cockpit 的 decision log（JSONL 格式）刻意设计成兼容现有 event schema。**两者搭配使用**：Cockpit 负责事中主动控制，disler / simple10 这类 dashboard 负责事后回顾分析。

---

## 2. 我们要解决的问题

**核心问题**：当你把任务交给 AI agent 时，你恰好在最需要参与的时刻失去了对它决策过程的访问。

来自一位 deep AI user 的真实表达（2026-04-29）：

> "我真的自动化的让 agent 跑的时候 我不知道他们到底在干嘛 这个结果能不能符合我的预期 是不是要让我重新改"

这种"不知道在干嘛"的感觉来自 3 种具体的失败模式：

1. **执行前盲区（Pre-execution blindness）**：你按下 Enter，不知道 agent 准备做什么——直到它已经在做了
2. **执行中不可见（Mid-execution invisibility）**：agent 每个任务做 5-50 个 micro-decision（选哪个 tool / 哪个 source / 什么 assumption / 怎么 slice 数据），全部隐形。**每一个都可能默默改变最终输出**
3. **执行后无法归因（Post-execution attribution gap）**：输出出问题时，你无法追溯到是哪个决策导致的

### 为什么现有工具没解决这个

| 工具类型 | 它做什么 | 它不做什么 |
|---|---|---|
| Observability dashboard（disler、simple10）| 记录所有发生过的事 | 不 surface 即将发生的事 |
| Permission 系统（Claude Code 内置）| block 危险命令（rm -rf 等）| 不让你 redirect 正常但错误的决策 |
| Audit 工具（melodic）| 查询历史事件 | 不在 real-time 介入 |

**缺失的是一层："active oversight"**——不是"看发生了什么"，不是"block 危险的"，而是 **"在 agent 跑的时候 stay in the decision loop"**。

### Cockpit 对应这 3 个失败模式的直接 mapping

| 失败模式 | Cockpit 解法 |
|---|---|
| ① 执行前盲区 | **Plan-First** —— agent 必须先声明计划，你 approve 才执行 |
| ② 执行中不可见 | **Decision Markers** —— 每个 micro-decision surface 给你审阅 |
| ③ 执行后无法归因 | **Brief + Decision Log** —— 决策汇总 + JSONL 持久化 |

### 目标用户

**Deep AI users**——把 agent 用在真实工作（research / 数据分析 / 写作 / 编码）的人。他们在意输出**正确性**多于速度。**他们不想让 AI 替代决策，他们想 stay in the decision loop 但不成为 bottleneck**。

### 成功的样子

装上 Cockpit 后，用户体验发生根本性转变——从 "我给 agent 一个 prompt 然后等结果" 转为 "在 agent 推理过程中我参与了关键时刻"。任务可能多花 10-30% 时间，但**输出质量提升**，因为错误在传播前被抓住。

---

## 3. Anti-goals（v0.1 显式不做的事）

| 不做 | 为什么 |
|---|---|
| Web dashboard / 浏览器 UI | disler / simple10 已经做得很好，重复造轮子 |
| Multi-agent hierarchy 可视化 | simple10 已经做得很好 |
| Cost tracking | 不在 oversight scope 里 |
| 跨 AI tool 支持（Cursor / Devin / 其他）| v0.1 只 Claude Code，专注 |
| 多用户 / 团队共享 | 个人 dev 工具 v0.1 ≠ 协作平台 |
| 智能默认规则学习 | 需要先有 decision log 数据，v0.2+ |
| Override 后的局部 re-run | v0.1 直接 abort，v0.2 加 |

---

## 4. Core 3 Functions（v0.1 必做）

### 4.1 Plan-First

**触发**：任务被 Haiku judge 判定为 plan-worthy（详见 architecture.md §1 + §6 D1.5/D4.5）
**行为**：agent 输出 `<cockpit-plan>` block，**2 档自适应**——
- Tier 1（simple task）：steps + ETA
- Tier 2（detailed task）：goal + steps + ETA + key decisions + (optional) assumptions
**Plan 是 informational**，不需要 user 显式 approve；user 通过 `/cockpit on/off/auto` 控制整体行为
**实现**：
- `UserPromptSubmit` hook：读 user override → Haiku judge → 条件注入指令
- `PreToolUse` hook：β verification 验证 transcript 有 `<cockpit-plan>` 块；没有则 deny + Claude 重试
- detail 见 [architecture.md](architecture.md) §4.1 + §4.2

**用户看到的格式**：

```
╭─ 🛂 Cockpit: Plan Review ─────────────────────╮
│ Agent 准备做：                                 │
│   [1] Load nupay_q2_data.csv                 │
│   [2] Slice by: user_segment × payment       │
│   [3] Compute 4-step funnel                  │
│   [4] Render bar chart                       │
│                                              │
│ ETA: ~2 min                                  │
│ 关键决策点: [2] [3]                            │
│                                              │
│ [a]pprove  [m]odify  [c]ancel                │
╰──────────────────────────────────────────────╯
```

### 4.2 Decision Markers

**触发**：plan-worthy 任务里 agent 准备调用 decision-worthy tool 时
**v0.1 scope**：6 个 decision-worthy tool 拦截：
- ✅ ask: **WebSearch | WebFetch | Task | Edit | Write | NotebookEdit**
- ❌ silent: Read | Grep | Glob | Bash | AskUserQuestion | ExitPlanMode | TodoWrite | mcp__*

**行为**：`PreToolUse` hook 直接从 `tool_input` 提取关键参数（query/url/file_path 等），返回 `permissionDecision: "ask"` + 格式化 reason → Claude Code 内置权限 dialog 弹出 → 用户 approve / deny
**用户动作**：dialog 上 approve / deny
**实现**：`PreToolUse` hook + Claude Code 内置 permission 系统（无自建 UI）；详见 [architecture.md](architecture.md) §4.2 + D2/D3

**用户看到的格式**：

```
[2] 🔵 DECISION: Slicing by user_segment × payment
    └─ Why: 默认 config 推断
    └─ Alternative: by country / by month
    └─ [Enter 继续 / o override]
```

### 4.3 Brief

**触发**：`Stop` hook（agent 完成任务）
**行为**：agent 输出 `<cockpit-brief>` block，**2 档自适应** mirror plan tier——
- Tier 1: count + outputs + time（一行）
- Tier 2: count + outputs + time + **recommend review**（agent 主动 flag 风险点）
**实现**：`Stop` hook 解析 brief 并 render；详见 [architecture.md](architecture.md) §4.4 + D6

### 4.4 Thinking Checkpoint（NEW，2026-04-29 下午加入）

**触发**：plan-worthy 任务里每个 tool call 之后
**行为**：agent 输出 `<cockpit-thought>` block——
- **Got**：tool 返回的关键信息（一句话总结）
- **Insight**：optional——如果 finding 改变了 mental model
- **Next**：下一步 + 简短 why
**Thinking checkpoint informational，不 block 执行**——agent 输出后立即进下一个 tool call
**实现**：skill 教 Claude 输出格式；`PostToolUse` hook 顺手 parse + 写 log；详见 [architecture.md](architecture.md) §4 + F1

**为什么重要**：直接命中 spec §2 FM2 痛点——"执行中 agent 的思考不可见"。这是把 agent 推理过程从黑盒转白盒的核心机制。

### 4.5 Assumption Marker（NEW，2026-04-29 下午加入）

**触发**：双轨——
1. plan 阶段：声明已知 assumptions（写进 plan 的 assumptions 字段）
2. mid-execution：发现新 assumption 时单独输出 `<cockpit-assumption>` block
**行为**：agent 输出 3 字段——
- **Assuming**：假设内容
- **Why**：为什么做这个假设
- **Impact**：假设错了会怎样
**Frequency**：only non-trivial assumptions（agent 自判，影响结论的才声明）
**实现**：skill 教 Claude 输出；详见 [architecture.md](architecture.md) §4 + F5

**为什么重要**：数据分析场景里 agent 大量隐式假设（"按 last-30d-orders 分 user segment"）影响结论但不可见——assumption marker 把这层显性化。

**用户看到的格式**：

```
╭─ 🛂 Cockpit: Brief ──────────────────────────╮
│ Done in 1m 47s                               │
│ Made 4 micro-decisions                       │
│ ⚠️ 1 你可能想 review:                          │
│   [3] Funnel 定义直接影响结论                   │
│                                              │
│ Output: ./q2_nupay.png                       │
│ Decision log: ./.cockpit/2026-04-29.jsonl    │
╰──────────────────────────────────────────────╯
```

---

## 5. Stretch Features（有时间加，没时间不强求）

- **ETA estimator** — 基于 plan 步骤数 + 平均 tool 时间估算
- **Productive idle suggestions** — agent 长时间跑时建议非污染主线的 fill task（解决你 4 痛中的痛 2 一部分）
- **Diff view post-execution** — 显示"做了什么 / 没做 / 考虑过的 alternative"

---

## 6. Architecture

### 6.1 Plugin structure（2026-04-29 verified against [Claude Code Plugin docs](https://code.claude.com/docs/en/plugins)）

```
agent-cockpit/
├── .claude-plugin/
│   └── plugin.json               # plugin metadata（必须在子文件夹）
├── hooks/
│   ├── hooks.json                # hook 注册配置（事件 → 脚本 mapping）
│   ├── user_prompt_submit.py     # 注入 plan-first 指令
│   ├── pre_tool_use.py           # 拦截 decision-worthy tool call
│   ├── post_tool_use.py          # 写 JSONL log
│   └── stop.py                   # render brief
├── skills/                       # 必须每个 skill 是子文件夹 + SKILL.md
│   ├── plan-first/SKILL.md       # 教 Claude 输出 plan 格式
│   ├── decision-marker/SKILL.md  # 教 Claude declare decision 格式
│   └── brief/SKILL.md            # 教 Claude 输出 brief 格式
├── commands/
│   └── cockpit.md                # /cockpit on/off/config/silent/verbose
├── README.md
└── LICENSE                       # MIT
```

### 6.2 Hook 用途（基于 verified API spec）

| Hook | 用途 | 关键 API |
|---|---|---|
| `UserPromptSubmit` | (1) 读 `~/.claude/cockpit.json` user override (2) 调 Haiku judge 分类 plan-worthy/trivial (3) 条件注入 plan-first 指令 (4) 写 scenario_judge log | output `additionalContext` 字符串 → Claude 看到 |
| `PreToolUse` | (1) 读 session-state 看 scenario (2) plan-worthy 时 β-verify transcript 有 `<cockpit-plan>` (3) 在 ask list 的 tool 触发 dialog | output `permissionDecision: "ask"\|"deny"\|"allow"` + `permissionDecisionReason` → 触发 Claude Code 内置权限对话框（带自定义 reason 文字） |
| `PostToolUse` | 写 tool_call entry 到 `.cockpit/[date].jsonl` | 不返回 decision，纯 side-effect |
| `Stop` | 仅 plan-worthy: parse `<cockpit-brief>` 并 render | output `additionalContext` 显示 brief 给 Claude（出现在最终输出附近）|

**关键 design 决策**：用 Claude Code 内置的 `permissionDecision: "ask"` 机制弹决策对话框，**不需要 build 自定义 terminal UI**——这是把工程复杂度降到最低的核心选择。

**关键 architecture flow** 详见 [architecture.md](architecture.md) §1 end-to-end flow 图。

### 6.3 JSONL schema（兼容 disler 风格）

```jsonc
{
  "timestamp": "2026-04-29T10:00:00Z",
  "session_id": "uuid",
  "event_type": "decision",       // 与 disler event_type 兼容
  "decision_type": "tool_selection" | "source_selection" | "assumption",
  "agent_choice": "WebSearch",
  "alternatives": ["WebFetch", "Read"],
  "rationale": "query 模糊需要先发现 URL",
  "user_action": "approved" | "overridden" | "skipped",
  "user_choice": null              // 如果 overridden 写用户的选择
}
```

PostToolUse 也写 entry，event_type 为 "tool_call"，schema 完全 mirror disler 的格式，让用户能把 Cockpit log 直接灌进 disler dashboard。

---

## 7. I/O 边界

**Input**：任何使用 tool 的 Claude Code 任务

**Output**：
- 终端：结构化 Plan / Decision Markers / Brief
- 文件：`./.cockpit/[date].jsonl` decision log

**Out of scope**：
- 无 tool call 的纯对话任务（Cockpit 不介入，因为没决策点）
- Claude Code 之外的 AI tool（Cursor / Devin 等 v0.1 不支持）

---

## 8. Eval design（3 维度）

### Eval 1: Decision Coverage

**问题**：agent 实际做的 micro-decision 中，多少被 Cockpit surface 给用户？
**方法**：dogfood 1 个完整任务，事后 review JSONL log，对比 agent 实际 tool call 序列，统计 missed decisions
**Target v0.1**：≥80% coverage on tool / source / assumption 三类
**Failure mode**：agent 跳过 declare decision → skill prompt 不够强 → 改 skill

### Eval 2: Override Rate

**问题**：surface 出来的 decision 中，用户 override 的比例
**方法**：dogfood 5+ 个 task，统计 approval/override ratio
**Target v0.1**：10-30% override
- 太低（<5%）= 我们 surface 了 trivial 的（noise）
- 太高（>50%）= agent 默认选择策略错（or surface 了不该 surface 的）

### Eval 3: Time Overhead

**问题**：装了 Cockpit 后完成相同任务多花多少时间？
**方法**：跑 5 个相似任务，A/B 比较有/无 Cockpit 的总时间
**Target v0.1**：<30% overhead
- review 决策时间是值的，但不能毁 productivity

---

## 9. Dogfood task candidates（Day 4 跑）

### Primary（demo 主场景）：wechat-radar 数据分析

**任务描述**：用 Claude Code agent 分析 wechat-radar 过去 30 天的公众号信号数据，回答 "哪些公众号信号质量在下降"

**为什么是 primary**：
- 数据是 owner 自己的，dogfood 100% 真实
- 决策点丰富（4 维评分选哪几个 / 时间切片 / "下降"定义 / 视觉化方式）
- 数据分析场景在 demo 视频里 visual 冲击力强

### Backup A：深度研究

**任务描述**：用 Claude Code 调研一家 AI 公司（比如 Lindy）

**为什么是 backup**：决策点丰富但更 generic；如果 primary 抓 bug 多就备用

### Backup B：写长文档

**任务描述**：用 Claude Code 写一份长文档（如 product brief、技术方案、深度分析报告）

**为什么是 backup**：写作类任务决策点偏少（更确定性），Cockpit 价值不如数据分析场景显著；如果 primary 跑不通就备用

---

## 10. 7-day build plan

| Day | 任务 | 输出 |
|---|---|---|
| Day 1 (今天) | spec.md（**当前**）| ✅ 此文件 |
| Day 2 | architecture 详细 + Claude Code hook API verify | architecture.md |
| Day 3 | Plan-First + Live Narration 实现 | runnable v0.1 |
| Day 4 | Decision Markers 实现 + dogfood | working dogfood |
| Day 5 | iterate（≤3 bug fix）+ generalization test | v0.2-ish |
| Day 6 | Demo video 录制 | demo.mp4 |
| Day 7 | GitHub release + 公众号文章 draft | github 仓库 + draft |

---

## 11. Attribution & References

- **[disler/claude-code-hooks-multi-agent-observability](https://github.com/disler/claude-code-hooks-multi-agent-observability)** — hook-based 12-event tracking 思路 baseline
- **[simple10/agents-observe](https://github.com/simple10/agents-observe)** — multi-agent hierarchy visualization 启发
- **Microsoft HAX Toolkit** (Saleema Amershi) — 18 Human-AI Interaction Guidelines（[microsoft.com/haxtoolkit](https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/)）
- **Mixed-Initiative Interaction** 学术框架 — 设计 pattern 来源
- **Anthropic "Building Effective Agents"** — agent system design 通用 reference framework（prompt chaining、evaluator-optimizer、HITL pattern）

---

## 12. Open Questions & Risks

| 风险 | 对冲 |
|---|---|
| Day 3 build 卡住（hook API 文档不完整）| Day 2 architecture 阶段必须 verify hook spec；备选 Python wrapper 替代 |
| Decision granularity 难定义 | v0.1 hard-code 3 类决策；v0.2 让用户配置 |
| Override 后 agent resume 难 | v0.1 直接 abort；v0.2 加局部 re-run |
| Skill prompt 不够强，agent 不 declare decision | Eval 1 设计就为发现这个；多轮迭代 prompt |
| Demo 录制 Day 6 突发问题 | Day 5 dry-run 1 次 |

---

## 13. v0.2+ Roadmap（不在 1 周 scope）

- Decision pattern 学习：基于 log "你 override 了 7 次同类型决策，要不要 default rule"
- Web dashboard 集成（或直接 export 到 disler）
- 跨 AI tool 支持（Cursor / Devin）
- 团队共享 / 多用户
- Override 后局部 re-run

---

## 14. Decision Log of This Spec（meta — 记录 spec 本身的演化）

- **2026-04-29 第 1 次 pivot**：Owner push back "为什么是 skill 而不是 superpower 这种插件" → positioning 从 "Claude Code skill" 修正为 **"Claude Code Plugin"**（hooks + skills + commands 三件套）
- **2026-04-29 第 2 次 pivot**：Owner 提出"这个场景不只是研究，也包括用户研究 / 写文档 / 数据分析" → product scope 从 "research helper" 扩展为 **"general agent observability layer"**（hook 在 universal tool-call lifecycle）
- **2026-04-29 第 3 次 pivot**：调研 GitHub 发现 disler / simple10 已是 1.4k / 510 stars 项目 → positioning 从 "observability" pivot 为 **"active oversight"**（避免和 incumbent 重叠 + 真实差异化）
- **2026-04-29 第 4 次 pivot**：Owner 升级 humanism thesis："AI 必须在产品架构上把'人决策'这一步显性化、不可绕过" → core principle sharpened（B-auto vs B-scaffold 区分）
- **2026-04-29 第 5 次 pivot**：Owner archive 之前 unilateral ship 的 13 个文件，要求 design 决策从零讨论 → 进入 collaborative design phase，15 个核心决策逐个 close。**implementation-level decisions 全部记录在 [architecture.md](architecture.md) §6 Decision Log**（spec 这层只记 spec 演化）
- **2026-04-29 第 6 次 pivot**：Owner self-check "v0.1 解决了多少 spec §2 失败模式" → 发现 FM2（mid-execution invisibility）解决度仅 50%，但**正是 owner 真实核心痛点**。Scope 扩展加 3 个 FM2 features：**F1 Thinking Checkpoint + F3 Read 可见性（通过 F1 实现）+ F5 Assumption Marker**。Ship 时间 7→9 天。FM2 解决度从 50% → ~85%。详见 [v01-completion-analysis.md](v01-completion-analysis.md) + [architecture.md](architecture.md) §6 F1/F3/F5

---

## 15. 6 项核心认知（owner 已确认对齐）

1. ✅ Cockpit 是 active oversight，不是 observability
2. ✅ Core 3 functions：Plan-First + Decision Markers + Pause/Override
3. ✅ Humanism thesis 产品化：决策步骤显性 + 不可绕过
4. ✅ 与 incumbents 互补（JSONL schema 兼容）
5. ✅ Anti-goals 明确（不做 dashboard / 不和 disler 比颜值）
6. ✅ 形态是 Claude Code Plugin（不是单纯 skill）
