#!/usr/bin/env python3
"""Web UI for TayPoadcast — Flask-based podcast control center.

Usage:
    pip install flask
    python web_app.py
    # Open http://localhost:5000

Environment variables are loaded automatically from .env file.
"""

import asyncio
import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path


def _load_dotenv(env_path: str | None = None):
    """Load KEY=VALUE pairs from a .env file into os.environ (no dependency needed)."""
    if env_path is None:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and not os.environ.get(key):  # don't override existing env vars
                os.environ[key] = value


_load_dotenv()

from flask import Flask, jsonify, request, send_file

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
from audio_generator import generate_audio_sync

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "output")

DEMO_SCRIPT_MAP = {
    "tech": "demo_script.json",
    "finance": "demo_script_finance.json",
    "academic": "demo_script_academic.json",
    "general": "demo_script_general.json",
}

# In-memory task store (sufficient for single-user local use)
_tasks: dict[str, dict] = {}
_task_counter = [0]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_demo_script(domain_key: str) -> list[dict]:
    filename = DEMO_SCRIPT_MAP.get(domain_key, "demo_script.json")
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _format_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}分{s}秒"


def _run_demo_thread(domain_key: str, domain_cfg: dict, task_id: str, results: dict):
    """Background thread: generate demo podcast for one domain."""
    try:
        results[domain_key]["status"] = "generating"
        demo = _load_demo_script(domain_key)
        date_display = datetime.now().strftime("%Y年%m月%d日")
        script = []
        for turn in demo:
            script.append({
                "speaker": turn["speaker"],
                "text": turn["text"].format(date=date_display),
            })

        date_str = datetime.now().strftime("%Y%m%d")
        domain_dir = os.path.join(OUTPUT_ROOT, date_str, domain_key)
        os.makedirs(domain_dir, exist_ok=True)
        output_path = os.path.join(domain_dir, f"podcast_{date_str}.mp3")

        result = generate_audio_sync(script, output_path)

        # Get duration
        duration = 0
        import subprocess
        try:
            proc = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                result,
            ], capture_output=True, text=True)
            duration = float(proc.stdout.strip())
        except Exception:
            pass

        results[domain_key] = {
            "status": "done",
            "audio_url": f"/audio/{date_str}/{domain_key}/podcast_{date_str}.mp3",
            "audio_path": result,
            "turns": len(script),
            "duration": _format_duration(duration),
            "duration_sec": round(duration, 1),
            "name": domain_cfg.get("name", domain_key),
            "emoji": domain_cfg.get("emoji", ""),
            "script": script,
            "summaries": [],
        }
    except Exception as e:
        results[domain_key] = {
            "status": "error",
            "error": str(e),
            "name": domain_cfg.get("name", domain_key),
            "emoji": domain_cfg.get("emoji", ""),
        }


def _run_real_thread(domain_key: str, domain_cfg: dict, task_id: str, results: dict):
    """Background thread: generate real podcast for one domain (needs API key)."""
    try:
        results[domain_key]["status"] = "generating"

        from fetcher import FETCHER_REGISTRY
        from script_generator import _detect_provider, generate_script

        async def _pipeline():
            fetcher_cls = FETCHER_REGISTRY.get(domain_key)
            if not fetcher_cls:
                raise ValueError(f"未知领域: {domain_key}")

            digest = await fetcher_cls().fetch()
            if not digest.items:
                raise ValueError("未获取到新闻")

            script, summaries = generate_script(
                digest.to_prompt_context(),
                domain_name=domain_cfg.get("name", domain_key),
                domain_prompt_extra=domain_cfg.get("prompt_extra", ""),
            )

            date_str = datetime.now().strftime("%Y%m%d")
            domain_dir = os.path.join(OUTPUT_ROOT, date_str, domain_key)
            os.makedirs(domain_dir, exist_ok=True)
            output_path = os.path.join(domain_dir, f"podcast_{date_str}.mp3")

            from audio_generator import generate_audio as gen_audio
            audio_result = await gen_audio(script, output_path)
            return audio_result, script, summaries, digest

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result, script, summaries, digest = loop.run_until_complete(_pipeline())
        loop.close()

        duration = 0
        import subprocess
        try:
            proc = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                result,
            ], capture_output=True, text=True)
            duration = float(proc.stdout.strip())
        except Exception:
            pass

        date_str = datetime.now().strftime("%Y%m%d")
        results[domain_key] = {
            "status": "done",
            "audio_url": f"/audio/{date_str}/{domain_key}/podcast_{date_str}.mp3",
            "audio_path": result,
            "turns": len(script),
            "duration": _format_duration(duration),
            "duration_sec": round(duration, 1),
            "name": domain_cfg.get("name", domain_key),
            "emoji": domain_cfg.get("emoji", ""),
            "script": script,
            "summaries": summaries,
            "digest_items": [{"title": it.title, "description": it.description, "stars": it.stars, "language": it.language} for it in digest.items],
        }
    except Exception as e:
        results[domain_key] = {
            "status": "error",
            "error": str(e),
            "name": domain_cfg.get("name", domain_key),
            "emoji": domain_cfg.get("emoji", ""),
        }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return _HTML


@app.route("/api/domains")
def get_domains():
    """Return domain list from config.yaml."""
    cfg = _load_config()
    domains = []
    for key, d in cfg.get("domains", {}).items():
        domains.append({
            "key": key,
            "name": d.get("name", key),
            "description": d.get("description", ""),
            "emoji": d.get("emoji", ""),
            "enabled": d.get("enabled", False),
        })
    # Check for API keys
    has_api_key = bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    return jsonify({
        "domains": domains,
        "has_api_key": has_api_key,
        "llm_provider": os.environ.get("LLM_PROVIDER", "auto"),
    })


@app.route("/api/generate", methods=["POST"])
def start_generation():
    """Start background generation for selected domains."""
    data = request.get_json() or {}
    selected = data.get("domains", [])
    use_demo = data.get("demo", False)

    if not selected:
        return jsonify({"error": "请至少选择一个领域"}), 400

    cfg = _load_config()
    domains_cfg = cfg.get("domains", {})

    task_id = str(_task_counter[0])
    _task_counter[0] += 1

    results = {}
    threads = []

    for domain_key in selected:
        domain_cfg = domains_cfg.get(domain_key, {})
        results[domain_key] = {"status": "pending", "name": domain_cfg.get("name", domain_key), "emoji": domain_cfg.get("emoji", "")}

        if use_demo:
            t = threading.Thread(
                target=_run_demo_thread,
                args=(domain_key, domain_cfg, task_id, results),
                daemon=True,
            )
        else:
            t = threading.Thread(
                target=_run_real_thread,
                args=(domain_key, domain_cfg, task_id, results),
                daemon=True,
            )
        threads.append(t)
        t.start()

    _tasks[task_id] = {
        "results": results,
        "threads": threads,
        "total": len(selected),
        "demo": use_demo,
        "started_at": datetime.now().isoformat(),
    }

    return jsonify({"task_id": task_id})


@app.route("/api/status/<task_id>")
def get_status(task_id: str):
    """Poll generation progress."""
    task = _tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    results = task["results"]
    done_count = sum(1 for r in results.values() if r["status"] in ("done", "error"))
    all_done = done_count >= task["total"]

    return jsonify({
        "total": task["total"],
        "done": done_count,
        "all_done": all_done,
        "demo": task["demo"],
        "notify_results": task.get("notify_results"),
        "notify_error": task.get("notify_error"),
        "results": {
            k: {
                "status": v["status"],
                "name": v.get("name", k),
                "emoji": v.get("emoji", ""),
                "audio_url": v.get("audio_url", ""),
                "turns": v.get("turns", 0),
                "duration": v.get("duration", ""),
                "duration_sec": v.get("duration_sec", 0),
                "error": v.get("error", ""),
                "script": v.get("script", []),
                "summaries": v.get("summaries", []),
            }
            for k, v in results.items()
        },
    })


@app.route("/audio/<path:filepath>")
def serve_audio(filepath: str):
    """Serve generated MP3 files."""
    full_path = os.path.join(OUTPUT_ROOT, filepath)
    if not os.path.exists(full_path):
        return jsonify({"error": "文件不存在"}), 404
    return send_file(full_path, mimetype="audio/mpeg")


@app.route("/api/notify/config")
def get_notify_config():
    """Return which notification channels are configured."""
    telegram_ok = bool(
        os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")
    )
    wechat_ok = bool(
        os.environ.get("WX_APPID") and os.environ.get("WX_SECRET")
        and os.environ.get("WX_OPENID") and os.environ.get("WX_TEMPLATE_ID")
    )
    feishu_ok = bool(
        os.environ.get("FEISHU_APP_ID") and os.environ.get("FEISHU_APP_SECRET")
        and os.environ.get("FEISHU_RECEIVE_ID")
    )
    return jsonify({
        "telegram": telegram_ok,
        "wechat": wechat_ok,
        "feishu": feishu_ok,
    })


@app.route("/api/notify/<task_id>", methods=["POST"])
def trigger_notify(task_id: str):
    """Push generated podcast results to configured notification channels (sync).

    Accepts optional JSON body:
      {"feishu": {"app_id": "...", "app_secret": "...", "receive_id": "..."}}
    """
    task = _tasks.get(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    results = task["results"]
    all_done = all(r["status"] in ("done", "error") for r in results.values())
    if not all_done:
        return jsonify({"error": "生成尚未完成"}), 400

    from notifier import notify_multi_domain
    date_str = datetime.now().strftime("%Y年%m月%d日")

    domain_results = []
    for domain_key, r in results.items():
        if r["status"] != "done":
            continue
        audio_path = r.get("audio_path", "")
        domain_results.append({
            "domain": domain_key,
            "name": r.get("name", domain_key),
            "audio_path": audio_path,
            "script": r.get("script", []),
            "repo_summaries": r.get("summaries", []),
            "digest_items": r.get("digest_items", []),
        })

    if not domain_results:
        return jsonify({"error": "没有已完成的领域"}), 400

    # Parse optional Feishu credentials from request body
    feishu_creds = {}
    try:
        body = request.get_json(silent=True) or {}
        feishu_creds = body.get("feishu", {})
    except Exception:
        pass

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        notify_results = loop.run_until_complete(
            notify_multi_domain(
                domain_results,
                date_str=date_str,
                feishu_creds=feishu_creds if feishu_creds else None,
            )
        )
        loop.close()

        task["notify_results"] = {
            "telegram": bool(notify_results.get("telegram")),
            "wechat": bool(notify_results.get("wechat")),
            "feishu": bool(notify_results.get("feishu")),
        }
        return jsonify({
            "status": "done",
            "results": task["notify_results"],
        })
    except Exception as e:
        task["notify_error"] = str(e)
        return jsonify({"status": "error", "error": str(e)}), 500


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TayPoadcast — AI 播客</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=LXGW+WenKai:wght@400;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg-page-top: #f5efe0;
  --bg-page-bottom: #ede4d3;
  --bg-card: #faf5eb;
  --bg-card-hover: #f7f1e6;
  --bg-elevated: #faf5eb;
  --border: #d4c5b0;
  --border-light: #e0d7c5;
  --border-active: #6b8a7a;
  --text-primary: #3d3226;
  --text-secondary: #8b7355;
  --text-muted: #b8a48e;
  --accent: #6b8a7a;
  --accent-dark: #5a7a6a;
  --accent-glow: rgba(107,138,122,.25);
  --accent-rose: #9b6a72;
  --accent-rose-bg: rgba(155,106,114,.08);
  --accent-slate: #5a7a8a;
  --accent-slate-bg: rgba(90,122,138,.08);
  --success: #6b8a7a;
  --error: #c97b6b;
  --radius-sm: 4px;
  --radius: 6px;
  --radius-lg: 8px;
  --font-display: "Noto Serif SC", "Songti SC", "SimSun", serif;
  --font-body: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  --ease-out: cubic-bezier(.34,1.56,.64,1);
  --ease-spring: cubic-bezier(.22,.61,.36,1);
}
*{margin:0;padding:0;box-sizing:border-box}
html{background:var(--bg-page-top)}
body{
  font-family:var(--font-body);
  background:linear-gradient(180deg,var(--bg-page-top) 0%,var(--bg-page-bottom) 100%);
  color:var(--text-primary);
  min-height:100vh;
  line-height:1.8;
  -webkit-font-smoothing:antialiased;
  position:relative;
}
/* Paper texture overlay */
body::before{
  content:"";
  position:fixed;inset:0;pointer-events:none;z-index:0;
  opacity:.025;
  background:radial-gradient(circle at 20% 30%,#8b7355 1px,transparent 1px);
  background-size:4px 4px;
}

/* ── Header ── */
.header{
  text-align:center;
  padding:56px 24px 40px;
  position:relative;
}
.header::after{
  content:"";
  position:absolute;
  bottom:0;left:50%;transform:translateX(-50%);
  width:60px;height:2px;
  background:linear-gradient(90deg,transparent,var(--accent),transparent);
}
.header h1{
  font-family:var(--font-display);
  font-size:36px;
  font-weight:700;
  color:var(--text-primary);
  letter-spacing:.04em;
  margin-bottom:8px;
}
.header .subtitle{
  font-size:15px;
  color:var(--text-secondary);
  letter-spacing:.06em;
}

/* ── Container ── */
.container{max-width:640px;margin:0 auto;padding:0 24px 64px}

/* ── Domain cards ── */
.domains{display:flex;flex-direction:column;gap:10px;margin-bottom:32px}
.domain-card{
  display:flex;align-items:center;gap:14px;
  padding:16px 18px;
  background:var(--bg-card);
  border:1.5px solid var(--border);
  border-radius:var(--radius);
  cursor:pointer;
  transition:all .3s var(--ease-spring);
  user-select:none;position:relative;
}
.domain-card:hover{background:var(--bg-card-hover);transform:translateX(4px)}
.domain-card.selected{
  border-color:var(--border-active);
  background:linear-gradient(135deg,rgba(200,148,106,.08),rgba(200,148,106,.02));
  box-shadow:inset 0 0 0 1px rgba(200,148,106,.1),0 4px 20px var(--accent-glow);
}
.domain-card .emoji{font-size:26px;flex-shrink:0;width:36px;text-align:center;transition:transform .3s var(--ease-out)}
.domain-card.selected .emoji{transform:scale(1.15)}
.domain-card .info{flex:1;min-width:0}
.domain-card .name{font-family:var(--font-display);font-size:16px;font-weight:600;color:var(--text-primary);margin-bottom:2px}
.domain-card .desc{font-size:13px;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.domain-card .indicator{
  flex-shrink:0;width:20px;height:20px;
  border-radius:50%;border:2px solid var(--border);
  transition:all .3s var(--ease-out);
  display:flex;align-items:center;justify-content:center;
}
.domain-card.selected .indicator{
  border-color:var(--accent);background:var(--accent);
  box-shadow:0 0 12px var(--accent-glow);
}
.domain-card.selected .indicator::after{
  content:"";display:block;width:6px;height:4px;
  border-left:2px solid var(--bg-deep);border-bottom:2px solid var(--bg-deep);
  transform:rotate(-45deg) translateY(-1px);
}

/* ── Generate button ── */
.generate-wrap{margin-bottom:36px}
.generate-btn{
  width:100%;padding:18px;border:none;border-radius:var(--radius);
  background:linear-gradient(135deg,#b8805a,#9b6d48);
  color:#fff;font-family:var(--font-display);font-size:17px;font-weight:600;
  letter-spacing:.08em;cursor:pointer;
  transition:all .35s var(--ease-spring);
  position:relative;overflow:hidden;
}
.generate-btn::before{
  content:"";position:absolute;inset:0;
  background:linear-gradient(135deg,rgba(255,255,255,.08),transparent 60%);
  pointer-events:none;
}
.generate-btn:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 12px 36px rgba(200,148,106,.3)}
.generate-btn:active:not(:disabled){transform:translateY(0)}
.generate-btn:disabled{opacity:.55;cursor:not-allowed;filter:saturate(.5)}

/* ── Tab navigation ── */
.tab-nav{display:none;margin-bottom:24px;border-bottom:2px solid var(--border)}
.tab-nav.visible{display:flex;gap:0}
.tab-btn{
  flex:1;padding:12px 8px;background:none;border:none;
  color:var(--text-muted);font-family:var(--font-display);
  font-size:14px;font-weight:600;cursor:pointer;
  position:relative;transition:color .25s ease;
  letter-spacing:.04em;
}
.tab-btn:hover{color:var(--text-secondary)}
.tab-btn.active{color:var(--accent)}
.tab-btn.active::after{
  content:"";position:absolute;bottom:-2px;left:20%;right:20%;height:2px;
  background:var(--accent);border-radius:1px;
}

/* ── Tab panels ── */
.tab-panel{display:none;animation:fade-up .4s ease}
.tab-panel.active{display:block}

/* ── Results cards (audio tab) ── */
.results{display:flex;flex-direction:column;gap:10px;margin-bottom:20px}
.result-card{
  display:flex;align-items:center;gap:14px;
  padding:14px 16px;background:var(--bg-card);
  border-radius:var(--radius);border:1.5px solid var(--border);
  transition:all .4s ease;
}
.result-card.status-generating{border-left:3px solid #c8946a;animation:pulse-border 2s ease-in-out infinite}
.result-card.status-done{border-left:3px solid var(--success);background:linear-gradient(135deg,rgba(122,159,126,.06),transparent)}
.result-card.status-error{border-left:3px solid var(--error);background:linear-gradient(135deg,rgba(201,123,107,.06),transparent)}
@keyframes pulse-border{0%,100%{border-left-color:#c8946a}50%{border-left-color:#e0b88a}}
.result-emoji{font-size:24px;flex-shrink:0}
.result-info{flex:1;min-width:0}
.result-name{font-family:var(--font-display);font-size:15px;font-weight:600;margin-bottom:2px}
.result-meta{font-size:13px;color:var(--text-secondary)}

/* ── Play button ── */
.play-btn{
  flex-shrink:0;width:42px;height:42px;
  border-radius:50%;border:2px solid var(--border);
  background:transparent;color:var(--text-secondary);
  font-size:16px;cursor:pointer;display:none;
  align-items:center;justify-content:center;
  transition:all .25s var(--ease-out);
}
.play-btn.visible{display:flex}
.play-btn:hover{border-color:var(--accent);color:var(--accent);box-shadow:0 0 16px var(--accent-glow)}
.play-btn.playing{border-color:var(--accent);background:var(--accent);color:#fff}

/* ── Script viewer (文稿 tab) ── */
.script-viewer{font-size:15px;line-height:2;padding:8px 0}
.script-turn{display:flex;gap:12px;margin-bottom:14px;align-items:flex-start}
.script-turn .speaker-badge{
  flex-shrink:0;padding:2px 10px;border-radius:var(--radius-sm);
  font-family:var(--font-display);font-size:13px;font-weight:600;
  white-space:nowrap;margin-top:2px;
}
.script-turn .speaker-badge.xiaoxiao{background:rgba(201,123,139,.15);color:var(--accent-rose)}
.script-turn .speaker-badge.yunyang{background:rgba(123,156,201,.15);color:var(--accent-slate)}
.script-turn .turn-text{flex:1;color:var(--text-primary)}

/* ── Summaries (速览 tab) ── */
.summary-list{display:flex;flex-direction:column;gap:12px}
.summary-item{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius);padding:14px 16px;
}
.summary-item .repo-header{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.summary-item .repo-name{font-family:var(--font-display);font-size:15px;font-weight:600;color:var(--accent)}
.summary-item .repo-meta{font-size:12px;color:var(--text-muted);margin-left:auto;white-space:nowrap}
.summary-item .repo-desc{font-size:14px;color:var(--text-secondary);line-height:1.7}

/* ── Push section ── */
.push-section{display:none;margin-top:28px;padding-top:24px;border-top:1px solid var(--border)}
.push-section.visible{display:block;animation:fade-up .5s ease}
.push-section .push-title{
  font-family:var(--font-display);font-size:14px;color:var(--text-muted);
  margin-bottom:14px;letter-spacing:.04em;text-align:center;
}
.push-buttons{display:flex;gap:10px}
.push-btn{
  flex:1;padding:14px;border-radius:var(--radius);border:1.5px solid var(--border);
  background:var(--bg-card);color:var(--text-secondary);
  font-family:var(--font-display);font-size:14px;font-weight:600;
  cursor:pointer;transition:all .25s var(--ease-out);
  display:flex;align-items:center;justify-content:center;gap:8px;
}
.push-btn:hover:not(:disabled){border-color:var(--border-active);color:var(--text-primary)}
.push-btn:disabled{opacity:.4;cursor:not-allowed}
.push-btn.sent{border-color:var(--success);color:var(--success)}
.push-btn.failed{border-color:var(--error);color:var(--error)}
.push-btn .push-icon{font-size:18px}
.push-btn .push-label{font-size:13px}

.feishu-config{display:none;margin-top:12px;padding:14px 16px;background:rgba(200,148,106,.04);border-radius:8px;border:1px solid var(--border)}
.feishu-config.visible{display:block}
.feishu-config .config-title{font-size:13px;color:var(--text-secondary);margin-bottom:10px}
.feishu-config label{display:block;font-size:12px;color:var(--text-muted);margin-bottom:4px;margin-top:8px}
.feishu-config label:first-of-type{margin-top:0}
.feishu-config input{width:100%;padding:7px 10px;font-size:12px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:6px;color:var(--text-primary);box-sizing:border-box;font-family:var(--font-mono)}
.feishu-config input:focus{outline:none;border-color:var(--accent)}

/* ── Spinner ── */
.spinner{
  display:inline-block;width:12px;height:12px;
  border:2px solid rgba(200,148,106,.3);border-top-color:var(--accent);
  border-radius:50%;animation:spin .7s linear infinite;
  margin-right:6px;vertical-align:middle;
}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── Summary bar ── */
.summary-bar{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius);padding:14px 18px;
  text-align:center;font-size:14px;color:var(--text-secondary);
  display:none;animation:fade-up .5s ease;margin-bottom:20px;
}
.summary-bar .highlight{color:var(--accent);font-family:var(--font-display)}

/* ── Audio player ── */
.audio-player{
  display:none;width:100%;margin-top:16px;
  border-radius:var(--radius);background:var(--bg-card);
  outline:none;
}
.audio-player.visible{display:block}

/* ── Animations ── */
@keyframes fade-up{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.result-card{animation:fade-up .4s ease both}
.result-card:nth-child(1){animation-delay:0s}
.result-card:nth-child(2){animation-delay:.05s}
.result-card:nth-child(3){animation-delay:.1s}
.result-card:nth-child(4){animation-delay:.15s}

/* ── Responsive ── */
@media(max-width:480px){
  .header{padding:40px 20px 32px}
  .header h1{font-size:28px}
  .domain-card{padding:14px}
  .domain-card .desc{font-size:12px}
  .push-buttons{flex-direction:column}
}
</style>
</head>
<body>

<header class="header">
  <h1>TayPoadcast</h1>
  <p class="subtitle">每日 AI 播客 · 收听与阅读</p>
</header>

<div class="container">

  <div class="domains" id="domains"></div>

  <div class="generate-wrap">
    <button class="generate-btn" id="generateBtn" onclick="startGeneration()">
      生成播客
    </button>
  </div>

  <!-- Summary bar -->
  <div class="summary-bar" id="summaryBar"></div>

  <!-- Tab navigation -->
  <nav class="tab-nav" id="tabNav">
    <button class="tab-btn active" data-tab="audio" onclick="switchTab('audio')">音频</button>
    <button class="tab-btn" data-tab="script" onclick="switchTab('script')">文稿</button>
    <button class="tab-btn" data-tab="summary" onclick="switchTab('summary')">速览</button>
  </nav>

  <!-- Tab: Audio -->
  <div class="tab-panel active" id="panel-audio">
    <div class="results" id="results"></div>
  </div>

  <!-- Tab: Script -->
  <div class="tab-panel" id="panel-script">
    <div class="script-viewer" id="scriptContent">
      <div class="empty-state">生成播客后将在此显示对话文稿</div>
    </div>
  </div>

  <!-- Tab: Summaries -->
  <div class="tab-panel" id="panel-summary">
    <div class="summary-list" id="summaryContent">
      <div class="empty-state">生成播客后将在此显示内容速览</div>
    </div>
  </div>

  <!-- Push to channels -->
  <div class="push-section" id="pushSection">
    <div class="push-title">推送到通讯软件</div>
    <div class="push-buttons" id="pushButtons"></div>
    <div class="feishu-config" id="feishuConfig">
      <div class="config-title">飞书机器人配置</div>
      <label>APP ID</label>
      <input type="text" id="feishuAppId" placeholder="cli_xxxxxxxxxxxxxxxx" autocomplete="off">
      <label>APP SECRET</label>
      <input type="password" id="feishuAppSecret" placeholder="飞书应用 Secret" autocomplete="off">
      <label>RECEIVE ID</label>
      <input type="text" id="feishuReceiveId" placeholder="ou_xxxxxxxx 或 chat_id" autocomplete="off">
    </div>
  </div>

  <audio class="audio-player" id="audioPlayer" controls onended="onAudioEnded()"></audio>

</div>

<script>
let selectedDomains = new Set();
let pollTimer = null;
let currentAudioDomain = null;
let currentTaskId = null;
let completedData = null;
let notifyChannels = {};

// Init
fetch('/api/domains')
  .then(r => r.json())
  .then(data => {
    const container = document.getElementById('domains');
    data.domains.forEach(d => {
      const card = document.createElement('div');
      card.className = 'domain-card' + (d.enabled ? ' selected' : '');
      card.dataset.key = d.key;
      card.onclick = () => toggleDomain(d.key, card);
      card.innerHTML = `
        <div class="emoji">${d.emoji}</div>
        <div class="info">
          <div class="name">${d.name}</div>
          <div class="desc">${d.description}</div>
        </div>
        <div class="indicator"></div>
      `;
      container.appendChild(card);
      if (d.enabled) selectedDomains.add(d.key);
    });
  });

fetch('/api/notify/config')
  .then(r => r.json())
  .then(data => { notifyChannels = data; });

function toggleDomain(key, card) {
  // Single-domain mode: deselect all others first
  const wasSelected = selectedDomains.has(key);
  selectedDomains.clear();
  document.querySelectorAll('.domain-card').forEach(c => c.classList.remove('selected'));
  if (!wasSelected) {
    selectedDomains.add(key);
    card.classList.add('selected');
  }
}

function switchTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tabName));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + tabName));
}

function startGeneration() {
  if (selectedDomains.size === 0) { alert('请至少选择一个领域'); return; }

  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  btn.textContent = '生成中...';

  document.getElementById('tabNav').classList.remove('visible');
  document.getElementById('pushSection').classList.remove('visible');
  document.getElementById('results').innerHTML = '';
  document.getElementById('scriptContent').innerHTML = '<div class="empty-state">生成播客后将在此显示对话文稿</div>';
  document.getElementById('summaryContent').innerHTML = '<div class="empty-state">生成播客后将在此显示内容速览</div>';
  document.getElementById('summaryBar').style.display = 'none';
  switchTab('audio');
  completedData = null;

  const resultsDiv = document.getElementById('results');
  selectedDomains.forEach(key => {
    const card = document.querySelector(`[data-key="${key}"]`);
    const name = card ? card.querySelector('.name').textContent : key;
    const emoji = card ? card.querySelector('.emoji').textContent : '';
    resultsDiv.innerHTML += `
      <div class="result-card status-pending" id="result-${key}">
        <div class="result-emoji">${emoji}</div>
        <div class="result-info">
          <div class="result-name">${name}</div>
          <div class="result-meta">排队中...</div>
        </div>
        <button class="play-btn" id="play-${key}" onclick="togglePlay('${key}')">▶</button>
      </div>
    `;
  });

  fetch('/api/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ domains: Array.from(selectedDomains), demo: false })
  })
  .then(r => r.json())
  .then(data => {
    if (data.error) { alert(data.error); btn.disabled = false; btn.textContent = '生成播客'; return; }
    currentTaskId = data.task_id;
    pollStatus(data.task_id, btn);
  })
  .catch(err => {
    alert('请求失败: ' + err);
    btn.disabled = false; btn.textContent = '生成播客';
  });
}

function pollStatus(taskId, btn) {
  pollTimer = setInterval(() => {
    fetch('/api/status/' + taskId)
      .then(r => r.json())
      .then(data => {
        completedData = data;
        for (const [key, r] of Object.entries(data.results)) {
          const card = document.getElementById('result-' + key);
          if (!card) continue;
          card.className = 'result-card status-' + r.status;
          const metaDiv = card.querySelector('.result-meta');
          const playBtn = document.getElementById('play-' + key);

          if (r.status === 'generating') {
            metaDiv.innerHTML = '<span class="spinner"></span> 正在抓取热点并生成脚本...';
          } else if (r.status === 'done') {
            metaDiv.innerHTML = `<span style="color:var(--success)">${r.turns} 轮对话 · ${r.duration}</span>`;
            playBtn.classList.add('visible');
            playBtn.dataset.url = r.audio_url;
          } else if (r.status === 'error') {
            metaDiv.innerHTML = `<span style="color:var(--error)">生成失败</span>`;
            const errEl = document.createElement('div');
            errEl.style.cssText = 'color:var(--error);font-size:12px;margin-top:4px';
            errEl.textContent = r.error;
            card.appendChild(errEl);
          }
        }

        if (data.all_done) {
          clearInterval(pollTimer);
          btn.disabled = false; btn.textContent = '重新生成';
          document.getElementById('tabNav').classList.add('visible');
          renderScripts(data);
          renderSummaries(data);
          renderPushButtons(data);
          switchTab('audio');

          const doneCount = Object.values(data.results).filter(r => r.status === 'done').length;
          const totalSec = Object.values(data.results).reduce((s, r) => s + (r.duration_sec || 0), 0);
          const minutes = Math.floor(totalSec / 60), seconds = Math.round(totalSec % 60);
          const bar = document.getElementById('summaryBar');
          bar.style.display = 'block';
          bar.innerHTML = `<span class="highlight">${doneCount}/${data.total}</span> 个领域生成完成 · 总时长 <span class="highlight">${minutes}分${seconds}秒</span>`;
        }
      });
  }, 1500);
}

function renderScripts(data) {
  const container = document.getElementById('scriptContent');
  let html = '';
  for (const [key, r] of Object.entries(data.results)) {
    if (r.status !== 'done' || !r.script || !r.script.length) continue;
    if (Object.keys(data.results).length > 1) {
      html += `<div style="font-family:var(--font-display);font-size:16px;font-weight:600;margin:16px 0 8px;color:var(--accent)">${r.emoji} ${r.name}</div>`;
    }
    r.script.forEach(turn => {
      const cls = turn.speaker === '晓晓' ? 'xiaoxiao' : 'yunyang';
      html += `<div class="script-turn"><span class="speaker-badge ${cls}">${turn.speaker}</span><span class="turn-text">${turn.text}</span></div>`;
    });
  }
  container.innerHTML = html || '<div class="empty-state">暂无文稿</div>';
}

function renderSummaries(data) {
  const container = document.getElementById('summaryContent');
  let html = '';
  for (const [key, r] of Object.entries(data.results)) {
    if (r.status !== 'done') continue;
    const summaries = r.summaries || [];
    if (summaries.length === 0) continue;
    if (Object.keys(data.results).length > 1) {
      html += `<div style="font-family:var(--font-display);font-size:16px;font-weight:600;margin:8px 0 12px;color:var(--accent)">${r.emoji} ${r.name}</div>`;
    }
    summaries.forEach(s => {
      const stars = s.stars ? ` ⭐${s.stars}` : '';
      const lang = s.lang ? ` · ${s.lang}` : '';
      html += `
        <div class="summary-item">
          <div class="repo-header">
            <span class="repo-name">${s.name || '?'}</span>
            <span class="repo-meta">${stars}${lang}</span>
          </div>
          <div class="repo-desc">${s.summary || ''}</div>
        </div>
      `;
    });
  }
  container.innerHTML = html || '<div class="empty-state">暂无速览内容</div>';
}

function renderPushButtons(data) {
  const section = document.getElementById('pushSection');
  const container = document.getElementById('pushButtons');
  const hasDone = Object.values(data.results).some(r => r.status === 'done');
  if (!hasDone) { section.classList.remove('visible'); return; }

  // Fetch notify config directly to avoid race condition
  fetch('/api/notify/config')
    .then(r => r.json())
    .then(cfg => {
      section.classList.add('visible');
      let html = '';
      if (cfg.telegram) {
        html += '<button class="push-btn" id="pushTelegram" onclick="pushNotify(currentTaskId)"><span class="push-icon">✈</span><span class="push-label">推送到 Telegram</span></button>';
      }
      if (cfg.wechat) {
        html += '<button class="push-btn" id="pushWechat" onclick="pushNotify(currentTaskId)"><span class="push-icon">💬</span><span class="push-label">推送到微信</span></button>';
      }
      // Feishu: always show (user enters credentials in form)
      html += '<button class="push-btn" id="pushFeishu" onclick="toggleFeishuConfig()"><span class="push-icon">📄</span><span class="push-label">推送到飞书</span></button>';
      if (!html) {
        html = '<div style=\"text-align:center;color:var(--text-muted);font-size:13px;padding:8px\">未配置通知渠道。设置环境变量后重启服务。</div>';
      }
      container.innerHTML = html;
    });
}

function toggleFeishuConfig() {
  const cfgDiv = document.getElementById('feishuConfig');
  const isVisible = cfgDiv.classList.contains('visible');
  if (isVisible) {
    cfgDiv.classList.remove('visible');
    return;
  }
  // Show config form
  cfgDiv.classList.add('visible');
  // Change button to send action
  const btn = document.getElementById('pushFeishu');
  btn.onclick = function() { pushFeishuWithConfig(currentTaskId); };
  btn.querySelector('.push-label').textContent = '发送到飞书 →';
}

function pushNotify(taskId) {
  const buttons = document.querySelectorAll('.push-btn');
  if (buttons.length === 0) return;
  buttons.forEach(b => { b.disabled = true; b.querySelector('.push-label').textContent = '发送中...'; });

  fetch('/api/notify/' + taskId, { method: 'POST' })
    .then(r => r.json())
    .then(resp => {
      if (resp.status === 'done' && resp.results) {
        const r = resp.results;
        // Update each button individually based on channel result
        const channelMap = [
          { btnId: 'pushTelegram', key: 'telegram', label: '推送到 Telegram' },
          { btnId: 'pushWechat', key: 'wechat', label: '推送到微信' },
          { btnId: 'pushFeishu', key: 'feishu', label: '推送到飞书' },
        ];
        channelMap.forEach(ch => {
          const btn = document.getElementById(ch.btnId);
          if (!btn) return;
          if (r[ch.key] === true) {
            btn.classList.add('sent');
            btn.querySelector('.push-label').textContent = '已发送 ✓';
          } else if (r.hasOwnProperty(ch.key)) {
            btn.classList.add('failed');
            btn.querySelector('.push-label').textContent = '发送失败 ✗';
          }
        });
      } else if (resp.error) {
        buttons.forEach(b => {
          b.classList.add('failed');
          b.querySelector('.push-label').textContent = '失败: ' + resp.error.substring(0, 30);
        });
      } else {
        buttons.forEach(b => {
          b.classList.add('failed');
          b.querySelector('.push-label').textContent = '未知错误';
        });
      }
      setTimeout(() => {
        buttons.forEach(b => {
          b.disabled = false;
          b.classList.remove('sent', 'failed');
          const labelMap = {
            'pushTelegram': '推送到 Telegram',
            'pushWechat': '推送到微信',
            'pushFeishu': '推送到飞书',
          };
          b.querySelector('.push-label').textContent = labelMap[b.id] || '推送';
        });
      }, 8000);
    })
    .catch(() => {
      buttons.forEach(b => {
        b.classList.add('failed');
        b.querySelector('.push-label').textContent = '请求失败 ✗';
        b.disabled = false;
      });
    });
}

function pushFeishuWithConfig(taskId) {
  const appId = document.getElementById('feishuAppId').value.trim();
  const appSecret = document.getElementById('feishuAppSecret').value.trim();
  const receiveId = document.getElementById('feishuReceiveId').value.trim();

  if (!appId || !appSecret || !receiveId) {
    alert('请填写完整的飞书配置：APP ID、APP SECRET、RECEIVE ID');
    return;
  }

  const btn = document.getElementById('pushFeishu');
  btn.disabled = true;
  btn.querySelector('.push-label').textContent = '发送中...';

  fetch('/api/notify/' + taskId, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      feishu: {
        app_id: appId,
        app_secret: appSecret,
        receive_id: receiveId,
        receive_id_type: 'open_id',
      }
    })
  })
    .then(r => r.json())
    .then(resp => {
      if (resp.status === 'done' && resp.results && resp.results.feishu) {
        btn.classList.add('sent');
        btn.querySelector('.push-label').textContent = '飞书已发送 ✓';
      } else {
        btn.classList.add('failed');
        btn.querySelector('.push-label').textContent = '飞书发送失败 ✗';
        btn.disabled = false;
      }
      setTimeout(() => {
        btn.disabled = false;
        btn.classList.remove('sent', 'failed');
        btn.querySelector('.push-label').textContent = '推送到飞书';
        btn.onclick = function() { toggleFeishuConfig(); };
      }, 8000);
    })
    .catch(() => {
      btn.classList.add('failed');
      btn.querySelector('.push-label').textContent = '请求失败 ✗';
      btn.disabled = false;
    });
}

function togglePlay(domainKey) {
  const playBtn = document.getElementById('play-' + domainKey);
  const audioUrl = playBtn.dataset.url;
  if (!audioUrl) return;
  const player = document.getElementById('audioPlayer');

  if (currentAudioDomain === domainKey && !player.paused) {
    player.pause();
    playBtn.textContent = '▶'; playBtn.classList.remove('playing');
    currentAudioDomain = null;
  } else {
    if (currentAudioDomain) {
      const prevBtn = document.getElementById('play-' + currentAudioDomain);
      if (prevBtn) { prevBtn.textContent = '▶'; prevBtn.classList.remove('playing'); }
    }
    player.src = audioUrl;
    player.classList.add('visible');
    player.load();
    player.play().catch(e => {
      console.error('Audio play failed:', e);
      playBtn.textContent = '▶'; playBtn.classList.remove('playing');
      currentAudioDomain = null;
    });
    playBtn.textContent = '⏸'; playBtn.classList.add('playing');
    currentAudioDomain = domainKey;
  }
}

function onAudioEnded() {
  if (currentAudioDomain) {
    const btn = document.getElementById('play-' + currentAudioDomain);
    if (btn) { btn.textContent = '▶'; btn.classList.remove('playing'); }
    currentAudioDomain = null;
  }
}
</script>

</body>
</html>"""

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════╗
    ║   TayPoadcast Web UI                ║
    ║   播客控制中心                       ║
    ╚══════════════════════════════════════╝
    """)
    print("  🌐 打开浏览器访问: http://localhost:5001")
    print()
    app.run(host="0.0.0.0", port=5001, debug=False)
