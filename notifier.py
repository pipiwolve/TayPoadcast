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
    repo_summaries: list[dict] | None = None,
    date_str: str = "",
    duration_sec: float = 0,
    token: str | None = None,
    chat_id: str | None = None,
) -> dict:
    """Send podcast: repo summary preview first, then audio file."""
    if not date_str:
        date_str = datetime.now().strftime("%Y年%m月%d日")

    preview_lines = [f"🎙️ <b>AI新闻播客 | {date_str}</b>\n"]

    # Use Chinese summaries from LLM if available, fallback to raw data
    if repo_summaries:
        preview_lines.append("📦 <b>本期 GitHub 仓库：</b>")
        for i, s in enumerate(repo_summaries[:6]):
            name = s.get("name", "?")
            stars = s.get("stars", 0)
            lang = s.get("lang", "")
            summary = s.get("summary", "")
            star_str = f"⭐{stars}" if stars else ""
            lang_str = f" | {lang}" if lang else ""
            preview_lines.append(f"  {i+1}. <b>{name}</b> — {star_str}{lang_str}")
            if summary:
                preview_lines.append(f"     {summary}")
        preview_lines.append("")

    elif digest_items:
        preview_lines.append("📦 <b>本期 GitHub 仓库：</b>")
        for i, item in enumerate(digest_items[:6]):
            if item.stars > 0:
                lang_str = f" | {item.language}" if item.language else ""
                preview_lines.append(f"  {i+1}. <b>{item.title.strip()}</b> — ⭐{item.stars}{lang_str}")
                if item.description:
                    preview_lines.append(f"     {item.description[:80].strip()}")
        preview_lines.append("")

    if script:
        minutes = int(duration_sec // 60) if duration_sec else 0
        seconds = int(duration_sec % 60) if duration_sec else 0
        duration_str = f" · 时长 {minutes}分{seconds}秒" if minutes else ""
        preview_lines.append(f"📻 共 {len(script)} 轮对话{duration_str}")
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


# ── Feishu (飞书) ──────────────────────────────────────────

FEISHU_API = "https://open.feishu.cn/open-apis/{path}"

_feishu_token_cache: dict = {}  # {"token": "t-xxx", "expires_at": 1716200000.0}


async def _feishu_get_tenant_token(
    app_id: str,
    app_secret: str,
) -> str | None:
    """Get tenant_access_token, cached for 2h."""
    import time

    now = time.time()
    cached = _feishu_token_cache
    if cached.get("token") and cached.get("expires_at", 0) > now + 60:
        return cached["token"]

    url = FEISHU_API.format(path="auth/v3/tenant_access_token/internal")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json={
                "app_id": app_id,
                "app_secret": app_secret,
            }, timeout=15)
            data = resp.json()
            if data.get("code") == 0:
                token = data["tenant_access_token"]
                expire = data.get("expire", 7200)
                cached["token"] = token
                cached["expires_at"] = now + expire - 120
                return token
            print(f"  ✗ 飞书 tenant_access_token 获取失败: {data}")
            return None
        except Exception as e:
            print(f"  ✗ 飞书 API 请求失败: {e}")
            return None


async def feishu_upload_file(
    file_path: str,
    file_type: str = "stream",
    token: str | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
) -> str | None:
    """Upload a file to Feishu IM. Returns file_key or None."""
    token = token or await _feishu_get_tenant_token(
        app_id or os.environ.get("FEISHU_APP_ID", ""),
        app_secret or os.environ.get("FEISHU_APP_SECRET", ""),
    )
    if not token:
        print("  ⚠️  飞书 token 获取失败，跳过文件上传")
        return None

    if not os.path.exists(file_path):
        print(f"  ✗ 文件不存在: {file_path}")
        return None

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > 30:
        print(f"  ✗ 文件过大 ({file_size_mb:.1f}MB)，飞书限制 30MB")
        return None

    url = FEISHU_API.format(path="im/v1/files")
    async with httpx.AsyncClient() as client:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, "audio/mpeg")}
                data = {
                    "file_type": file_type,
                    "file_name": os.path.basename(file_path),
                }
                resp = await client.post(
                    url,
                    data=data,
                    files=files,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=60,
                )
            resp_data = resp.json()
            if resp_data.get("code") == 0:
                file_key = resp_data["data"]["file_key"]
                print(f"  ✓ 飞书文件已上传 ({file_size_mb:.1f}MB) -> {file_key}")
                return file_key
            print(f"  ✗ 飞书文件上传失败: {resp_data}")
            return None
        except Exception as e:
            print(f"  ✗ 飞书文件上传异常: {e}")
            return None


async def feishu_send_text(
    text: str,
    receive_id: str,
    receive_id_type: str = "open_id",
    token: str | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
) -> bool:
    """Send a text message via Feishu bot."""
    app_id = app_id or os.environ.get("FEISHU_APP_ID")
    app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")

    if not all([app_id, app_secret, receive_id]):
        print("  ⚠️  飞书未配置: 缺少 app_id/app_secret/receive_id")
        return False

    token = token or await _feishu_get_tenant_token(app_id, app_secret)
    if not token:
        return False

    url = FEISHU_API.format(path="im/v1/messages")
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}),
            }
            resp = await client.post(
                f"{url}?receive_id_type={receive_id_type}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            data = resp.json()
            if data.get("code") == 0:
                print(f"  ✓ 飞书文本已发送")
                return True
            print(f"  ✗ 飞书文本发送失败: {data}")
            return False
        except Exception as e:
            print(f"  ✗ 飞书 API 请求失败: {e}")
            return False


async def feishu_send_file(
    file_key: str,
    receive_id: str,
    receive_id_type: str = "open_id",
    token: str | None = None,
    app_id: str | None = None,
    app_secret: str | None = None,
) -> bool:
    """Send a file message via Feishu bot using an uploaded file_key."""
    app_id = app_id or os.environ.get("FEISHU_APP_ID")
    app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")

    if not all([app_id, app_secret, receive_id]):
        return False

    token = token or await _feishu_get_tenant_token(app_id, app_secret)
    if not token:
        return False

    url = FEISHU_API.format(path="im/v1/messages")
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "receive_id": receive_id,
                "msg_type": "file",
                "content": json.dumps({"file_key": file_key}),
            }
            resp = await client.post(
                f"{url}?receive_id_type={receive_id_type}",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            data = resp.json()
            if data.get("code") == 0:
                print(f"  ✓ 飞书文件消息已发送")
                return True
            print(f"  ✗ 飞书文件消息发送失败: {data}")
            return False
        except Exception as e:
            print(f"  ✗ 飞书 API 请求失败: {e}")
            return False


async def feishu_send_podcast(
    audio_path: str,
    script: list[dict] | None = None,
    repo_summaries: list[dict] | None = None,
    date_str: str = "",
    duration_sec: float = 0,
    receive_id: str = "",
    receive_id_type: str = "open_id",
    app_id: str = "",
    app_secret: str = "",
) -> dict:
    """Send podcast: text preview first, then MP3 file via Feishu.

    All credentials accepted as parameters (from frontend form or env vars).
    Falls back to env vars if parameters are empty.
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y年%m月%d日")

    app_id = app_id or os.environ.get("FEISHU_APP_ID", "")
    app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET", "")
    receive_id = receive_id or os.environ.get("FEISHU_RECEIVE_ID", "")
    receive_id_type = receive_id_type or os.environ.get("FEISHU_RECEIVE_ID_TYPE", "open_id")

    if not all([app_id, app_secret, receive_id]):
        print("  ⚠️  飞书未配置: 缺少 app_id/app_secret/receive_id")
        return {"text": False, "file": False}

    token = await _feishu_get_tenant_token(app_id, app_secret)
    if not token:
        return {"text": False, "file": False}

    # Build text preview
    preview_lines = [f"🎙️ AI新闻播客 | {date_str}\n"]
    if repo_summaries:
        preview_lines.append("📦 本期仓库：")
        for i, s in enumerate(repo_summaries[:6]):
            name = s.get("name", "?")
            stars = s.get("stars", 0)
            summary = s.get("summary", "")
            star_str = f"⭐{stars}" if stars else ""
            preview_lines.append(f"  {i+1}. {name} — {star_str}")
            if summary:
                preview_lines.append(f"     {summary}")
        preview_lines.append("")
    if script:
        minutes = int(duration_sec // 60) if duration_sec else 0
        seconds = int(duration_sec % 60) if duration_sec else 0
        duration_str = f" · 时长 {minutes}分{seconds}秒" if minutes else ""
        preview_lines.append(f"📻 共 {len(script)} 轮对话{duration_str}")
    preview_lines.append("点击下方文件收听 ↓")

    results = {}
    results["text"] = await feishu_send_text(
        "\n".join(preview_lines), receive_id, receive_id_type, token, app_id, app_secret,
    )

    # Upload and send MP3
    file_key = await feishu_upload_file(audio_path, "stream", token, app_id, app_secret)
    if file_key:
        results["file"] = await feishu_send_file(
            file_key, receive_id, receive_id_type, token, app_id, app_secret,
        )
    else:
        results["file"] = False

    return results


# ── Combined ──────────────────────────────────────────────

async def notify_all(
    audio_path: str,
    script: list[dict] | None = None,
    digest_items: list | None = None,
    repo_summaries: list[dict] | None = None,
    audio_url: str = "",
    date_str: str = "",
) -> dict:
    """Send podcast via all configured channels. Returns per-channel results."""
    if not date_str:
        date_str = datetime.now().strftime("%Y年%m月%d日")

    results = {}

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

    # Telegram — Chinese repo summary preview + MP3
    results["telegram"] = await telegram_send_podcast(
        audio_path=audio_path,
        script=script,
        digest_items=digest_items,
        repo_summaries=repo_summaries,
        date_str=date_str,
        duration_sec=duration_sec,
    )

    # WeChat — text briefing (no link, self-contained summary)
    if os.environ.get("WX_APPID"):
        if repo_summaries:
            lines = []
            for i, s in enumerate(repo_summaries[:5]):
                name = s.get("name", "?").split("/")[-1]
                stars = s.get("stars", 0)
                summary = s.get("summary", "")
                lines.append(f"{i+1}.{name} ⭐{stars} {summary}")
            briefing = "\n".join(lines)
        elif digest_items:
            lines = []
            for i, item in enumerate(digest_items[:5]):
                if item.stars > 0:
                    name = item.title.strip().split("/")[-1]
                    lines.append(f"{i+1}.{name} ⭐{item.stars}")
            briefing = "\n".join(lines) if lines else "今日AI热点速递"
        else:
            briefing = "今日AI热点速递，点击收听完整播客"

        # Truncate to fit WeChat template limits
        briefing = briefing[:200]

        results["wechat"] = await wechat_send_template(
            title=f"AI新闻早报 | {date_str}",
            summary=briefing,
            url="",  # No GitHub link — self-contained text briefing
        )

    return results


async def notify_multi_domain(
    domain_results: list[dict],
    date_str: str = "",
) -> dict:
    """Send aggregated multi-domain notification.

    Args:
        domain_results: [
            {
                "domain": "tech",
                "name": "技术资讯",
                "audio_path": "output/20260520/tech/podcast.mp3",
                "script": [...],
                "repo_summaries": [...],
            },
            ...
        ]
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y年%m月%d日")

    results = {}

    # Telegram: send each domain's podcast separately
    telegram_ok = False
    for dr in domain_results:
        domain_tag = f"[{dr['name']}]"
        audio_path = dr.get("audio_path", "")
        if not audio_path or not os.path.exists(audio_path):
            print(f"  ⚠️  跳过 {domain_tag}: audio_path 不存在 ({audio_path})")
            continue

        res = await telegram_send_podcast(
            audio_path=audio_path,
            script=dr.get("script"),
            repo_summaries=dr.get("repo_summaries"),
            date_str=f"{date_str} {domain_tag}",
        )
        if res.get("text") or res.get("audio"):
            telegram_ok = True

    results["telegram"] = telegram_ok

    # WeChat: send one aggregated text briefing for all domains
    if os.environ.get("WX_APPID"):
        lines = []
        for dr in domain_results:
            name = dr.get("name", "?")
            items = dr.get("repo_summaries", [])
            if items:
                lines.append(f"【{name}】")
                for j, s in enumerate(items[:3]):
                    repo_name = s.get("name", "?").split("/")[-1]
                    stars = s.get("stars", 0)
                    summary = s.get("summary", "")
                    lines.append(f"  {repo_name} ⭐{stars} {summary[:40]}")
                lines.append("")

        briefing = "\n".join(lines)[:200] if lines else "今日多领域资讯速递"
        results["wechat"] = await wechat_send_template(
            title=f"AI新闻早报 | {date_str}",
            summary=briefing,
        )

    return results


if __name__ == "__main__":
    print("Notification module loaded.")
    print("环境变量检查:")
    for var in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "WX_APPID", "WX_SECRET"]:
        val = os.environ.get(var)
        status = "✓ 已设置" if val else "✗ 未设置"
        print(f"  {var}: {status}")
