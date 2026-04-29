# Agent Cockpit — User Research

**Status**: v0.1
**Date**: 2026-04-29
**Purpose**: 验证 Cockpit 解决的痛点是 AI builder community 的共识级 frustration，不是 owner 个人 idiosyncratic pain。
**Use cases**: README hook / 公众号文章 / Demo 视频开头 quote / 投资 pitch / interview 论据

---

## Methodology

### Sources searched
- **English**: Hacker News (full thread fetches with comment text), Reddit, builder blogs (HyperDev / DEV Community / Implicator / Marmelab / Indie Hackers / O'Reilly)
- **Chinese**: V2EX 全文 fetch（comment 级粒度）, 知乎 / 即刻 search 索引

### Limitations
- ❌ **X / Twitter raw posts**: search index 差，未能直接 retrieve 原帖；**待后续单独研究 X 数据获取方式**（可能需 X API 或 scraping）
- ❌ **Discord communities**: 不可公开搜索
- ⚠️ **Reddit subreddit-specific search 命中率低**：Reddit 索引在 Google 上质量差，部分 subreddit thread 拿不到
- ✅ **HN full thread comments**：可 fetch，质量最高
- ✅ **V2EX 中文社区**：可 fetch，原话保留完整

---

## 1. 高强度 frustration quotes — English / Hacker News

### Source A: ["Claude CLI deleted my home directory and wiped my Mac"](https://news.ycombinator.com/item?id=46268222)
**HN metrics**: 255 points / 216 comments / 高 visibility

| Speaker | Verbatim quote |
|---|---|
| 高赞评论 | **"AI tools are honestly unusable without running in yolo mode. You have to baby every single little command. It is utterly miserable and awful."** |
| 高赞评论 | "If it's running on your computer and can run arbitrary commands, it can wipe your disk, that's it." |
| 高赞评论 | "The `--dangerously-skip-permissions` flag does exactly what it says. It bypasses every guardrail and runs commands without asking you." |

**为什么这条 thread 重要**：第一条 quote **直接命中 Cockpit 的 product gap** —— 用户明确表达 "yolo / micro-permission" 的二元极化，没有中间产品形态。Cockpit 就是这个中间形态。

### Source B: ["Claude code modified my .bashrc without asking"](https://news.ycombinator.com/item?id=44499746)

| Speaker | Verbatim quote |
|---|---|
| fcpguru | **"I ended up making a bash script called 'c'...Because the alias kept getting removed! It was one of the first times I thought 'man, AI will start doing more and more "stuff" without asking me, this is just the start.'"** |
| JohnFen | "It's very disturbing that there are devs who think this behavior is even remotely acceptable" |
| antocuni (OP rebuttal) | "this is done by the installation process, not by AI" |

**为什么这条 thread 重要**：fcpguru 的 quote 表达 **escalation anxiety** —— 担心 AI 自主行为只会更不可控。这是 forward-looking pain，不是 already-happened pain。Cockpit 的 humanism thesis 直接回应这种焦虑。

---

## 2. 中文真实开发者语气 — V2EX

### Source C: [V2EX "有点搞不懂 Claude Code 了"](https://www.v2ex.com/t/1201779)

| Speaker | Verbatim quote（保留中文）|
|---|---|
| 楼主 nealzhuqian | **"纯 cli 编码的话任务开始后不就不能东看西看（指看看代码之类的）了，编码完成之后在 claude code 里看代码/review 貌似也不是很方便"** |
| BeautifulSoap | **"claude code 的很多设计的目的就是纯粹在逼着你不 review 代码改动，让你放弃对代码细节的掌控"** |
| BeautifulSoap | **"你根本没法 review 和它每轮对话后的代码，最终生成的代码你根本无法立刻掌控并且及时人工干预"** |
| lod | "相比图片/视频生成，代码作为'中间产物'的优势在于可以审查和低成本修改，纯靠'vibe coding'就等于放弃这种优势" |
| ksc010 | **"涉及线上业务的，我是一点不敢不做 review。因为业务太复杂了"** |

**为什么这条 thread 重要**：
- BeautifulSoap 的 quote 是 **整组 quote 里情感强度最高的**——"逼着你不 review / 放弃掌控" 是 emotionally loaded 表达，公众号文章直接可以当 hook
- ksc010 的 quote 表达 **production 场景的额外严肃性**——B 端 / 企业用户痛点比 hobbyist 深
- 楼主原话表达 **CLI 模式的 review 不便**——这是结构性 UX 问题，不是个人 preference

---

## 3. 隐式 product demand — 已被 community 命名的产品形态

### Source D: ["Plan Mode in Claude Code" by codewithmukesh](https://codewithmukesh.com/blog/plan-mode-claude-code/)

> **"Start your next session in Plan Mode. Force Claude to think first. Edit the plan. Then execute. Use plan mode for anything complex. Before Claude writes a single line of code, let it lay out its approach. It forces end-to-end thinking and lets you catch wrong assumptions before implementation begins."**

> **"Because it already explored the codebase and I already approved the approach, there are no surprises. No rogue global query filters."**

**为什么这条重要**："no surprises" / "approved the approach" —— **这就是 Plan-First 功能的 user benefit 描述**，社区已经在用这种语言。

### Source E: HN improvement suggestions (implicit, multiple commenters)

社区在多条 HN 评论中 implicit 描述需要的产品形态：
- **"Intermediate 'almost yolo' modes with light restrictions"**
- **"Supervisor models to prevent dangerous commands"**
- **"Better containerization/sandboxing enforcement before enabling the dangerous flag"**

**为什么这条重要**：**用户已经在用自然语言 describe Cockpit**——只是没人把它做出来。市场语言 ready，产品空白。

---

## 4. Adjacent media coverage — 行业级 framing

| Source | Framing quote |
|---|---|
| [HyperDev](https://hyperdev.matsuoka.com/p/when-ai-coding-feels-like-yelling) | "When AI Coding Feels Like Yelling at a Black Box" |
| [Implicator](https://www.implicator.ai/claude-probably-wasnt-secretly-nerfed-anthropic-made-the-black-box-too-dark/) | "Claude Code had become a stack of hidden policy choices that users could not fully inspect" |
| [DEV Community](https://dev.to/nirav_joshi/claude-code-charges-you-and-wont-tell-you-why-the-community-fixed-it-4hcd) | "Claude Code is a black box with a billing meter attached" |
| [Slashdot / Alex Kim blog](https://alex000kim.com/posts/2026-03-31-claude-code-source-leak/) (源码泄露分析) | Claude Code 源码里有 `userPromptKeywords.ts` 文件，含 regex 扫用户 frustration words（脏话）—— Anthropic 在 detect frustration 但没解决 opacity 根因 |

**meta 含义**："black box" 是 multiple independent 媒体共同使用的 framing word，已成行业级共识表达。

---

## 5. Pattern Analysis — 6 类共同 surface 的 sub-pain

把所有 quotes 抽取出来的公共主题：

| Pattern | 代表 quote | Cockpit 对应解法 |
|---|---|---|
| **① 极化 frustration（yolo vs micro-permission）** | "AI tools are honestly unusable without running in yolo mode" | Decision-level intervention（不是 per-tool）—— Decision Markers 设计 |
| **② 不可见性的具体形态** | "任务开始后不就不能东看西看了" | Plan-First + Live Narration |
| **③ 被迫放弃控制权（emotionally loaded）** | "逼着你不 review / 放弃掌控" | Pause / Override at decision points |
| **④ Escalation anxiety（forward-looking fear）** | "AI will start doing more and more stuff without asking me, this is just the start" | Humanism thesis 的产品化体现——决策不可绕过 |
| **⑤ Production 场景的额外保守** | "涉及线上业务的，我是一点不敢不做 review" | B 端切入点的 product positioning（v0.1 不专做但记下） |
| **⑥ 隐式产品语言（市场 ready）** | "Intermediate yolo / supervisor model / approve plan / no surprises" | Cockpit 直接 mirror 这套语言到 README + 文档 |

---

## 6. 对 Cockpit 产品决策的 implications

### 6.1 Build go/no-go：✅ Validated

证据强度（按 axes 评估）：
- ✅ **多语境**：英文 HN + 中文 V2EX，pain 跨语言一致
- ✅ **多 frame**：生气 / 害怕 / 困惑 / implicit demand 四种情感都有
- ✅ **高 visibility**：HN 255 分 thread，216 评论
- ✅ **直接产品形态语言**：community 已在用 "plan mode / intermediate yolo / no surprises" 描述 Cockpit
- ⚠️ **未拿到 X / Twitter raw posts**：但其他源已足够 validate

**结论**：Cockpit 解决的痛点是社区共识级 pain，**不是 idiosyncratic**。Build decision validated。

### 6.2 Positioning sharpening

基于 quotes，spec.md 的 positioning 可以加一条：

> **Cockpit is the missing middle ground between "yolo" and "baby every command".**

这句话直接 mirror HN top quote 的语言，社区一看就知道你在说什么。

### 6.3 Marketing assets 应用

| 资产 | 推荐 quote 用法 |
|---|---|
| **README hook** | HN top quote（"AI tools are honestly unusable..."） + 一句 "Cockpit is the middle ground" |
| **公众号文章 hook（中文）** | BeautifulSoap 的 "逼着你不 review / 放弃掌控" |
| **Demo 视频前 5 秒** | 滚屏 quote（HN 2 条 + V2EX 2 条），配黑盒 terminal 画面 |
| **投资 pitch / interview 用例** | HN 255 分数据 + 多源 quote 表明 community demand |

### 6.4 Anti-pattern 警告

⚠️ **不要把所有 quote 都堆进 README** —— 受众反感感觉强 sell。**精选 3-5 条最 sharp 的，留白比堆砌强**。

---

## 7. 待办：未来 X / Twitter 数据获取

**当前缺口**：X / Twitter raw posts（用户 unfiltered 实时 frustration）未能 retrieve

**待研究方法**：
- X API v2（需 dev account + paid tier，2026 年新政策）
- 第三方 X scraping 工具（合规性需 check）
- X 高质量账号 follow（已有 Karpathy / swyx / Amanda Askell 等，可定向看他们对 Claude Code 的吐槽）
- 用 typefully / nitter mirror 站作为 query 入口

**优先级**：Medium——当前证据已 validate build；X 数据是 nice-to-have，**不阻塞 v0.1 ship**

---

## 8. Decision log of this user-research

- 2026-04-29 第 1 轮：4 条 search 抓 community framing（HyperDev / Implicator / DEV / Anthropic 源码泄露）—— 确认行业级 black box 共识
- 2026-04-29 第 2 轮：5 条 search 针对 raw user voice—— Reddit 命中差，HN / V2EX 命中好
- 2026-04-29 第 3 轮：3 条 fetch 抓 HN / V2EX thread 全文—— 拿到 verbatim quotes
- **未来**：X 数据获取方法研究（单独 task）
