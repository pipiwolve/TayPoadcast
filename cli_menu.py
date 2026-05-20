#!/usr/bin/env python3
"""交互式配置菜单 — 选择和定制每日播客领域模块."""

import os
import sys
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print("  ✓ 配置已保存到 config.yaml")


def show_banner():
    print("""
╔══════════════════════════════════════╗
║   TayPoadcast 播客配置中心           ║
║   选择你想收听的领域，我们每天生成    ║
╚══════════════════════════════════════╝
""")


def print_status(enabled: bool) -> str:
    return "✅ 已启用" if enabled else "⏸️  已停用"


def toggle_domains(config: dict) -> None:
    domains = config["domains"]
    print("\n📻 领域模块 (输入编号切换启用/停用，输入 0 返回):\n")
    for i, (key, d) in enumerate(domains.items(), 1):
        print(f"  {i}. {d['emoji']} {d['name']:<8} {print_status(d['enabled']):<12} — {d['description']}")
    print(f"\n  当前启用的领域: {[d['name'] for d in domains.values() if d['enabled']]}")

    choice = input("\n> 输入编号: ").strip()
    if choice == "0":
        return
    try:
        idx = int(choice) - 1
        key = list(domains.keys())[idx]
        domains[key]["enabled"] = not domains[key]["enabled"]
        status = "启用" if domains[key]["enabled"] else "停用"
        print(f"  ✓ {domains[key]['name']} 已{status}")
    except (ValueError, IndexError):
        print("  ✗ 无效编号")


def edit_prompt(config: dict) -> None:
    domains = config["domains"]
    print("\n✏️  自定义领域 Prompt (让播客更聚焦你关心的方向):\n")
    enabled_domains = {k: v for k, v in domains.items() if v["enabled"]}
    if not enabled_domains:
        print("  没有启用的领域，请先启用至少一个领域。")
        return
    for i, (key, d) in enumerate(enabled_domains.items(), 1):
        print(f"  {i}. {d['emoji']} {d['name']}")
        print(f"     Prompt: {d['prompt_extra'][:80]}...")

    choice = input("\n> 输入编号编辑 (0 返回): ").strip()
    if choice == "0":
        return
    try:
        idx = int(choice) - 1
        key = list(enabled_domains.keys())[idx]
        d = enabled_domains[key]
        print(f"\n  当前 Prompt: {d['prompt_extra']}")
        new_prompt = input("  新 Prompt (留空保持): ").strip()
        if new_prompt:
            domains[key]["prompt_extra"] = new_prompt
            print("  ✓ 已更新")
    except (ValueError, IndexError):
        print("  ✗ 无效编号")


def test_env(config: dict) -> None:
    print("\n🔍 环境检测:\n")
    checks = {
        "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY", ""),
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "WX_APPID": os.environ.get("WX_APPID", ""),
    }
    has_llm = bool(checks["DEEPSEEK_API_KEY"] or checks["ANTHROPIC_API_KEY"] or checks["OPENAI_API_KEY"])
    has_tg = bool(checks["TELEGRAM_BOT_TOKEN"] and checks["TELEGRAM_CHAT_ID"])
    has_wx = bool(checks["WX_APPID"])

    print(f"  LLM API Key: {'✅' if has_llm else '❌ 未设置 (必需)'}")
    print(f"  Telegram:    {'✅' if has_tg else '⚠️  未配置'}")
    print(f"  微信:         {'✅' if has_wx else '⚠️  未配置'}")
    enabled_domains = [d['name'] for d in config['domains'].values() if d['enabled']]
    print(f"\n  启用的领域: {enabled_domains if enabled_domains else '无 (请先启用)'}")


def main():
    config = load_config()
    show_banner()

    while True:
        enabled_count = sum(1 for d in config["domains"].values() if d["enabled"])
        print(f"\n{'─'*40}")
        print(f"已启用 {enabled_count} 个领域模块\n")
        print("  1. 🎛️   选择领域模块 (开关)")
        print("  2. ✏️   自定义领域 Prompt")
        print("  3. 🔍  环境检测")
        print("  4. 💾  保存配置")
        print("  5. ▶️   立即生成播客 (运行 main.py --auto)")
        print("  0. 🚪  退出")
        print(f"{'─'*40}")

        choice = input("\n> ").strip()

        if choice == "1":
            toggle_domains(config)
        elif choice == "2":
            edit_prompt(config)
        elif choice == "3":
            test_env(config)
        elif choice == "4":
            save_config(config)
        elif choice == "5":
            save_config(config)
            print("\n🚀 启动播客生成管线...\n")
            os.system(f"{sys.executable} {Path(__file__).parent / 'main.py'} --auto")
        elif choice == "0":
            save_config(config)
            print("👋 再见！")
            break
        else:
            print("  无效选项")


if __name__ == "__main__":
    main()
