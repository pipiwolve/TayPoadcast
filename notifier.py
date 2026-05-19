"""Multi-channel notification: Telegram Bot + WeChat Test Account."""

import os
import json
import asyncio
from pathlib import Path
from datetime import datetime

import httpx


# ── Telegram ──────────────────────────────────────────────

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


async def telegram_send_text(
    text: str,
    token: str | None = None,
    chat_id: str | None = None,
) -> bool:
    """Send a text message via Telegram Bot."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("  ⚠️  Telegram 未配置: 缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        return False

    url = TELEGRAM_API.format(token=token, method="sendMessage")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }, timeout=15)
            resp.raise_for_status()
            print(f"  ✓ Telegram 文本已发送")
            return True
        except Exception as e:
            print(f"  ✗ Telegram 文本发送失败: {e}")
            return False


async def telegram_send_audio(
    audio_path: str,
    caption: str = "",
    token: str | None = None,
    chat_id: str | None = None,
) -> bool:
    """Send an MP3 file via Telegram Bot (supports up to 50MB)."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("  ⚠️  Telegram 未配置")
        return False

    if not os.path.exists(audio_path):
        print(f"  ✗ 音频文件不存在: {audio_path}")
        return False

    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if file_size_mb > 50:
        print(f"  ✗ 文件过大 ({file_size_mb:.1f}MB)，Telegram 限制 50MB")
        return False

    url = TELEGRAM_API.format(token=token, method="sendAudio")
    async with httpx.AsyncClient() as client:
        try:
            with open(audio_path, "rb") as f:
                files = {"audio": (os.path.basename(audio_path), f, "audio/mpeg")}
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption
                    data["parse_mode"] = "HTML"
                resp = await client.post(url, data=data, files=files, timeout=60)
            resp.raise_for_status()
            print(f"  ✓ Telegram 音频已发送 ({file_size_mb:.1f}MB)")
            return True
        except Exception as e:
            print(f"  ✗ Telegram 音频发送失败: {e}")
            return False


async def telegram_send_podcast(
    audio_path: str,
    script: list[dict] | None = None,
    digest_items: list | None = None,
    date_str: str = "",
    duration_sec: float = 0,
    token: str | None = None,
    chat_id: str | None = None,
) -> dict:
    """Send podcast: repo summary preview first, then audio file."""
    if not date_str:
        date_str = datetime.now().strftime("%Y年%m月%d日")

    preview_lines = [f"🎙️ <b>AI新闻播客 | {date_str}</b>\n"]

    if digest_items:
        preview_lines.append("📦 <b>本期 GitHub 仓库：</b>")
        for i, item in enumerate(digest_items[:8]):
            if item.source == "GitHub热门" and item.stars > 0:
                star_str = f"⭐{item.stars}"
                lang_str = f" | {item.language}" if item.language else ""
                preview_lines.append(f"  {i+1}. <b>{item.title.strip()}</b> — {star_str}{lang_str}")
                if item.description:
                    desc = item.description[:80].strip()
                    preview_lines.append(f"     {desc}")
        preview_lines.append("")

    if script:
        minutes = int(duration_sec // 60) if duration_sec else 0
        seconds = int(duration_sec % 60) if duration_sec else 0
        if minutes:
            preview_lines.append(f"📻 共 {len(script)} 轮对话 · 时长 {minutes}分{seconds}秒")
        else:
            preview_lines.append(f"📻 共 {len(script)} 轮对话")
    preview_lines.append("点击下方音频收听 ↓")

    preview = "\n".join(preview_lines)

    results = {}
    results["text"] = await telegram_send_text(preview, token, chat_id)
    results["audio"] = await telegram_send_audio(audio_path, f"AI News {date_str}", token, chat_id)
    return results


# ── WeChat Test Account ───────────────────────────────────

WX_API = "https://api.weixin.qq.com/cgi-bin/{method}"


async def _wx_get_access_token(appid: str, secret: str) -> str | None:
    """Get WeChat test account access token."""
    url = WX_API.format(method="token")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params={
                "grant_type": "client_credential",
                "appid": appid,
                "secret": secret,
            }, timeout=15)
            data = resp.json()
            if "access_token" in data:
                return data["access_token"]
            print(f"  ✗ 微信 access_token 获取失败: {data}")
            return None
        except Exception as e:
            print(f"  ✗ 微信 API 请求失败: {e}")
            return None


async def wechat_send_template(
    title: str,
    summary: str,
    url: str = "",
    appid: str | None = None,
    secret: str | None = None,
    openid: str | None = None,
    template_id: str | None = None,
) -> bool:
    """Send a template message via WeChat test account."""
    appid = appid or os.environ.get("WX_APPID")
    secret = secret or os.environ.get("WX_SECRET")
    openid = openid or os.environ.get("WX_OPENID")
    template_id = template_id or os.environ.get("WX_TEMPLATE_ID")

    if not all([appid, secret, openid, template_id]):
        print("  ⚠️  微信未配置: 缺少 WX_APPID/WX_SECRET/WX_OPENID/WX_TEMPLATE_ID")
        return False

    token = await _wx_get_access_token(appid, secret)
    if not token:
        return False

    url_send = WX_API.format(method="message/template/send")
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "touser": openid,
                "template_id": template_id,
                "url": url,
                "data": {
                    "first": {"value": title, "color": "#1a1a1a"},
                    "keyword1": {"value": summary, "color": "#333333"},
                    "keyword2": {"value": datetime.now().strftime("%m月%d日 %H:%M"), "color": "#999999"},
                    "remark": {"value": "点击查看详情或收听播客 ↓", "color": "#576b95"},
                },
            }
            resp = await client.post(f"{url_send}?access_token={token}", json=payload, timeout=15)
            data = resp.json()
            if data.get("errcode") == 0:
                print(f"  ✓ 微信模板消息已发送")
                return True
            print(f"  ✗ 微信发送失败: {data}")
            return False
        except Exception as e:
            print(f"  ✗ 微信 API 请求失败: {e}")
            return False


# ── Combined ──────────────────────────────────────────────

async def notify_all(
    audio_path: str,
    script: list[dict] | None = None,
    digest_items: list | None = None,
    audio_url: str = "",
    date_str: str = "",
) -> dict:
    """Send podcast via all configured channels. Returns per-channel results."""
    if not date_str:
        date_str = datetime.now().strftime("%Y年%m月%d日")

    results = {}

    # Get audio duration for preview
    duration_sec = 0
    try:
        import subprocess
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ], capture_output=True, text=True)
        duration_sec = float(result.stdout.strip())
    except Exception:
        pass

    # Telegram — repo summary preview + MP3
    results["telegram"] = await telegram_send_podcast(
        audio_path=audio_path,
        script=script,
        digest_items=digest_items,
        date_str=date_str,
        duration_sec=duration_sec,
    )

    # WeChat — repo summary as template message
    if os.environ.get("WX_APPID"):
        top_story = "今日AI热点速递"
        if digest_items:
            stars = []
            for item in digest_items[:5]:
                if item.stars > 0:
                    stars.append(f"{item.title.strip()}(⭐{item.stars})")
            if stars:
                top_story = " · ".join(stars)[:120]
        elif script:
            top_story = script[0]["text"][:80]

        results["wechat"] = await wechat_send_template(
            title=f"AI新闻播客 | {date_str}",
            summary=top_story,
            url=audio_url,
        )

    return results


if __name__ == "__main__":
    print("Notification module loaded.")
    print("环境变量检查:")
    for var in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "WX_APPID", "WX_SECRET"]:
        val = os.environ.get(var)
        status = "✓ 已设置" if val else "✗ 未设置"
        print(f"  {var}: {status}")
