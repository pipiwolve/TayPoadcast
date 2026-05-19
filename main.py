#!/usr/bin/env python3
"""AI News Podcast Generator — Full Pipeline.

Usage:
    # Auto-pilot (CI mode): fetch → script → audio → notify
    python main.py --auto

    # Full pipeline without notification:
    python main.py --full --output output/daily_podcast.mp3

    # Demo mode (built-in script, no API key needed):
    python main.py --demo --output output/demo_podcast.mp3

    # Generate script only (no audio):
    python main.py --script-only
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import fetch_all, DailyDigest
from audio_generator import generate_audio, generate_audio_sync
from notifier import notify_all

DEMO_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "demo_script.json")


def _load_demo_script() -> list[dict]:
    with open(DEMO_SCRIPT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def print_banner():
    print("""
    ╔══════════════════════════════════╗
    ║   AI News Podcast Generator      ║
    ║   每日AI新闻播客生成器 v1.0       ║
    ╚══════════════════════════════════╝
    """)


def _save_artifacts(script: list[dict], audio_path: str, date_str: str):
    """Save script JSON and copy audio to a date-stamped output dir."""
    out_dir = f"output/{date_str}"
    os.makedirs(out_dir, exist_ok=True)

    script_path = os.path.join(out_dir, "script.json")
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"  ✓ 脚本已保存: {script_path}")
    print(f"  ✓ 播客已保存: {audio_path}")


async def run_auto_pipeline():
    """Auto-pilot: fetch → generate script → synthesize → notify → save."""
    date_str = datetime.now().strftime("%Y%m%d")
    date_display = datetime.now().strftime("%Y年%m月%d日")
    output_path = f"output/{date_str}/podcast_{date_str}.mp3"

    # Step 1: Fetch
    print(f"\n📡 Step 1/4: 获取今日AI热点...")
    digest = await fetch_all()
    print(f"   获取到 {len(digest.items)} 条新闻")
    for item in digest.items[:5]:
        print(f"   - {item.title[:60]}")

    # Step 2: Generate script
    print("\n🤖 Step 2/4: 生成双人播客脚本...")
    from script_generator import _detect_provider, generate_script

    provider = _detect_provider()
    print(f"   使用 LLM: {provider}")

    try:
        script = generate_script(digest.to_prompt_context())
        print(f"   生成了 {len(script)} 轮对话")
    except Exception as e:
        print(f"   ❌ 脚本生成失败: {e}")
        return None

    # Step 3: Synthesize audio
    print("\n🎙️  Step 3/4: 合成双人播客音频...")
    output = await generate_audio(script, output_path)
    if not output:
        print("   ❌ 音频合成失败")
        return None

    # Step 4: Notify
    print("\n📤 Step 4/4: 推送通知...")
    results = await notify_all(
        audio_path=output,
        script=script,
        date_str=date_display,
    )

    # Save artifacts
    _save_artifacts(script, output_path, date_str)

    # Summary
    channels_sent = [k for k, v in results.items() if v]
    if channels_sent:
        print(f"\n✅ 全管线完成！已通过 {', '.join(channels_sent)} 推送")
    else:
        print(f"\n⚠️  管线完成但未配置通知渠道")
        print("   设置 TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID 启用 Telegram 推送")

    return output


async def run_full_pipeline(output_path: str):
    """Fetch + generate + synthesize without notification."""
    print("\n📡 Step 1/3: 获取今日AI热点...")
    digest = await fetch_all()
    print(f"   获取到 {len(digest.items)} 条新闻")
    for item in digest.items[:5]:
        print(f"   - {item.title[:60]}")

    print("\n🤖 Step 2/3: 生成双人播客脚本...")
    from script_generator import _detect_provider, generate_script

    provider = _detect_provider()
    print(f"   使用 LLM: {provider}")

    try:
        script = generate_script(digest.to_prompt_context())
        print(f"   生成了 {len(script)} 轮对话")
    except Exception as e:
        print(f"   ❌ 脚本生成失败: {e}")
        return None

    print("\n🎙️  Step 3/3: 合成音频...")
    output = await generate_audio(script, output_path)
    return output


def run_demo(output_path: str):
    """Run with built-in demo script, no API keys needed."""
    date_str = datetime.now().strftime("%Y年%m月%d日")

    demo = _load_demo_script()
    script = []
    for turn in demo:
        script.append({
            "speaker": turn["speaker"],
            "text": turn["text"].format(date=date_str),
        })

    print(f"\n🎙️  使用演示脚本合成音频 ({len(script)} 轮对话)...")
    return generate_audio_sync(script, output_path)


async def run_script_only():
    """Generate and print script only."""
    print("\n📡 获取今日AI热点...")
    digest = await fetch_all()
    print(digest.to_prompt_context())

    print("\n🤖 生成播客脚本...")
    from script_generator import _detect_provider, generate_script

    provider = _detect_provider()
    has_key = (
        os.environ.get("ANTHROPIC_API_KEY") or
        os.environ.get("DEEPSEEK_API_KEY") or
        os.environ.get("OPENAI_API_KEY")
    )
    if not has_key:
        print(f"\n⚠️  未设置任何 LLM API Key，跳过脚本生成")
        print("   支持: ANTHROPIC_API_KEY / DEEPSEEK_API_KEY / OPENAI_API_KEY")
        print("   上述新闻内容可手动复制给 LLM 生成脚本")
        return

    print(f"   使用 LLM: {provider}")
    script = generate_script(digest.to_prompt_context())

    print(f"\n{'='*60}")
    print(f"  播客脚本 ({len(script)} 轮对话)")
    print(f"{'='*60}\n")
    for turn in script:
        speaker = turn.get("speaker", "?")
        text = turn.get("text", "")
        print(f"  {speaker}：{text}\n")

    date_str = datetime.now().strftime("%Y%m%d")
    script_path = f"output/script_{date_str}.json"
    os.makedirs("output", exist_ok=True)
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    print(f"脚本已保存: {script_path}")


def print_usage():
    print("用法:")
    print("  python main.py --auto          # 🤖 全自动: 采集→脚本→音频→推送")
    print("  python main.py --full          # 完整管线 (不推送)")
    print("  python main.py --demo          # 演示模式 (无需API key)")
    print("  python main.py --script-only   # 只生成脚本")
    print()
    print("LLM 配置 (三选一):")
    print("  ANTHROPIC_API_KEY     Claude API")
    print("  DEEPSEEK_API_KEY      DeepSeek API (推荐，便宜)")
    print("  OPENAI_API_KEY        OpenAI 或兼容 API")
    print("  LLM_PROVIDER          可选: anthropic/deepseek/openai (自动检测)")
    print("  LLM_MODEL             可选: 覆盖默认模型")
    print()
    print("通知配置 (可选):")
    print("  TELEGRAM_BOT_TOKEN    Telegram Bot Token")
    print("  TELEGRAM_CHAT_ID      Telegram 接收 Chat ID")
    print("  WX_APPID/WX_SECRET    微信测试号配置")


def main():
    parser = argparse.ArgumentParser(description="AI News Podcast Generator")
    parser.add_argument("--auto", action="store_true", help="全自动模式: 采集→脚本→音频→推送")
    parser.add_argument("--full", action="store_true", help="完整管线，不推送")
    parser.add_argument("--demo", action="store_true", help="演示模式 (无需API key)")
    parser.add_argument("--script-only", action="store_true", help="只生成脚本")
    parser.add_argument("--output", "-o", default="output/podcast.mp3", help="输出文件路径")
    args = parser.parse_args()

    print_banner()

    if args.auto:
        asyncio.run(run_auto_pipeline())
    elif args.script_only:
        asyncio.run(run_script_only())
    elif args.full:
        asyncio.run(run_full_pipeline(args.output))
    elif args.demo:
        run_demo(args.output)
    else:
        print_usage()


if __name__ == "__main__":
    main()
