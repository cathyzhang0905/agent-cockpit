#!/usr/bin/env python3
"""
Agent Cockpit — UserPromptSubmit hook.

Main brain of Cockpit. Lifecycle:
  1. Read user override mode from ~/.claude/cockpit.json
  2. If "off"  → exit silently (Cockpit disabled this session)
  3. If "on"   → skip Haiku, force plan-worthy
  4. If "auto" → call Haiku judge to classify task as plan-worthy / trivial
  5. If plan-worthy → inject plan-first instruction + write session state
  6. If trivial → write session state, no instruction injection
  7. Always log scenario_judge entry to .cockpit/[date].jsonl

Per Decision R1: Haiku failures fall back to "plan-worthy" (conservative).
Per Decision Sub-Q4: trivial tasks get NO Cockpit interference.
Per Decision Q5: hook fails silent (sys.exit 0) on any internal error.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

CONFIG_PATH = os.path.expanduser("~/.claude/cockpit.json")
LOG_DIR_NAME = ".cockpit"
LLM_TIMEOUT_SECONDS = 5
OLLAMA_TIMEOUT_SECONDS = 10  # local can be slower on first call

# Multi-provider config
ANTHROPIC_MODEL = "claude-haiku-4-5"
OPENAI_MODEL = "gpt-4o-mini"
OLLAMA_DEFAULT_MODEL = "llama3.2:3b"

# Chinese LLM providers (all OpenAI-compatible API except MiniMax)
QWEN_MODEL = "qwen-turbo"
DEEPSEEK_MODEL = "deepseek-chat"
GLM_MODEL = "glm-4-flash"          # GLM-4-Flash is FREE
KIMI_MODEL = "kimi-latest"
MINIMAX_MODEL = "abab6.5s-chat"

DEFAULT_PROVIDER_CHAIN = [
    "anthropic", "openai",                       # international
    "deepseek", "qwen", "glm", "kimi", "minimax",  # Chinese
    "ollama",                                    # local fallback
]

# ----------------------------------------------------------------------------
# Heuristic classifier (Plan B: works without API key)
# ----------------------------------------------------------------------------

# Trivial start patterns (greetings/acks). Matched prefix-style, lowercase.
TRIVIAL_STARTS = [
    "hi", "hello", "hey", "yo", "你好", "您好", "哈喽",
    "thanks", "thank you", "thx", "谢谢", "多谢",
    "ok", "okay", "好的", "嗯", "知道了", "明白",
    "bye", "再见",
]

# Plan-worthy keywords (Chinese)
PLAN_KEYWORDS_ZH = [
    # research / analysis
    "调研", "研究", "分析", "比较", "对比", "评估", "审阅", "梳理",
    "整理", "总结", "汇总", "复盘", "拆解", "深入",
    # creation
    "设计", "撰写", "写一份", "写一个", "生成", "创建", "构建", "搭建", "实现", "完善",
    # search / find
    "搜索", "查询", "查找", "找出", "列出", "罗列", "枚举", "找一下",
    # modification
    "修改", "编辑", "改写", "重构", "优化", "删除", "更新",
    # action verbs
    "帮我做", "帮我写", "帮我查", "帮我分析", "帮我整理", "帮我设计", "帮我对比",
]

# Plan-worthy keywords (English) — match lowercased
PLAN_KEYWORDS_EN = [
    "research", "analyze", "analyse", "compare", "investigate", "explore",
    "evaluate", "audit", "review", "summarize", "summarise", "synthesize",
    "design", "build", "create", "draft", "write a", "write an",
    "implement", "develop", "refactor", "modify", "fix", "debug",
    "find", "list", "search for", "look up", "look into",
]

# File modification keywords (both languages)
FILE_MOD_KEYWORDS = [
    "修改文件", "编辑文件", "改写", "改一下",
    "edit", "modify", "refactor", "rewrite",
]


def heuristic_judge(prompt: str) -> dict:
    """Keyword + length heuristic. Returns decision: 'skip' | 'plan' | 'ambiguous'.

    Order matters: explicit keywords win over length-based heuristics.
    Greeting at start with short length is the only "skip wins over keyword" case.
    """
    p = prompt.strip()
    p_lower = p.lower()
    p_length = len(p)

    # ---- Tier 1a: Greeting at start + short → skip (always wins) ----
    # Greetings like "hi" or "你好" should skip even if rest has keywords like
    # "thank you for the research" — but only if very short overall (a real greeting).
    if p_length < 50:
        for start in TRIVIAL_STARTS:
            if p_lower.startswith(start.lower()):
                return {
                    "decision": "skip",
                    "reason": f"Heuristic trivial: starts with '{start}' (short)",
                }

    # ---- Tier 2: Plan keywords (explicit signals beat length) ----

    # File modification keywords (highest confidence)
    for kw in FILE_MOD_KEYWORDS:
        if kw in p_lower or kw in p:
            return {
                "decision": "plan",
                "reason": f"Heuristic plan: file-mod keyword '{kw}'",
            }

    # Chinese plan keywords
    for kw in PLAN_KEYWORDS_ZH:
        if kw in p:
            return {
                "decision": "plan",
                "reason": f"Heuristic plan: Chinese keyword '{kw}'",
            }

    # English plan keywords
    for kw in PLAN_KEYWORDS_EN:
        if kw in p_lower:
            return {
                "decision": "plan",
                "reason": f"Heuristic plan: English keyword '{kw}'",
            }

    # ---- Tier 1b: Length-based trivial (only if no plan keyword found) ----
    # Very short prompt without any plan signal → likely lookup
    if p_length < 20:
        return {
            "decision": "skip",
            "reason": f"Heuristic trivial: short prompt ({p_length} chars, no keyword)",
        }

    # ---- Tier 3: Length-based plan signal ----
    # Long prompt without keywords — likely complex narrative
    if p_length > 100:
        return {
            "decision": "plan",
            "reason": f"Heuristic plan: long prompt ({p_length} chars, no clear keyword)",
        }

    # ---- Ambiguous: defer to LLM if available ----
    return {
        "decision": "ambiguous",
        "reason": f"Heuristic ambiguous: medium-length prompt ({p_length} chars), no keyword match",
    }

# ----------------------------------------------------------------------------
# Haiku judge prompt (D4.5 — Conservative + 5 explicit triggers + reason log)
# ----------------------------------------------------------------------------

LLM_JUDGE_PROMPT = """You are a triage classifier for Claude Code task oversight (Cockpit).

Given a user prompt (in any language, including Chinese), decide:
does this task benefit from a structured plan before tool execution?

Reply with JSON only:
{
  "decision": "plan" | "skip",
  "reason": "<one short sentence in same language as user prompt>"
}

Reply "plan" if ANY of these are clearly true:
1. Deep research task — comparing entities, analyzing competitors,
   multi-source synthesis, in-depth investigation (深度调研类)
2. Multiple external information gathering — multiple WebSearch/WebFetch
   steps expected (涉及外部多次搜集)
3. File modifications — creating, editing, writing files including code
   (文件修改/写代码)
4. Long-running task — estimated >3 minutes execution time
   (任务时间长)
5. Multi-step task with 3+ tool calls and multiple decision points

Reply "skip" if ANY of these:
- Conversational ("hi", "thanks", "你好", "explain X")
- Single-step lookup ("what time", "read README.md", "今天几号")
- Pure explanation/thinking, no tool use needed
- Small code question ("how do I X in Python", "Python 怎么 Y")

When ambiguous between plan and skip, lean "skip" — Cockpit is for
genuinely complex tasks. But if any of the 5 plan triggers is clearly
present, ALWAYS choose "plan".

User prompt:
\"\"\"
{prompt}
\"\"\"

Your reply (JSON only):"""

# ----------------------------------------------------------------------------
# Plan-first instruction (covers D1, D4 plan format, F1 thought, F5 assumption)
# ----------------------------------------------------------------------------

PLAN_INSTRUCTION = """[Cockpit Active] You are operating under Agent Cockpit — an active oversight layer.

This task has been classified as plan-worthy. You MUST follow these rules:

═══ 1. PLAN-FIRST ═══

Before calling any tool, output a structured plan. Choose tier based on task complexity:

Tier 1 (simple task, 1-3 steps):
<cockpit-plan>
- 1. [step] (using [tool])
- 2. [step] (using [tool])
- ETA: ~Xmin
</cockpit-plan>

Tier 2 (detailed task, multi-step):
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

Plan is informational — proceed to tool calls immediately after. The user does NOT need to approve.

═══ 2. THINKING CHECKPOINT (after EVERY tool call) ═══

After each tool call result, BEFORE deciding next action, output:

<cockpit-thought>
Got: [one-sentence summary of what tool returned that's relevant]
Insight: [optional — if finding changed your mental model or plan; skip if no change]
Next: [next action + brief why]
</cockpit-thought>

Then proceed immediately to next action. Do NOT wait for user approval.

═══ 3. ASSUMPTION MARKER (when making non-trivial assumptions) ═══

When you make an assumption that meaningfully affects output (especially in data analysis), declare:

<cockpit-assumption>
Assuming: [the assumption]
Why: [why making this assumption]
Impact: [what changes if this assumption is wrong]
</cockpit-assumption>

Only declare non-trivial assumptions (skip "assuming utf-8 encoding" type trivia).

═══ 4. BRIEF (at end of task) ═══

Before finishing your response, output:

Tier 1 brief (simple task):
<cockpit-brief>
Done in ~Tmin. N decisions. Output: PATH
</cockpit-brief>

Tier 2 brief (detailed task):
<cockpit-brief>
Decisions made: N
Outputs: [paths]
Time taken: ~Tmin
Recommend review: [1-2 decisions worth re-examining, or omit if none]
</cockpit-brief>

═══ Core principle ═══

Human decisions must be explicit and never bypassed. Cockpit scaffolds your reasoning; the human watches and intervenes if needed.

For Read / Grep / Glob / Bash tools: proceed silently (Cockpit doesn't ask before these).
For WebSearch / WebFetch / Task / Edit / Write / NotebookEdit: Claude Code will surface a permission dialog with Cockpit context — the user approves or denies.
"""

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def read_user_config() -> dict:
    """Read full ~/.claude/cockpit.json. Returns empty dict if missing/invalid."""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (IOError, OSError, json.JSONDecodeError):
        return {}


def read_user_override() -> str:
    """Read user override mode. Returns 'auto' if missing or invalid."""
    config = read_user_config()
    mode = config.get("mode", "auto")
    if mode in ("auto", "on", "off"):
        return mode
    return "auto"


def read_provider_chain() -> list:
    """Read LLM provider chain from config. Returns default chain if missing."""
    config = read_user_config()
    chain = config.get("llm_providers", DEFAULT_PROVIDER_CHAIN)
    if isinstance(chain, list) and chain:
        return chain
    return DEFAULT_PROVIDER_CHAIN


# ----------------------------------------------------------------------------
# LLM provider implementations
# Each returns dict {"decision": "plan"|"skip", "reason": "..."} or None on failure
# ----------------------------------------------------------------------------


def parse_llm_response(text: str) -> dict:
    """Parse LLM response (JSON-ish). Lenient — handles markdown fences + non-JSON."""
    text = text.strip()
    # Strip markdown code fence if present
    if text.startswith("```"):
        lines = text.split("\n")
        if len(lines) > 2:
            text = "\n".join(lines[1:-1])
        elif text.endswith("```"):
            text = text[3:-3].strip()

    # Try strict JSON parse
    try:
        parsed = json.loads(text)
        decision = parsed.get("decision", "plan")
        if decision not in ("plan", "skip"):
            decision = "plan"
        return {
            "decision": decision,
            "reason": str(parsed.get("reason", ""))[:200],
        }
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fallback: scan for "plan" or "skip" keyword in text
    text_lower = text.lower()
    has_plan = "plan" in text_lower
    has_skip = "skip" in text_lower
    if has_skip and not has_plan:
        return {"decision": "skip", "reason": "Parsed from non-JSON LLM response"}
    if has_plan and not has_skip:
        return {"decision": "plan", "reason": "Parsed from non-JSON LLM response"}
    # Both or neither — default plan (safe fallback)
    return {
        "decision": "plan",
        "reason": "LLM response unparseable — defaulted to plan",
    }


def call_anthropic_judge(prompt: str):
    """Call Anthropic Haiku. Returns None if no API key or call fails."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    body = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 200,
        "messages": [{
            "role": "user",
            "content": LLM_JUDGE_PROMPT.format(prompt=prompt),
        }],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["content"][0]["text"]
            return parse_llm_response(text)
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, KeyError, IndexError, TimeoutError, OSError):
        return None


def _call_openai_compatible(prompt: str, api_key_env: str, base_url: str,
                            model: str, timeout: int = LLM_TIMEOUT_SECONDS):
    """Generic OpenAI-compatible provider helper.

    Used for: OpenAI, DeepSeek, Qwen (compatible mode), GLM, Kimi/Moonshot.
    Returns None if no API key or call fails.
    """
    api_key = os.environ.get(api_key_env)
    if not api_key:
        return None

    body = json.dumps({
        "model": model,
        "max_tokens": 200,
        "messages": [{
            "role": "user",
            "content": LLM_JUDGE_PROMPT.format(prompt=prompt),
        }],
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"]
            return parse_llm_response(text)
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, KeyError, IndexError, TimeoutError, OSError):
        return None


def call_openai_judge(prompt: str):
    """OpenAI GPT-4o-mini."""
    return _call_openai_compatible(
        prompt, "OPENAI_API_KEY",
        "https://api.openai.com/v1", OPENAI_MODEL,
    )


def call_deepseek_judge(prompt: str):
    """DeepSeek deepseek-chat (V3)."""
    return _call_openai_compatible(
        prompt, "DEEPSEEK_API_KEY",
        "https://api.deepseek.com/v1", DEEPSEEK_MODEL,
    )


def call_qwen_judge(prompt: str):
    """Alibaba Qwen via DashScope OpenAI-compatible mode."""
    return _call_openai_compatible(
        prompt, "DASHSCOPE_API_KEY",
        "https://dashscope.aliyuncs.com/compatible-mode/v1", QWEN_MODEL,
    )


def call_glm_judge(prompt: str):
    """Zhipu GLM-4-Flash (free tier)."""
    return _call_openai_compatible(
        prompt, "ZHIPU_API_KEY",
        "https://open.bigmodel.cn/api/paas/v4", GLM_MODEL,
    )


def call_kimi_judge(prompt: str):
    """Moonshot Kimi."""
    return _call_openai_compatible(
        prompt, "MOONSHOT_API_KEY",
        "https://api.moonshot.cn/v1", KIMI_MODEL,
    )


def call_minimax_judge(prompt: str):
    """MiniMax abab6.5s-chat (uses its own endpoint, OpenAI-style body)."""
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return None

    group_id = os.environ.get("MINIMAX_GROUP_ID", "")

    body = json.dumps({
        "model": MINIMAX_MODEL,
        "max_tokens": 200,
        "messages": [{
            "role": "user",
            "content": LLM_JUDGE_PROMPT.format(prompt=prompt),
        }],
    }).encode("utf-8")

    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    if group_id:
        url += f"?GroupId={group_id}"

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"]
            return parse_llm_response(text)
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, KeyError, IndexError, TimeoutError, OSError):
        return None


def call_ollama_judge(prompt: str):
    """Call local Ollama. Returns None if Ollama not running."""
    ollama_model = os.environ.get("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    body = json.dumps({
        "model": ollama_model,
        "messages": [{
            "role": "user",
            "content": LLM_JUDGE_PROMPT.format(prompt=prompt),
        }],
        "stream": False,
        "options": {"num_predict": 200, "temperature": 0.0},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{ollama_host.rstrip('/')}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data["message"]["content"]
            return parse_llm_response(text)
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, KeyError, IndexError, TimeoutError, OSError):
        return None


# Provider registry — extend here to add new providers
PROVIDERS = {
    "anthropic": call_anthropic_judge,
    "openai": call_openai_judge,
    "deepseek": call_deepseek_judge,
    "qwen": call_qwen_judge,
    "glm": call_glm_judge,
    "kimi": call_kimi_judge,
    "minimax": call_minimax_judge,
    "ollama": call_ollama_judge,
}


def call_llm_judge(prompt: str, providers_chain: list):
    """Try providers in chain order. Returns (result, provider_name) or (None, None)."""
    for provider_name in providers_chain:
        provider_fn = PROVIDERS.get(provider_name)
        if provider_fn is None:
            continue
        try:
            result = provider_fn(prompt)
            if result is not None:
                return result, provider_name
        except Exception:
            continue
    return None, None


def write_log(cwd: str, entry: dict) -> None:
    """Append JSONL log entry. Fails silently."""
    try:
        log_dir = os.path.join(cwd, LOG_DIR_NAME)
        os.makedirs(log_dir, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = os.path.join(log_dir, f"{today}.jsonl")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except (IOError, OSError):
        pass


def write_session_state(cwd: str, state: dict) -> None:
    """Write session state file. Fails silently."""
    try:
        state_dir = os.path.join(cwd, LOG_DIR_NAME)
        os.makedirs(state_dir, exist_ok=True)
        with open(os.path.join(state_dir, "session-state.json"), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except (IOError, OSError):
        pass


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    user_prompt = input_data.get("prompt", "")
    cwd = input_data.get("cwd") or os.getcwd()
    session_id = input_data.get("session_id", "")
    now_iso = datetime.now(timezone.utc).isoformat()

    override = read_user_override()

    if override == "off":
        # Cockpit disabled this session
        write_session_state(cwd, {
            "session_id": session_id,
            "current_scenario": "off",
            "plan_required": False,
            "last_prompt_at": now_iso,
        })
        sys.exit(0)

    # Skip Cockpit for slash commands (explicit user invocation, not free-form task)
    # e.g., /cockpit status, /help, /agent-cockpit:cockpit on
    if user_prompt.lstrip().startswith("/"):
        write_session_state(cwd, {
            "session_id": session_id,
            "current_scenario": "trivial",
            "plan_required": False,
            "last_prompt_at": now_iso,
        })
        write_log(cwd, {
            "timestamp": now_iso,
            "session_id": session_id,
            "event_type": "scenario_judge",
            "prompt_preview": user_prompt[:200],
            "decision": "skip",
            "reason": "Slash command — Cockpit skipped (explicit user invocation)",
            "override_mode": override,
        })
        sys.exit(0)

    if override == "on":
        decision = "plan"
        reason = "User override: /cockpit on (forces plan-worthy)"
        classifier = "override"
    else:  # auto mode → Plan B+C: heuristic first, multi-provider LLM fallback
        h = heuristic_judge(user_prompt)
        if h["decision"] in ("plan", "skip"):
            # Heuristic confident → use it directly (no API call)
            decision = h["decision"]
            reason = h["reason"]
            classifier = "heuristic"
        else:
            # Heuristic ambiguous → try LLM provider chain
            providers_chain = read_provider_chain()
            llm_result, used_provider = call_llm_judge(user_prompt, providers_chain)
            if llm_result is not None:
                decision = llm_result["decision"]
                reason = f"LLM ({used_provider}): {llm_result['reason']}"
                classifier = f"llm:{used_provider}"
            else:
                # All providers unavailable/failed → conservative fallback to plan
                decision = "plan"
                reason = (
                    f"Heuristic ambiguous + all LLM providers unavailable "
                    f"({', '.join(providers_chain)}) → fallback to plan"
                )
                classifier = "fallback"

    # Log scenario_judge entry (with classifier type for v0.2 tune)
    write_log(cwd, {
        "timestamp": now_iso,
        "session_id": session_id,
        "event_type": "scenario_judge",
        "prompt_preview": user_prompt[:200],
        "decision": decision,
        "reason": reason,
        "classifier": classifier,
        "override_mode": override,
    })

    # Update session state
    write_session_state(cwd, {
        "session_id": session_id,
        "current_scenario": "plan-worthy" if decision == "plan" else "trivial",
        "plan_required": decision == "plan",
        "last_prompt_at": now_iso,
    })

    # Inject plan-first instruction if plan-worthy
    if decision == "plan":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": PLAN_INSTRUCTION,
            },
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
