#!/usr/bin/env python3
"""Web UI for TayPoadcast — Flask-based podcast control center.

Usage:
    pip install flask
    python web_app.py
    # Open http://localhost:5000
"""

import asyncio
import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

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
            "turns": len(script),
            "duration": _format_duration(duration),
            "duration_sec": round(duration, 1),
            "name": domain_cfg.get("name", domain_key),
            "emoji": domain_cfg.get("emoji", ""),
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
            result = await gen_audio(script, output_path)
            return result, script

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result, script = loop.run_until_complete(_pipeline())
        loop.close()

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

        date_str = datetime.now().strftime("%Y%m%d")
        results[domain_key] = {
            "status": "done",
            "audio_url": f"/audio/{date_str}/{domain_key}/podcast_{date_str}.mp3",
            "turns": len(script),
            "duration": _format_duration(duration),
            "duration_sec": round(duration, 1),
            "name": domain_cfg.get("name", domain_key),
            "emoji": domain_cfg.get("emoji", ""),
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
    use_demo = data.get("demo", True)

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


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TayPoadcast — AI 播客控制中心</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0f0f14;color:#e0e0e0;min-height:100vh}
.header{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:32px 24px;text-align:center;border-bottom:1px solid #2a2a3e}
.header h1{font-size:28px;margin-bottom:8px;background:linear-gradient(135deg,#a78bfa,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header p{color:#888;font-size:14px}
.container{max-width:800px;margin:0 auto;padding:24px}
.section{margin-bottom:32px}
.section-title{font-size:18px;font-weight:600;margin-bottom:16px;color:#a78bfa}
.domains{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}
.domain-card{background:#1a1a28;border:2px solid #2a2a3e;border-radius:12px;padding:16px;cursor:pointer;transition:all .2s;display:flex;align-items:flex-start;gap:12px}
.domain-card:hover{border-color:#3a3a5e}
.domain-card.selected{border-color:#a78bfa;background:#1a1a30}
.domain-card .emoji{font-size:28px;flex-shrink:0;width:40px;text-align:center}
.domain-card .info{flex:1}
.domain-card .name{font-size:16px;font-weight:600;margin-bottom:4px}
.domain-card .desc{font-size:13px;color:#888}
.domain-card .check{flex-shrink:0;width:24px;height:24px;border-radius:6px;border:2px solid #555;display:flex;align-items:center;justify-content:center;transition:all .2s}
.domain-card.selected .check{background:#a78bfa;border-color:#a78bfa}
.domain-card.selected .check::after{content:"✓";color:#fff;font-size:14px;font-weight:700}
.mode-selector{display:flex;gap:12px;margin-bottom:16px}
.mode-btn{flex:1;padding:14px;border-radius:10px;border:2px solid #2a2a3e;background:#1a1a28;color:#ccc;font-size:14px;cursor:pointer;text-align:center;transition:all .2s}
.mode-btn:hover{border-color:#3a3a5e}
.mode-btn.active{border-color:#60a5fa;background:#1a1a32;color:#fff}
.mode-btn .mode-title{font-weight:600;margin-bottom:4px}
.mode-btn .mode-desc{font-size:12px;color:#888}
.generate-btn{width:100%;padding:18px;border-radius:12px;border:none;background:linear-gradient(135deg,#7c3aed,#4f46e5);color:#fff;font-size:18px;font-weight:700;cursor:pointer;transition:all .2s;letter-spacing:1px}
.generate-btn:hover{transform:translateY(-1px);box-shadow:0 8px 30px rgba(124,58,237,.3)}
.generate-btn:active{transform:translateY(0)}
.generate-btn:disabled{opacity:.5;cursor:not-allowed;transform:none}
.results{margin-top:24px}
.result-card{background:#1a1a28;border-radius:12px;padding:16px;margin-bottom:8px;display:flex;align-items:center;gap:12px;transition:all .3s}
.result-card.status-pending{opacity:.5}
.result-card.status-generating{border-left:3px solid #f59e0b}
.result-card.status-done{border-left:3px solid #22c55e}
.result-card.status-error{border-left:3px solid #ef4444}
.result-emoji{font-size:24px;flex-shrink:0}
.result-info{flex:1}
.result-name{font-size:15px;font-weight:600;margin-bottom:2px}
.result-meta{font-size:13px;color:#888}
.result-status{font-size:13px;font-weight:500}
.result-status.done{color:#22c55e}
.result-status.error{color:#ef4444}
.result-status.generating{color:#f59e0b}
.play-btn{flex-shrink:0;width:44px;height:44px;border-radius:50%;border:none;background:#a78bfa;color:#fff;font-size:18px;cursor:pointer;display:none;align-items:center;justify-content:center;transition:all .2s}
.play-btn.visible{display:flex}
.play-btn:hover{background:#8b5cf6;transform:scale(1.05)}
.play-btn.playing{background:#ef4444}
.audio-player{display:none}
.error-text{color:#ef4444;font-size:13px;margin-top:4px}
.api-notice{background:#1a1a28;border:1px solid #f59e0b;border-radius:10px;padding:14px;margin-top:12px;font-size:13px;color:#f59e0b;display:none}
.summary-bar{background:#1a1a28;border-radius:12px;padding:14px;margin-bottom:24px;text-align:center;font-size:14px;color:#888;display:none}
.spinner{display:inline-block;width:14px;height:14px;border:2px solid #f59e0b;border-top-color:transparent;border-radius:50%;animation:spin .8s linear infinite;margin-right:6px;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:600px){.domains{grid-template-columns:1fr}.mode-selector{flex-direction:column}}
</style>
</head>
<body>

<div class="header">
  <h1>TayPoadcast</h1>
  <p>AI 播客控制中心 — 选择领域，一键生成你的专属播客</p>
</div>

<div class="container">

  <!-- Domain Selection -->
  <div class="section">
    <div class="section-title">📻 选择领域</div>
    <div class="domains" id="domains"></div>
  </div>

  <!-- Mode Selection -->
  <div class="section">
    <div class="section-title">⚙️ 生成模式</div>
    <div class="mode-selector">
      <button class="mode-btn active" data-mode="demo" onclick="selectMode('demo')">
        <div class="mode-title">🎭 演示脚本</div>
        <div class="mode-desc">无需 API Key，立即可用</div>
      </button>
      <button class="mode-btn" data-mode="real" id="realModeBtn" onclick="selectMode('real')">
        <div class="mode-title">🔥 真实数据</div>
        <div class="mode-desc">实时抓取热点，需 API Key</div>
      </button>
    </div>
    <div class="api-notice" id="apiNotice">
      ⚠️ 未检测到 LLM API Key (DEEPSEEK_API_KEY / ANTHROPIC_API_KEY)。<br>
      真实数据模式需要 LLM 才能生成脚本。请设置环境变量后重启服务。
    </div>
  </div>

  <!-- Generate Button -->
  <button class="generate-btn" id="generateBtn" onclick="startGeneration()">
    🚀 生成播客
  </button>

  <!-- Summary -->
  <div class="summary-bar" id="summaryBar"></div>

  <!-- Results -->
  <div class="results" id="results"></div>

  <!-- Hidden audio player -->
  <audio class="audio-player" id="audioPlayer" controls onended="onAudioEnded()"></audio>

</div>

<script>
let selectedDomains = new Set();
let currentMode = 'demo';
let pollTimer = null;
let currentAudioDomain = null;

// Initialize
fetch('/api/domains')
  .then(r => r.json())
  .then(data => {
    // Render domain cards
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
        <div class="check"></div>
      `;
      container.appendChild(card);
      if (d.enabled) selectedDomains.add(d.key);
    });

    // Show/hide real mode and API notice
    document.getElementById('realModeBtn').style.display = data.has_api_key ? '' : 'none';
    if (!data.has_api_key) {
      document.getElementById('apiNotice').style.display = 'block';
      currentMode = 'demo';
    }
  });

function toggleDomain(key, card) {
  if (selectedDomains.has(key)) {
    selectedDomains.delete(key);
    card.classList.remove('selected');
  } else {
    selectedDomains.add(key);
    card.classList.add('selected');
  }
}

function selectMode(mode) {
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
}

function startGeneration() {
  if (selectedDomains.size === 0) {
    alert('请至少选择一个领域');
    return;
  }

  const btn = document.getElementById('generateBtn');
  btn.disabled = true;
  btn.textContent = '⏳ 生成中...';

  document.getElementById('results').innerHTML = '';
  document.getElementById('summaryBar').style.display = 'none';

  // Show pending cards immediately
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
          <div class="result-meta">等待中...</div>
        </div>
        <button class="play-btn" id="play-${key}" onclick="togglePlay('${key}')">▶</button>
      </div>
    `;
  });

  // Start generation
  fetch('/api/generate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      domains: Array.from(selectedDomains),
      demo: currentMode === 'demo'
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.error) {
      alert(data.error);
      btn.disabled = false;
      btn.textContent = '🚀 生成播客';
      return;
    }
    pollStatus(data.task_id, btn);
  })
  .catch(err => {
    alert('请求失败: ' + err);
    btn.disabled = false;
    btn.textContent = '🚀 生成播客';
  });
}

function pollStatus(taskId, btn) {
  pollTimer = setInterval(() => {
    fetch('/api/status/' + taskId)
      .then(r => r.json())
      .then(data => {
        // Update result cards
        for (const [key, r] of Object.entries(data.results)) {
          const card = document.getElementById('result-' + key);
          if (!card) continue;

          card.className = 'result-card status-' + r.status;

          const metaDiv = card.querySelector('.result-meta');
          const playBtn = document.getElementById('play-' + key);

          if (r.status === 'generating') {
            metaDiv.innerHTML = '<span class="spinner"></span> 生成中...';
          } else if (r.status === 'done') {
            metaDiv.innerHTML = `<span class="result-status done">✅ ${r.turns} 轮对话 · ${r.duration}</span>`;
            playBtn.classList.add('visible');
            playBtn.dataset.url = r.audio_url;
          } else if (r.status === 'error') {
            metaDiv.innerHTML = `<span class="result-status error">❌ 失败</span>`;
            card.innerHTML += `<div class="error-text">${r.error}</div>`;
          }
        }

        // Summary
        if (data.all_done) {
          clearInterval(pollTimer);
          btn.disabled = false;
          btn.textContent = '🔄 重新生成';

          const doneCount = Object.values(data.results).filter(r => r.status === 'done').length;
          const totalSec = Object.values(data.results).reduce((s, r) => s + (r.duration_sec || 0), 0);
          const minutes = Math.floor(totalSec / 60);
          const seconds = Math.round(totalSec % 60);

          const bar = document.getElementById('summaryBar');
          bar.style.display = 'block';
          bar.innerHTML = `✅ ${doneCount}/${data.total} 个领域生成完成 · 总时长 ${minutes}分${seconds}秒  <span style="color:#a78bfa">|</span>  点击 ▶ 在线收听`;
        }
      });
  }, 1500);
}

function togglePlay(domainKey) {
  const playBtn = document.getElementById('play-' + domainKey);
  const audioUrl = playBtn.dataset.url;
  if (!audioUrl) return;

  const player = document.getElementById('audioPlayer');

  if (currentAudioDomain === domainKey && !player.paused) {
    // Pause current
    player.pause();
    playBtn.textContent = '▶';
    playBtn.classList.remove('playing');
    currentAudioDomain = null;
  } else {
    // Reset previous button
    if (currentAudioDomain) {
      const prevBtn = document.getElementById('play-' + currentAudioDomain);
      if (prevBtn) { prevBtn.textContent = '▶'; prevBtn.classList.remove('playing'); }
    }
    // Play new
    player.src = audioUrl;
    player.style.display = 'block';
    player.play();
    playBtn.textContent = '⏸';
    playBtn.classList.add('playing');
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
    print("  💡 提示:")
    print("     - 演示脚本模式无需 API Key，即刻体验")
    print("     - 真实数据模式需要设置 DEEPSEEK_API_KEY")
    print("     - 按 Ctrl+C 停止服务")
    print()
    app.run(host="0.0.0.0", port=5001, debug=False)
