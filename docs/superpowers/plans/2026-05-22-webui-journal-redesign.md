# Web UI Journal-Style Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the TayPoadcast Web UI from dark warm-theme to Japanese journal/log style with tea-stained paper background and vintage accents, without touching any backend logic, JS, or API routes.

**Architecture:** All changes confined to the `_HTML` string in `web_app.py` (lines 443-1173). CSS variables and styles are completely rewritten; HTML structure gets minor additions (decorative elements, paper texture overlay, date stamp, seal). JavaScript is untouched.

**Tech Stack:** Flask, vanilla HTML/CSS, Google Fonts (Noto Serif SC + LXGW WenKai)

---

### Task 1: Rewrite CSS Variables and Base Styles

**Files:**
- Modify: `web_app.py:452-488` (CSS variables + base reset)

- [ ] **Step 1: Replace CSS custom properties block**

Replace the `:root` block and base reset styles. The old dark theme variables become tea-paper journal variables.

Old (lines 453-488):
```css
:root {
  --bg-deep: #1a1412;
  --bg-card: #241d1a;
  ...
  --font-display: "Noto Serif SC", "Songti SC", "SimSun", serif;
  --font-body: "LXGW WenKai", "KaiTi", "STKaiti", serif;
  --ease-out: cubic-bezier(.34,1.56,.64,1);
  --ease-spring: cubic-bezier(.22,.61,.36,1);
}
*{margin:0;padding:0;box-sizing:border-box}
html{background:var(--bg-deep)}
body{...}
```

New:
```css
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
```

Note: Use the Edit tool to replace `old_string` with `new_string` in one call.

- [ ] **Step 2: Verify the file parses**

```bash
python3 -c "from web_app import app; print('OK')"
```
Expected: `OK` (no syntax errors)

- [ ] **Step 3: Commit**

```bash
git add web_app.py
git commit -m "feat: rewrite CSS variables for tea-paper journal theme"
```

---

### Task 2: Update Header and Add Decorative Elements

**Files:**
- Modify: `web_app.py:490-515` (Header CSS)
- Modify: `web_app.py:728-731` (Header HTML)

- [ ] **Step 1: Replace header CSS**

Old (lines 490-515):
```css
/* ── Header ── */
.header{...}
```

New:
```css
/* ── Header ── */
.header{
  text-align:center;
  padding:48px 24px 36px;
  position:relative;z-index:1;
}
.header .badge{
  display:inline-block;
  border:1.5px solid var(--text-primary);
  padding:4px 18px;
  margin-bottom:12px;
  font-size:10px;
  color:var(--text-secondary);
  letter-spacing:.14em;
  text-transform:uppercase;
}
.header h1{
  font-family:var(--font-display);
  font-size:34px;
  font-weight:700;
  color:var(--text-primary);
  letter-spacing:.1em;
  margin-bottom:6px;
}
.header .subtitle{
  font-size:14px;
  color:var(--text-secondary);
  letter-spacing:.08em;
}
.header .divider{
  width:50px;height:1px;
  background:var(--border);
  margin:18px auto 0;
}
.header .date-stamp{
  position:absolute;
  top:28px;right:24px;
  font-size:12px;
  color:var(--text-muted);
  letter-spacing:.04em;
  writing-mode:horizontal-tb;
}
@media(max-width:480px){
  .header .date-stamp{position:static;text-align:center;margin-top:12px}
}
```

- [ ] **Step 2: Replace header HTML**

Old (lines 728-731):
```html
<header class="header">
  <h1>TayPoadcast</h1>
  <p class="subtitle">每日 AI 播客 · 收听与阅读</p>
</header>
```

New:
```html
<header class="header">
  <div class="badge">Daily AI Podcast</div>
  <h1>TayPoadcast</h1>
  <p class="subtitle">每日 AI 播客 · 收听与阅读</p>
  <div class="divider"></div>
  <div class="date-stamp" id="dateStamp"></div>
</header>
```

- [ ] **Step 3: Add JS to populate date stamp**

The JS at the bottom of the `<script>` needs one line added to set the date. Add after `fetch('/api/notify/config')...` block (around line 824):

```javascript
// Set date stamp
(function(){
  const d = new Date();
  const days = ['星期日','星期一','星期二','星期三','星期四','星期五','星期六'];
  document.getElementById('dateStamp').textContent =
    d.getFullYear() + '年' + (d.getMonth()+1) + '月' + d.getDate() + '日 · ' + days[d.getDay()];
})();
```

- [ ] **Step 4: Verify the file parses**

```bash
python3 -c "from web_app import app; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add web_app.py
git commit -m "feat: update header with badge, divider, and date stamp"
```

---

### Task 3: Update Domain Cards

**Files:**
- Modify: `web_app.py:520-557` (Domain card CSS)

- [ ] **Step 1: Replace domain card CSS**

Replace the old `.domains`, `.domain-card`, and related styles with the journal version:

```css
/* ── Domain cards ── */
.domains{display:flex;flex-direction:column;gap:8px;margin-bottom:28px;position:relative;z-index:1}
.domain-card{
  display:flex;align-items:center;gap:12px;
  padding:14px 16px;
  background:var(--bg-card);
  border:1px solid var(--border);
  border-radius:var(--radius);
  cursor:pointer;
  transition:all .25s var(--ease-out);
  user-select:none;position:relative;
  border-left:3px solid transparent;
}
.domain-card:hover{background:var(--bg-card-hover);transform:translateX(3px)}
.domain-card.selected{
  border-left-color:var(--accent);
  border-color:var(--border);
  border-left:3px solid var(--accent);
  background:linear-gradient(135deg,rgba(107,138,122,.06),rgba(107,138,122,.01));
}
.domain-card .emoji{font-size:24px;flex-shrink:0;width:32px;text-align:center;transition:transform .25s var(--ease-out)}
.domain-card.selected .emoji{transform:scale(1.1)}
.domain-card .info{flex:1;min-width:0}
.domain-card .name{font-family:var(--font-display);font-size:15px;font-weight:600;color:var(--text-primary);margin-bottom:2px}
.domain-card .desc{font-size:12px;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.domain-card .indicator{
  flex-shrink:0;width:18px;height:18px;
  border-radius:50%;border:1.5px solid var(--border);
  transition:all .25s var(--ease-out);
  display:flex;align-items:center;justify-content:center;
}
.domain-card.selected .indicator{
  border-color:var(--accent);background:var(--accent);
}
.domain-card.selected .indicator::after{
  content:"";display:block;width:5px;height:3px;
  border-left:1.5px solid #fff;border-bottom:1.5px solid #fff;
  transform:rotate(-45deg) translateY(-1px);
}
```

- [ ] **Step 2: Verify parse**

```bash
python3 -c "from web_app import app; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add web_app.py
git commit -m "feat: update domain cards to journal style with left-border accent"
```

---

### Task 4: Update Generate Button

**Files:**
- Modify: `web_app.py:559-576` (Generate button CSS)

- [ ] **Step 1: Replace generate button CSS**

```css
/* ── Generate button ── */
.generate-wrap{margin-bottom:32px;position:relative;z-index:1}
.generate-btn{
  width:100%;padding:16px;border:none;border-radius:var(--radius);
  background:linear-gradient(135deg,var(--accent),var(--accent-dark));
  color:#faf5eb;font-family:var(--font-display);font-size:16px;font-weight:600;
  letter-spacing:.08em;cursor:pointer;
  transition:all .3s var(--ease-out);
  position:relative;overflow:hidden;
  box-shadow:0 2px 12px var(--accent-glow);
}
.generate-btn::before{
  content:"";position:absolute;inset:0;
  background:linear-gradient(135deg,rgba(255,255,255,.06),transparent 60%);
  pointer-events:none;
}
.generate-btn:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 6px 24px var(--accent-glow)}
.generate-btn:active:not(:disabled){transform:translateY(0)}
.generate-btn:disabled{opacity:.5;cursor:not-allowed;filter:grayscale(.3)}
```

- [ ] **Step 2: Verify parse**

```bash
python3 -c "from web_app import app; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add web_app.py
git commit -m "feat: update generate button to sage-green gradient"
```

---

### Task 5: Update Tab Navigation

**Files:**
- Modify: `web_app.py:578-598` (Tab nav CSS + panels)

- [ ] **Step 1: Replace tab nav CSS**

```css
/* ── Tab navigation ── */
.tab-nav{display:none;margin-bottom:20px;border-bottom:1px solid var(--border);position:relative;z-index:1}
.tab-nav.visible{display:flex;gap:0}
.tab-btn{
  flex:1;padding:10px 8px;background:none;border:none;
  color:var(--text-muted);font-family:var(--font-display);
  font-size:13px;font-weight:600;cursor:pointer;
  position:relative;transition:color .2s ease;
  letter-spacing:.06em;
}
.tab-btn:hover{color:var(--text-secondary)}
.tab-btn.active{color:var(--accent)}
.tab-btn.active::after{
  content:"";position:absolute;bottom:-1px;left:25%;right:25%;height:2px;
  background:var(--accent);border-radius:1px;
}

/* ── Tab panels ── */
.tab-panel{display:none;animation:fade-up .4s ease;position:relative;z-index:1}
.tab-panel.active{display:block}
```

- [ ] **Step 2: Verify parse**

```bash
python3 -c "from web_app import app; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add web_app.py
git commit -m "feat: update tab navigation to journal style"
```

---

### Task 6: Update Result Cards and Audio Player

**Files:**
- Modify: `web_app.py:600-706` (Results, play button, audio player CSS)

- [ ] **Step 1: Replace result card CSS**

```css
/* ── Results cards (audio tab) ── */
.results{display:flex;flex-direction:column;gap:8px;margin-bottom:16px;position:relative;z-index:1}
.result-card{
  display:flex;align-items:center;gap:12px;
  padding:14px 16px;background:var(--bg-card);
  border-radius:var(--radius);border:1px solid var(--border);
  border-left:3px solid transparent;
  transition:all .3s ease;
}
.result-card.status-pending{border-left-color:var(--border)}
.result-card.status-generating{border-left-color:var(--accent);animation:pulse-border 2s ease-in-out infinite}
.result-card.status-done{border-left-color:var(--accent);background:linear-gradient(135deg,rgba(107,138,122,.05),transparent)}
.result-card.status-error{border-left-color:var(--error);background:linear-gradient(135deg,rgba(201,123,107,.05),transparent)}
@keyframes pulse-border{0%,100%{border-left-color:var(--accent)}50%{border-left-color:#8ab8a0}}
.result-emoji{font-size:22px;flex-shrink:0}
.result-info{flex:1;min-width:0}
.result-name{font-family:var(--font-display);font-size:14px;font-weight:600;margin-bottom:2px}
.result-meta{font-size:12px;color:var(--text-secondary)}

/* ── Play button ── */
.play-btn{
  flex-shrink:0;width:36px;height:36px;
  border-radius:50%;border:1.5px solid var(--border);
  background:transparent;color:var(--text-secondary);
  font-size:14px;cursor:pointer;display:none;
  align-items:center;justify-content:center;
  transition:all .25s var(--ease-out);
}
.play-btn.visible{display:flex}
.play-btn:hover{border-color:var(--accent);color:var(--accent)}
.play-btn.playing{
  border-color:var(--accent);background:var(--accent);color:#faf5eb;
  animation:glowPulse 2s ease-in-out infinite;
}
@keyframes glowPulse{
  0%,100%{box-shadow:0 0 6px var(--accent-glow),0 0 18px rgba(107,138,122,.15)}
  50%{box-shadow:0 0 14px var(--accent-glow),0 0 32px rgba(107,138,122,.3)}
}

/* ── Audio player ── */
.audio-player{
  display:none;width:100%;margin-top:14px;
  border-radius:var(--radius);background:var(--bg-card);
  border:1px solid var(--border);outline:none;
  position:relative;z-index:1;
}
.audio-player.visible{display:block}
```

- [ ] **Step 2: Verify parse**

```bash
python3 -c "from web_app import app; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add web_app.py
git commit -m "feat: update result cards and add glow pulse animation to play button"
```

---

### Task 7: Update Script Viewer and Summaries

**Files:**
- Modify: `web_app.py:629-650` (Script + summary CSS)

- [ ] **Step 1: Replace script viewer and summary CSS**

```css
/* ── Script viewer (文稿 tab) ── */
.script-viewer{font-size:14px;line-height:2;padding:8px 0;position:relative;z-index:1}
.script-turn{display:flex;gap:10px;margin-bottom:16px;align-items:flex-start}
.script-turn .speaker-badge{
  flex-shrink:0;padding:1px 10px;border-radius:var(--radius-sm);
  font-family:var(--font-display);font-size:12px;font-weight:600;
  white-space:nowrap;margin-top:3px;border:1px solid transparent;
}
.script-turn .speaker-badge.xiaoxiao{border-color:#c9a0a8;color:var(--accent-rose);background:var(--accent-rose-bg)}
.script-turn .speaker-badge.yunyang{border-color:#8aacc9;color:var(--accent-slate);background:var(--accent-slate-bg)}
.script-turn .turn-text{flex:1;color:var(--text-primary)}

/* ── Summaries (速览 tab) ── */
.summary-list{display:flex;flex-direction:column;gap:10px;position:relative;z-index:1}
.summary-item{
  background:var(--bg-card);border:1px solid var(--border);
  border-radius:var(--radius);padding:14px 16px;
}
.summary-item .repo-header{display:flex;align-items:center;gap:10px;margin-bottom:4px}
.summary-item .repo-name{font-family:var(--font-display);font-size:14px;font-weight:600;color:var(--accent)}
.summary-item .repo-meta{font-size:11px;color:var(--text-muted);margin-left:auto;white-space:nowrap}
.summary-item .repo-desc{font-size:13px;color:var(--text-secondary);line-height:1.8}
```

- [ ] **Step 2: Verify parse**

```bash
python3 -c "from web_app import app; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add web_app.py
git commit -m "feat: update script viewer and summaries to journal style"
```

---

### Task 8: Update Push Section

**Files:**
- Modify: `web_app.py:652-685` (Push section CSS)

- [ ] **Step 1: Replace push section CSS**

```css
/* ── Push section ── */
.push-section{display:none;margin-top:28px;padding-top:20px;border-top:1px dashed var(--border);position:relative;z-index:1}
.push-section.visible{display:block;animation:fade-up .5s ease}
.push-section .push-title{
  font-family:var(--font-display);font-size:12px;color:var(--text-muted);
  margin-bottom:14px;letter-spacing:.08em;text-align:center;
}
.push-buttons{display:flex;gap:8px}
.push-btn{
  flex:1;padding:12px;border-radius:var(--radius);border:1px solid var(--border);
  background:var(--bg-card);color:var(--text-secondary);
  font-family:var(--font-display);font-size:13px;font-weight:600;
  cursor:pointer;transition:all .2s var(--ease-out);
  display:flex;align-items:center;justify-content:center;gap:6px;
}
.push-btn:hover:not(:disabled){border-color:var(--accent);color:var(--text-primary)}
.push-btn:disabled{opacity:.4;cursor:not-allowed}
.push-btn.sent{border-color:var(--accent);color:var(--accent)}
.push-btn.failed{border-color:var(--error);color:var(--error)}
.push-btn .push-icon{font-size:16px}
.push-btn .push-label{font-size:12px}

.feishu-config{display:none;margin-top:12px;padding:14px 16px;background:rgba(107,138,122,.04);border-radius:var(--radius);border:1px solid var(--border)}
.feishu-config.visible{display:block}
.feishu-config .config-title{font-size:12px;color:var(--text-secondary);margin-bottom:10px}
.feishu-config label{display:block;font-size:11px;color:var(--text-muted);margin-bottom:3px;margin-top:8px}
.feishu-config label:first-of-type{margin-top:0}
.feishu-config input{width:100%;padding:7px 10px;font-size:12px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-sm);color:var(--text-primary);box-sizing:border-box;font-family:var(--font-body)}
.feishu-config input:focus{outline:none;border-color:var(--accent)}
```

- [ ] **Step 2: Verify parse**

```bash
python3 -c "from web_app import app; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add web_app.py
git commit -m "feat: update push section to journal style with dashed separator"
```

---

### Task 9: Update Remaining Styles and Add Seal

**Files:**
- Modify: `web_app.py:682-724` (Spinner, summary-bar, animations, responsive)

- [ ] **Step 1: Replace spinner, summary bar, animations, responsive CSS**

```css
/* ── Spinner ── */
.spinner{
  display:inline-block;width:12px;height:12px;
  border:2px solid rgba(107,138,122,.25);border-top-color:var(--accent);
  border-radius:50%;animation:spin .7s linear infinite;
  margin-right:6px;vertical-align:middle;
}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── Summary bar ── */
.summary-bar{
  background:var(--bg-card);border-top:1px dashed var(--border);border-bottom:1px dashed var(--border);
  padding:12px 18px;text-align:center;font-size:13px;color:var(--text-secondary);
  display:none;animation:fade-up .5s ease;margin-bottom:16px;position:relative;z-index:1;
}
.summary-bar .highlight{color:var(--accent);font-family:var(--font-display);font-weight:600}

/* ── Animations ── */
@keyframes fade-up{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.result-card{animation:fade-up .4s ease both}
.result-card:nth-child(1){animation-delay:0s}
.result-card:nth-child(2){animation-delay:.05s}
.result-card:nth-child(3){animation-delay:.1s}
.result-card:nth-child(4){animation-delay:.15s}

/* ── Seal ── */
.seal{
  text-align:center;margin-top:24px;position:relative;z-index:1;
}
.seal-inner{
  display:inline-flex;align-items:center;justify-content:center;
  width:36px;height:36px;border-radius:50%;
  border:1.5px solid var(--border);
  font-size:10px;color:var(--text-muted);
  transform:rotate(-12deg);
  line-height:1.3;text-align:center;
  font-family:var(--font-display);
}

/* ── Responsive ── */
@media(max-width:480px){
  .header{padding:36px 20px 28px}
  .header h1{font-size:26px}
  .domain-card{padding:12px}
  .domain-card .desc{font-size:11px}
  .push-buttons{flex-direction:column}
}
```

- [ ] **Step 2: Add seal HTML before closing `</div>` of container**

Add after the `</div>` of push section (before `</div>` of container, around line 787):

```html
  <div class="seal">
    <div class="seal-inner">手<br>帳</div>
  </div>
```

- [ ] **Step 3: Verify parse**

```bash
python3 -c "from web_app import app; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add web_app.py
git commit -m "feat: add seal decoration, update summary bar and responsive styles"
```

---

### Task 10: End-to-End Visual Verification

**Files:**
- Launch: `python3 web_app.py`

- [ ] **Step 1: Start the app**

```bash
python3 web_app.py &
sleep 2
```

- [ ] **Step 2: Verify page loads with correct styles**

```bash
curl -s http://localhost:5001 | grep -o 'f5efe0' | head -1
```
Expected: `f5efe0` (new tea-paper background color present)

- [ ] **Step 3: Verify no old dark theme colors leaked**

```bash
curl -s http://localhost:5001 | grep -c '1a1412'
```
Expected: `0` (old dark background gone)

- [ ] **Step 4: Verify JS variables/function names unchanged**

```bash
# All key JS functions should still be present
curl -s http://localhost:5001 | grep -c 'function toggleDomain'
curl -s http://localhost:5001 | grep -c 'function startGeneration'
curl -s http://localhost:5001 | grep -c 'function switchTab'
curl -s http://localhost:5001 | grep -c 'function pushNotify'
```
Expected: `1` for each

- [ ] **Step 5: Kill test server**

```bash
kill %1 2>/dev/null || true
```

- [ ] **Step 6: Commit verification results**

```bash
git commit --allow-empty -m "verify: end-to-end visual check passed"
```

---

## Spec Coverage Check

| Spec Section | Task |
|---|---|
| 配色 (Design Tokens) | Task 1 |
| 纸张纹理 | Task 1 |
| 标题栏 + 日期戳 | Task 2 |
| 领域卡片 | Task 3 |
| 生成按钮 | Task 4 |
| 结果卡片 + 播放按钮光晕 | Task 6 |
| 播放器 (波形 + 进度条) | HTML5 audio element kept, glow animation added in Task 6 |
| 标签导航 | Task 5 |
| 推送区域 (虚线分隔) | Task 8 |
| 文稿 Tab (晓晓/云扬标签) | Task 7 |
| 速览 Tab | Task 7 |
| 印章装饰 | Task 9 |
| JS 不动 | All tasks (no JS changes except date stamp init) |
| Responsive | Task 9 |
