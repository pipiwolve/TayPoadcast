#!/usr/bin/env python3
"""AI News Podcast Generator — Full Pipeline.

Usage:
    # Auto-pilot (CI mode): fetch → script → audio → notify
    python main.py --auto

    # Full pipeline without notification:
    python main.py --full --output output/daily_podcast.mp3

    # Demo mode (built-in script, no API key needed):
    python main.py --demo --output output/demo_podcast.mp3

    # Multi-domain demo (all enabled domains, no API key needed):
    python main.py --multi-demo

    # Generate script only (no audio):
    python main.py --script-only
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher import fetch_all, DailyDigest
from audio_generator import generate_audio, generate_audio_sync
from notifier import notify_all, notify_multi_domain

DEMO_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "demo_script.json")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

DEMO_SCRIPT_MAP = {
    "tech": "demo_script.json",
    "finance": "demo_script_finance.json",
    "academic": "demo_script_academic.json",
    "general": "demo_script_general.json",
}


def _load_demo_script(domain_key: str = "tech") -> list[dict]:
    filename = DEMO_SCRIPT_MAP.get(domain_key, "demo_script.json")
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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
    """Multi-domain auto-pilot: for each enabled domain, fetch → script → audio → notify."""
    config = _load_config()
    domains = config.get("domains", {})
    enabled = {k: v for k, v in domains.items() if v.get("enabled", False)}

    if not enabled:
        print("⚠️  没有启用的领域模块。请运行 python cli_menu.py 选择领域。")
        return None

    date_str = datetime.now().strftime("%Y%m%d")
    date_display = datetime.now().strftime("%Y年%m月%d日")

    from fetcher import FETCHER_REGISTRY
    from script_generator import _detect_provider, generate_script

    provider = _detect_provider()
    print(f"🎯 使用 LLM: {provider}")
    print(f"📻 启用的领域: {[v['name'] for v in enabled.values()]}\n")

    domain_results = []

    for domain_key, domain_cfg in enabled.items():
        domain_name = domain_cfg.get("name", domain_key)
        domain_emoji = domain_cfg.get("emoji", "")
        domain_prompt = domain_cfg.get("prompt_extra", "")

        print(f"\n{'='*60}")
        print(f"  {domain_emoji} 开始处理: {domain_name}")
        print(f"{'='*60}")

        # Step 1: Fetch
        print(f"\n📡 Step 1/4: 获取{domain_name}热点...")
        fetcher_cls = FETCHER_REGISTRY.get(domain_key)
        if not fetcher_cls:
            print(f"   ❌ 未知领域: {domain_key}，跳过")
            continue

        try:
            digest = await fetcher_cls().fetch()
            print(f"   获取到 {len(digest.items)} 条新闻")
            for item in digest.items[:3]:
                print(f"   - {item.title[:60]}")
        except Exception as e:
            print(f"   ❌ 采集失败: {e}")
            continue

        if not digest.items:
            print(f"   ⚠️  无新闻，跳过 {domain_name}")
            continue

        # Step 2: Generate script
        print(f"\n🤖 Step 2/4: 生成{domain_name}播客脚本...")
        try:
            script, repo_summaries = generate_script(
                digest.to_prompt_context(),
                domain_name=domain_name,
                domain_prompt_extra=domain_prompt,
            )
            print(f"   生成了 {len(script)} 轮对话")
        except Exception as e:
            print(f"   ❌ 脚本生成失败: {e}")
            continue

        # Step 3: Synthesize audio
        domain_output_dir = f"output/{date_str}/{domain_key}"
        os.makedirs(domain_output_dir, exist_ok=True)
        output_path = f"{domain_output_dir}/podcast_{date_str}.mp3"

        print(f"\n🎙️  Step 3/4: 合成{domain_name}播客音频...")
        try:
            audio_result = await generate_audio(script, output_path)
            if not audio_result:
                raise RuntimeError("音频合成为空")
        except Exception as e:
            print(f"   ❌ 音频合成失败: {e}")
            continue

        # Save artifacts
        script_path = os.path.join(domain_output_dir, "script.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
        print(f"  ✓ 脚本已保存: {script_path}")
        print(f"  ✓ 播客已保存: {output_path}")

        domain_results.append({
            "domain": domain_key,
            "name": domain_name,
            "audio_path": audio_result,
            "script": script,
            "repo_summaries": repo_summaries,
            "digest_items": digest.items,
        })

    # Step 4: Aggregated notification
    if domain_results:
        print(f"\n📤 Step 4/4: 推送多领域播客 ({len(domain_results)} 个领域)...")
        results = await notify_multi_domain(domain_results, date_str=date_display)

        channels_sent = [k for k, v in results.items() if v]
        if channels_sent:
            print(f"\n✅ 全管线完成！已通过 {', '.join(channels_sent)} 推送 {len(domain_results)} 个领域播客")
        else:
            print(f"\n⚠️  管线完成但未配置通知渠道")
    else:
        print("\n⚠️  所有领域均处理失败")

    return domain_results


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
        script, _ = generate_script(digest.to_prompt_context())
        print(f"   生成了 {len(script)} 轮对话")
    except Exception as e:
        print(f"   ❌ 脚本生成失败: {e}")
        return None

    print("\n🎙️  Step 3/3: 合成音频...")
    output = await generate_audio(script, output_path)
    return output


def run_demo(output_path: str, domain_key: str = "tech"):
    """Run with built-in demo script, no API keys needed."""
    date_str = datetime.now().strftime("%Y年%m月%d日")

    demo = _load_demo_script(domain_key)
    script = []
    for turn in demo:
        script.append({
            "speaker": turn["speaker"],
            "text": turn["text"].format(date=date_str),
        })

    print(f"\n🎙️  使用{domain_key}演示脚本合成音频 ({len(script)} 轮对话)...")
    return generate_audio_sync(script, output_path)


def run_multi_demo():
    """Generate demo podcasts for all enabled domains. No API keys needed."""
    config = _load_config()
    domains = config.get("domains", {})
    enabled = {k: v for k, v in domains.items() if v.get("enabled", False)}

    if not enabled:
        print("⚠️  没有启用的领域模块。请运行 python cli_menu.py 选择领域。")
        return

    date_str = datetime.now().strftime("%Y%m%d")
    results = []

    for domain_key, domain_cfg in enabled.items():
        domain_name = domain_cfg.get("name", domain_key)
        domain_emoji = domain_cfg.get("emoji", "")

        if domain_key not in DEMO_SCRIPT_MAP:
            print(f"  ⚠️  {domain_name} 无演示脚本，跳过")
            continue

        print(f"\n{'='*50}")
        print(f"  {domain_emoji} 生成{domain_name}演示播客...")
        print(f"{'='*50}")

        domain_output_dir = f"output/{date_str}/{domain_key}"
        os.makedirs(domain_output_dir, exist_ok=True)
        output_path = f"{domain_output_dir}/podcast_{date_str}.mp3"

        try:
            result = run_demo(output_path, domain_key)
            if result:
                # Save script artifact too
                demo = _load_demo_script(domain_key)
                demo_script = []
                date_display = datetime.now().strftime("%Y年%m月%d日")
                for turn in demo:
                    demo_script.append({
                        "speaker": turn["speaker"],
                        "text": turn["text"].format(date=date_display),
                    })
                script_path = os.path.join(domain_output_dir, "script.json")
                with open(script_path, "w", encoding="utf-8") as f:
                    json.dump(demo_script, f, ensure_ascii=False, indent=2)
                results.append(domain_name)
        except Exception as e:
            print(f"   ❌ {domain_name} 生成失败: {e}")
            continue

    if results:
        print(f"\n✅ 多领域演示播客生成完成！")
        print(f"   已生成: {', '.join(results)}")
        print(f"   输出目录: output/{date_str}/")
    else:
        print("\n⚠️  所有领域均生成失败")


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
    script, summaries = generate_script(digest.to_prompt_context())

    print(f"\n{'='*60}")
    print(f"  仓库速览 ({len(summaries)} 条)")
    print(f"{'='*60}\n")
    for s in summaries:
        print(f"  📦 {s.get('name', '?')} ⭐{s.get('stars', '?')} | {s.get('lang', '?')}")
        print(f"     {s.get('summary', '')}\n")

    print(f"{'='*60}")
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
    print("  python main.py --multi-demo    # 多领域演示 (所有启用领域，无需API key)")
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
    parser.add_argument("--multi-demo", action="store_true", help="多领域演示 (所有启用领域，无需API key)")
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
    elif args.multi_demo:
        run_multi_demo()
    elif args.demo:
        run_demo(args.output)
    else:
        print_usage()


if __name__ == "__main__":
    main()
