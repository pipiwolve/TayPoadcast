"""Generate two-host Chinese podcast script from news digest using Claude API."""

import json
import os
import re

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
输出一个JSON数组，每个元素是一个对话轮次：

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


def parse_script(response_text: str) -> list[dict]:
    """Parse Claude's response into turn list. Handles both JSON and text formats."""
    turns = []

    # Try JSON array extraction
    json_match = re.search(r'\[[\s\S]*\]', response_text)
    if json_match:
        try:
            turns = json.loads(json_match.group())
            if isinstance(turns, list) and len(turns) > 0 and isinstance(turns[0], dict):
                return turns
        except json.JSONDecodeError:
            pass

    # Fallback: parse from text pattern "晓晓：..." or "云扬：..."
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
                turns.append({"speaker": speaker, "text": text})

    return turns


def generate_script_via_api(digest_text: str, api_key: str | None = None) -> list[dict]:
    """Generate script using Anthropic API."""
    import anthropic

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("需要设置 ANTHROPIC_API_KEY 环境变量")

    client = anthropic.Anthropic(api_key=key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        temperature=0.85,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(digest_text)}],
    )

    raw = message.content[0].text
    turns = parse_script(raw)

    if not turns:
        raise ValueError(f"无法解析脚本。原始响应:\n{raw[:500]}")

    return turns


if __name__ == "__main__":
    # Quick test
    print("Script generator module loaded.")
    print(f"System prompt length: {len(SYSTEM_PROMPT)} chars")
