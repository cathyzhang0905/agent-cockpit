# Agent Cockpit — v0.1 Completion Analysis

**Date**: 2026-04-29
**Owner**: Cathy Zhang
**Purpose**: 诚实评估 v0.1 design 对 spec.md §2 三个 failure mode 的解决度，flag 出未解决的 gap，作为 v0.2 路线图依据。

---

## 三个 failure mode 解决度速查

### v0.1 初版（2026-04-29 上午）

| Failure Mode | 初版解决度 | 真实痛感最近的 |
|---|---|---|
| FM1 — Pre-execution blindness（执行前盲区）| ~85% | ⚠️ 中 |
| **FM2 — Mid-execution invisibility（执行中不可见）** | **~50%** | **🔥 Owner 真实核心痛点** |
| FM3 — Post-execution attribution gap（执行后无法归因）| ~75% | ⚠️ 中 |
| **加权综合（按 spec 权重）** | **~70%** | |

### v0.1 scope 扩展后（2026-04-29 下午）

加入 F1 Thinking Checkpoint + F3（通过 F1 实现）+ F5 Assumption Marker 之后：

| Failure Mode | 扩展后解决度 | 改变 |
|---|---|---|
| FM1 — Pre-execution blindness | ~85%（同前）| F1/F3/F5 不直接影响 FM1 |
| **FM2 — Mid-execution invisibility** | **~85%** | 🚀 **+35%**——F1 让思考过程白盒；F3 通过 F1 让 read 可见；F5 让 assumption 显性 |
| FM3 — Post-execution attribution gap | ~80%（+5%）| F1 thought 写 log，F5 assumption 写 log，反向 trace 数据更全 |
| **加权综合** | **~83%** | **+13% absolute** |

⚠️ **关键反思**：初版 design 把精力放在 FM1（Plan-First）和 FM3（Brief），FM2 反而最薄。Owner 在 architecture.md decision phase 收尾时 self-check 发现 misallocation，立即扩展 scope 加 3 个 FM2 features 把 FM2 从 50% → 85%。**这种"design phase 后 self-check + 不固执于已有方案"的纪律本身是 PM 顶级信号**。

---

## FM1 — Pre-execution blindness 详细分解

> Spec promise: "用户按下 Enter，不知道 agent 准备做什么——直到它已经在做了"

### ✅ 已解决（85%）

| 解决能力 | v0.1 实现 |
|---|---|
| 用户在 first tool call 前能看到 agent 的步骤 | UserPromptSubmit hook 注入 plan-first 指令；β verification 在 PreToolUse 兜底强制输出 |
| 步骤含工具说明 + ETA + 关键决策点 | `<cockpit-plan>` 2 档自适应 (Tier 1 simple / Tier 2 detailed) |
| trivial 任务不打扰 | Haiku judge 过滤掉 trivial，不出 plan |

### ❌ 未解决（15%）

| 缺失能力 | 影响 | 待 v0.2 |
|---|---|---|
| Plan informational 不强制 user approve | 用户不仔细读 plan 也能让 agent 跑 → 仅"看见"不"控制" | 加 mid-execution checkpoint（FM2 那边补） |
| Haiku 判 trivial 误判时仍黑盒 | 实际复杂任务被判 skip → 用户彻底无 plan | 加 fallback: PreToolUse 计数 tool call > 3 时强制 surface 之前漏掉的 plan |
| Plan 一旦输出后 agent 改方向不通知 | 中途 pivot 不可见 | 这其实是 FM2 问题，不是 FM1 |

---

## FM2 — Mid-execution invisibility 详细分解（核心痛点）

> Spec promise: "agent 每个任务做 5-50 个 micro-decision（选哪个 tool / 哪个 source / 什么 assumption / 怎么 slice 数据），全部隐形"

### ✅ 已解决（50%）

| 解决能力 | v0.1 实现 |
|---|---|
| 6 个 ask-listed tool 的调用前会弹 dialog | PreToolUse hook → permissionDecision: "ask" |
| 用户能看到 query / URL / file_path 等 tool input 关键参数 | hook 直接从 `tool_input` 提取并 format 进 reason |
| 用户可以 approve / deny | Claude Code 内置 dialog 处理 |

### ❌ 未解决（50%）—— 这才是 owner 真实痛点核心

| 缺失能力 | 影响 | 严重度 |
|---|---|---|
| **Read / Grep / Glob 决策不可见** | 用户不知道 agent 选哪个文件读、为什么读这个不读那个、用什么 grep pattern | 🔥 高（数据分析 / 深度研究高频） |
| **Bash 命令决策不可见** | 跑了什么 shell 命令、为什么这个组合，Cockpit 不介入 | ⚠️ 中（CC 默认 permission 部分覆盖） |
| **Assumption 不显性化** | Agent 在数据分析里做的隐式假设（"按 last-30d-orders 分 user segment"）只有当它写进 plan 时才能看到，**纯 in-tool 的 assumption 不可见** | 🔥 高（spec §4.2 原本承诺过 "Assumption marker"） |
| **Tool call 之间的"思考转折"不结构化** | Agent 看了 source A 之后决定下一步，这个推理链埋在 Claude 散文里，**没有结构化 surface** | 🔥 高（owner 明确 surface 这条） |
| **Plan 中途 pivot 不通知** | 初始 plan 是"先 search 再 fetch"，跑了 search 之后决定改成"先 fetch 再 search"，用户看不到 plan delta | 🔥 高（深度研究典型模式） |
| **Mid-task check-in 不存在** | 长任务（10+ tool call）跑到一半，用户没机会"等等，你方向偏了"打断 | ⚠️ 中（深度研究/数据分析里频繁） |
| **Confidence / 不确定性不暴露** | Agent 用一个 source 一个 query 时其实有 confidence 高低，**用户看不到 agent 自己有没有觉得这步不太靠谱** | ⚠️ 中-高 |

### Owner 原话定位（2026-04-29）

> "我其实核心想要解决 failure mode 2 的问题 就是执行过程 agent的思考不可见 然后不知道他打算怎么做 是不是我想要的 和我match的 尤其是在进行深度调研的时候以及数据分析啥的"

**关键词**：思考不可见 / 打算怎么做 / 是不是我想要的 / match / 深度调研 / 数据分析

---

## FM3 — Post-execution attribution gap 详细分解

> Spec promise: "输出出问题时，你无法追溯到是哪个决策导致的"

### ✅ 已解决（75%）

| 解决能力 | v0.1 实现 |
|---|---|
| 任务结束有 brief 主动 flag 风险点 | Stop hook parse `<cockpit-brief>` + render |
| Brief 含 "Recommend review" 字段 | Tier 2 brief 4 字段含此 |
| JSONL log 含每个 tool call 的 input + output_preview + 决策 metadata | PostToolUse hook + Q3=B mirror disler |

### ❌ 未解决（25%）

| 缺失能力 | 影响 | 待 v0.2 |
|---|---|---|
| Read / Grep / Glob 调用 log 没 decision metadata | 无法回查"我读错了哪个文件" | 7.x 加 PreToolUse 也介入 read 类 + 写 metadata |
| Trivial 任务无 brief | 简单任务出问题没复盘 | 7.x trivial 任务也出极简 brief（仅 outputs） |
| 没有"reverse trace"（输出 → 决策因果链） | 用户要自己翻 log 拼时间线 | 7.x 加 causality 字段 |

---

## v0.2 优先级建议（按 owner 真实痛点排序）

按 owner 把 FM2 列为核心痛点重新 prioritize：

### 🔥 P0（v0.1.5 必须做）—— 关 FM2 的最大 gap

1. **Tool-call 之间的"thinking checkpoint"**
   - 让 agent 在每个 tool call 后输出 `<cockpit-thought>` 块
   - 格式：`{found: ..., implication: ..., next_step: ..., why: ...}`
   - 让用户在 mid-execution 看到 agent 推理链

2. **Plan delta tracking**
   - Plan 在执行中会变（agent 中途调整方向）
   - 每次 plan 变化时 surface delta 给用户

3. **Read 决策可见化**
   - 加 Read 到 ask list（或 lazy: Read 第一次某文件时 ask）
   - 数据分析场景至少 50% 价值在这里

### ⚠️ P1（v0.2 重要）

4. **Assumption marker 真正实现**（spec §4.2 承诺过）
5. **Mid-task check-in**（5+ tool call 后强制 pause）
6. **Confidence scoring**（agent 自评每步不确定度）

### 🟢 P2（v0.3 锦上添花）

7. Reverse trace（输出 → 决策因果链）
8. Trivial brief（极简版）
9. Bash 决策 context（基于命令字符串启发式判断）

---

## 给 owner 的诚实建议

### 接下来 3 个选择：

**Option A：v0.1 按现 design ship，v0.1.5 立即跟进 FM2 P0**
- 7-day plan 不变；ship 后 1-2 周内做 v0.1.5
- 优点：保持节奏；公众号文章可以 honestly 说"v0.1 解决 70%，路线图清晰"
- 缺点：v0.1 给人初印象偏弱（FM2 体感不强）

**Option B：v0.1 scope 扩展，把 P0 的 thinking checkpoint 加进来**
- 推迟 ship 1-2 天
- 优点：v0.1 直接命中 owner 真实痛点；产品体感更完整
- 缺点：scope creep；dogfood 时间被挤压

**Option C：spec.md §2 改写，把 FM2 缩成 v0.1 真正解决的部分**
- 改 promise 让 spec 和 delivery 100% 对齐
- 优点：诚实
- 缺点：产品听起来不那么 ambitious；隐藏了真实路线图野心

---

## 这份文档怎么用

- **dogfood 阶段**：Day 4 dogfood 失败 case 对照本文件的 "未解决 gap"——确认是否落在已知 gap 里
- **GitHub release**：README 里"v0.1 解决度"段落引用本文件的 70% + P0 路线图
- **公众号文章**：dark-honesty 角度——"v0.1 ≠ 100%，这是诚实路线图"
- **interview**：被问"你做了多少"时，引用本文件的解决度 + gap，比"我做完了一个产品"更可信
