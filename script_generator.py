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

SYSTEM_PROMPT = """你是一个顶尖的播客脚本作家，专门为AI科技新闻播客撰写双人对谈脚本。

## 播客风格要求

你要模拟两个AI主持人（晓晓和云扬）的对话风格，类似Google NotebookLM的"深度探讨"模式：

### 主持人设定
- **晓晓**（女声）：好奇心强，善于提问，代表"普通AI爱好者"视角。喜欢说"哇"、"真的假的"、"你等一下"、"这个有点意思"
- **云扬**（男声）：技术深度高，善于解释，代表"资深AI开发者"视角。偶尔温和反驳晓晓，补充技术背景

### 对话规则
1. **必须包含口语填充词**：嗯、就是说、你想想看、说白了、关键是、等等
2. **必须有互动反应**：晓晓打断提问、云扬说"好问题"、两人抢话、恍然大悟的"哦～"
3. **不要总是同意对方**：云扬偶尔说"我倒觉得不完全是"、"这个其实有个问题"
4. **每条新闻讲完要有过渡**：自然的"说起来..."、"对了，还有一个新闻..."
5. **开场白10秒内进入正题**：不要啰嗦的自我介绍
6. **结尾要有"今日金句"**：一句话总结今天最值得记住的事

### 输出格式

你的回复必须包含两个部分，按顺序：

**第一部分：仓库速览**
用JSON数组列出本期精选的5-7个GitHub仓库的中文简介：

```json
[
  {"name": "owner/repo", "stars": 3991, "lang": "Rust", "summary": "一句话中文描述，说明这个仓库是做什么的、为什么值得关注"},
  ...
]
```

**第二部分：播客脚本**
用JSON数组输出对话脚本：

```json
[
  {"speaker": "晓晓", "text": "对话内容..."},
  {"speaker": "云扬", "text": "对话内容..."}
]
```

要求：10-15轮对话，总字数2000-3500字，播客时长约5-8分钟。
每句话控制在15-50字之间，不要有超过80字的长句。
"""


def build_user_prompt(digest_text: str, custom_instructions: str = "") -> str:
    base = f"""请根据以下今日AI圈热点，生成一期中文双人播客脚本。

## 今日热点资讯

{digest_text}

## 额外要求
- 挑选最值得讲的5-7条，不要每条都讲
- 按重要性排序，最炸裂的放最前面
- 如果某条新闻特别重要，可以聊2-3轮再换下一条
- 全程用口语化中文，像是在聊天而不是在念稿
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

def _call_anthropic(digest_text: str, api_key: str | None = None) -> str:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("未设置 ANTHROPIC_API_KEY")

    import anthropic
    model = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
    client = anthropic.Anthropic(api_key=key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0.85,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(digest_text)}],
    )
    return message.content[0].text


def _call_deepseek(digest_text: str, api_key: str | None = None) -> str:
    """Call DeepSeek API (OpenAI-compatible)."""
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise ValueError("未设置 DEEPSEEK_API_KEY")

    model = os.environ.get("LLM_MODEL", "deepseek-chat")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    return _call_openai_compatible(digest_text, key, base_url, model)


def _call_openai_compatible(
    digest_text: str,
    api_key: str,
    base_url: str,
    model: str,
) -> str:
    """Generic OpenAI-compatible chat completions call via httpx."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.85,
        "max_tokens": 4096,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(digest_text)},
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
    "openai": lambda digest, key=None: _call_openai_compatible(
        digest,
        key or os.environ["OPENAI_API_KEY"],
        os.environ.get("OPENAI_BASE_URL", "https://api.openai.com"),
        os.environ.get("LLM_MODEL", "gpt-4o"),
    ),
}


# ── Public API ────────────────────────────────────────────

def generate_script(digest_text: str, provider: str | None = None) -> tuple[list[dict], list[dict]]:
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
    raw = call_fn(digest_text)
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
