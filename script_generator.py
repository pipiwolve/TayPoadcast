"""Generate two-host Chinese podcast script from news digest.

Supports multiple LLM providers:
  - Anthropic (Claude): set ANTHROPIC_API_KEY
  - DeepSeek: set DEEPSEEK_API_KEY
  - Any OpenAI-compatible: set OPENAI_API_KEY + OPENAI_BASE_URL

Select provider via LLM_PROVIDER env var (auto-detected if not set).
"""

import json
import os
import re

import httpx

SYSTEM_PROMPT = """你是一个顶尖的播客脚本作家，专门为AI科技新闻播客撰写双人对谈脚本。你的脚本以"深、广、比"著称——深度分析、广泛覆盖、技术对比。

## 播客风格要求

你要模拟两个AI主持人（晓晓和云扬）的对话风格，类似Google NotebookLM的"深度探讨"模式，但比它更有料：

### 主持人设定
- **晓晓**（女声）：好奇心强，善于提问，代表"普通AI爱好者"视角。喜欢说"哇"、"真的假的"、"你等一下"、"这个有点意思"、"那他跟XXX比呢？"
- **云扬**（男声）：技术深度高，善于解释，代表"资深AI开发者"视角。偶尔温和反驳晓晓，补充技术背景和历史脉络。喜欢说"说白了"、"你想想看"、"关键就在于"、"这让我想起之前的XXX"

### 对话规则
1. **必须有口语填充词**：嗯、就是说、说白了、关键是、你猜怎么着、等等
2. **必须有真实互动**：晓晓打断提问、云扬说"好问题"、恍然大悟的"哦～"、偶尔抢话
3. **不要总是同意对方**：云扬偶尔说"我倒觉得不完全是"、"这个其实有个问题"、"说实话"
4. **自然过渡**："说起来..."、"对了，说到这个..."、"这让我想起..."
5. **开场白10秒内进入正题**：不要啰嗦的自我介绍
6. **每个重要项目至少聊3-4轮**：不能只提一嘴就过，要展开讲是什么、为什么重要、跟旧方案比好在哪里
7. **结尾必须有"今日金句"**：一句话总结今日最值得记住的洞察

### 核心技术深度要求（极其重要）

对于每个重点讨论的项目，必须做到：
- **是什么**：一句话说清楚这个项目/技术解决什么问题
- **为什么现在火**：结合当前行业背景解释趋势
- **跟旧技术对比**：这个新技术出现之前，大家是怎么解决这个问题的？旧方案的痛点是什么？新方案好在哪？
- **局限或争议**：客观指出可能的短板、风险、或社区争议

示例对比模式：
"以前我们做这个要XXX，步骤繁琐还容易出错。现在这个项目直接XXX，说白了就是把XXX的门槛从专家级降到了入门级。"
"这跟之前的XXX思路完全不一样。XXX是XXX的做法，但他这个是XXX，相当于把整个范式翻过来了。"

### 输出格式

你的回复必须包含两个部分，按顺序：

**第一部分：仓库速览**
用JSON数组列出本期精选的7-10个GitHub仓库的中文简介。这是给听众的"速览菜单"，每条简介至少30字：

```json
[
  {"name": "owner/repo", "stars": 3991, "lang": "Rust", "summary": "详细的中文描述——这个仓库做什么、解决什么痛点、跟已有方案的区别。至少30字。"},
  ...
]
```

**第二部分：播客脚本**
用JSON数组输出对话脚本，每句15-65字，保持自然口语节奏：

```json
[
  {"speaker": "晓晓", "text": "对话内容..."},
  {"speaker": "云扬", "text": "对话内容..."}
]
```

硬性要求：
- 25-35轮对话
- 总字数4000-6000字
- 播客时长约12-18分钟
- 至少深入讨论6-8个项目
- 至少包含3处新旧技术对比
- 每句话15-65字，长句不超过80字
"""


def build_user_prompt(
    digest_text: str,
    custom_instructions: str = "",
    domain_name: str = "",
    domain_prompt_extra: str = "",
) -> str:
    if domain_name:
        base = f"""请根据以下今日{domain_name}热点，生成一期高质量的中文双人深度播客脚本。

## 本期领域: {domain_name}

## 今日热点资讯
"""
    else:
        base = f"""请根据以下今日AI圈热点，生成一期高质量的中文双人深度播客脚本。

## 今日热点资讯
"""
    base += f"""
{digest_text}

## 本期要求
- 挑选最值得讲的7-10个项目深度讨论，按重要性排序，最炸裂的放最前面
"""
    if domain_prompt_extra:
        base += f"\n## 领域聚焦\n{domain_prompt_extra}\n"
    base += """
- 每个重点项目的讨论至少3-4轮对话，不能只提一嘴就过
- 必须为至少3个项目做"新旧技术对比"——在聊新技术之前，先提一下旧方案是什么、痛点在哪
- 可以自然串联相关项目（"说到XXX，今天还有个项目也是做这个方向的..."）
- 涉及同类项目时主动做横向对比（"那它跟XXX比怎么样？"）
- 全程用口语化中文，像是在真实聊天而不是念稿
- 注意节奏：开场快速抓人→中间深度展开→收尾精彩有力
"""
    if custom_instructions:
        base += f"\n## 特别指示\n{custom_instructions}\n"
    return base


def parse_response(response_text: str) -> tuple[list[dict], list[dict]]:
    """Parse LLM response into (script_turns, repo_summaries).

    Extracts two JSON blocks:
      1. Repo summaries: [{"name": "...", "stars": N, "lang": "...", "summary": "..."}]
      2. Dialogue script: [{"speaker": "晓晓|云扬", "text": "..."}]
    """
    script_turns = []
    repo_summaries = []

    # Find all JSON arrays in the response
    json_blocks = re.finditer(r'\[[\s\S]*?\]', response_text)

    candidates = []
    for match in json_blocks:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                candidates.append(parsed)
        except json.JSONDecodeError:
            continue

    # Classify each candidate by its keys
    for cand in candidates:
        keys = set(cand[0].keys())
        if "speaker" in keys:
            script_turns = cand
        elif "name" in keys and "summary" in keys:
            repo_summaries = cand

    # Fallback: parse dialogue from text if no JSON script found
    if not script_turns:
        lines = response_text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'[（(]?(晓晓|云扬)[)）]?\s*[：:]\s*(.+)', line)
            if match:
                speaker = match.group(1)
                text = match.group(2).strip()
                if len(text) > 5:
                    script_turns.append({"speaker": speaker, "text": text})

    return script_turns, repo_summaries


# ── Provider Detection ────────────────────────────────────

def _detect_provider() -> str:
    """Auto-detect which LLM provider to use based on env vars."""
    explicit = os.environ.get("LLM_PROVIDER", "").lower()
    if explicit in ("anthropic", "deepseek", "openai"):
        return explicit

    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"

    return "anthropic"  # default, will fail with clear message


# ── Provider Implementations ──────────────────────────────

def _call_anthropic(
    digest_text: str,
    api_key: str | None = None,
    domain_name: str = "",
    domain_prompt_extra: str = "",
) -> str:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("未设置 ANTHROPIC_API_KEY")

    import anthropic
    model = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
    client = anthropic.Anthropic(api_key=key)
    message = client.messages.create(
        model=model,
        max_tokens=8192,
        temperature=0.88,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(
            digest_text,
            domain_name=domain_name,
            domain_prompt_extra=domain_prompt_extra,
        )}],
    )
    return message.content[0].text


def _call_deepseek(
    digest_text: str,
    api_key: str | None = None,
    domain_name: str = "",
    domain_prompt_extra: str = "",
) -> str:
    """Call DeepSeek API (OpenAI-compatible)."""
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise ValueError("未设置 DEEPSEEK_API_KEY")

    model = os.environ.get("LLM_MODEL", "deepseek-chat")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    return _call_openai_compatible(
        digest_text, key, base_url, model,
        domain_name=domain_name,
        domain_prompt_extra=domain_prompt_extra,
    )


def _call_openai_compatible(
    digest_text: str,
    api_key: str,
    base_url: str,
    model: str,
    domain_name: str = "",
    domain_prompt_extra: str = "",
) -> str:
    """Generic OpenAI-compatible chat completions call via httpx."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.88,
        "max_tokens": 8192,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(
                digest_text,
                domain_name=domain_name,
                domain_prompt_extra=domain_prompt_extra,
            )},
        ],
    }
    resp = httpx.post(
        f"{base_url}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


PROVIDERS = {
    "anthropic": _call_anthropic,
    "deepseek": _call_deepseek,
    "openai": lambda digest, key=None, domain_name="", domain_prompt_extra="": _call_openai_compatible(
        digest,
        key or os.environ["OPENAI_API_KEY"],
        os.environ.get("OPENAI_BASE_URL", "https://api.openai.com"),
        os.environ.get("LLM_MODEL", "gpt-4o"),
        domain_name=domain_name,
        domain_prompt_extra=domain_prompt_extra,
    ),
}


# ── Public API ────────────────────────────────────────────

def generate_script(
    digest_text: str,
    provider: str | None = None,
    domain_name: str = "",
    domain_prompt_extra: str = "",
) -> tuple[list[dict], list[dict]]:
    """Generate a two-host podcast script + Chinese repo summaries.

    Args:
        digest_text: Formatted news digest text.
        provider: 'anthropic', 'deepseek', or 'openai'. Auto-detected if None.

    Returns:
        (script_turns, repo_summaries) where:
          - script_turns: [{"speaker": "晓晓|云扬", "text": "..."}]
          - repo_summaries: [{"name": "owner/repo", "stars": N, "lang": "...", "summary": "中文简介"}]

    Raises:
        ValueError: If no API key found for the selected provider.
    """
    provider = provider or _detect_provider()

    if provider not in PROVIDERS:
        raise ValueError(
            f"未知的 LLM provider: {provider}。"
            f"支持: {', '.join(PROVIDERS.keys())}"
        )

    call_fn = PROVIDERS[provider]
    raw = call_fn(
        digest_text,
        domain_name=domain_name,
        domain_prompt_extra=domain_prompt_extra,
    )
    turns, summaries = parse_response(raw)

    if not turns:
        raise ValueError(
            f"{provider} 返回的脚本无法解析。"
            f"原始响应 (前500字):\n{raw[:500]}"
        )

    print(f"  ✓ 使用 {provider} 生成了 {len(turns)} 轮对话" +
          (f", {len(summaries)} 条中文仓库简介" if summaries else ""))
    return turns, summaries


# Keep backward-compatible alias
generate_script_via_api = generate_script


# ── Self-test ─────────────────────────────────────────────

if __name__ == "__main__":
    print("Script generator module loaded.")
    detected = _detect_provider()
    print(f"  检测到的 provider: {detected}")
    print(f"  可用 providers: {', '.join(PROVIDERS.keys())}")
    print(f"  System prompt: {len(SYSTEM_PROMPT)} chars")
