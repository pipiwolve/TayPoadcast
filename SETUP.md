# 配置指南：开启每日 AI 新闻播客推送

## 一、Telegram 通道（推荐，5分钟配置）

### 1. 创建 Bot
在 Telegram 中搜索 `@BotFather`，发送：
```
/newbot
```
按提示设置 bot 名称和用户名，完成后你会得到：
```
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 2. 获取 Chat ID
搜索你刚创建的 bot，发送任意消息。然后访问（替换 TOKEN）：
```
https://api.telegram.org/bot<TOKEN>/getUpdates
```
从返回的 JSON 中找到 `"chat":{"id":123456789}`，这就是你的 `TELEGRAM_CHAT_ID`。

### 3. 添加到 GitHub Secrets
在 GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret：
- Name: `TELEGRAM_BOT_TOKEN` → Value: 你的 token
- Name: `TELEGRAM_CHAT_ID` → Value: 你的 chat id

---

## 二、微信测试号通道（可选，10分钟配置）

### 1. 申请测试号
访问 https://mp.weixin.qq.com/debug/cgi-bin/sandboxinfo?action=showinfo&t=sandbox/index
扫码登录后获取：`appID` 和 `appsecret`

### 2. 关注测试号
在测试号页面，用微信扫描"测试号二维码"关注。关注后页面会显示你的 `openid`。

### 3. 创建模板消息
在测试号页面，点击"新增测试模板"，模板内容：
```
{{first.DATA}}
新闻摘要：{{keyword1.DATA}}
推送时间：{{keyword2.DATA}}
{{remark.DATA}}
```
记下 `template_id`。

### 4. 添加到 GitHub Secrets
- `WX_APPID`, `WX_SECRET`, `WX_OPENID`, `WX_TEMPLATE_ID`

---

## 三、Claude API Key（必需）

### 添加到 GitHub Secrets：
- Name: `ANTHROPIC_API_KEY` → Value: `sk-ant-...`

---

## 四、验证

### 手动触发测试：
在 GitHub 仓库 → Actions → Daily AI News Podcast → Run workflow

### 本地测试：
```bash
# 只验证管线，不发通知
python main.py --full

# 全管线 + 推送
export TELEGRAM_BOT_TOKEN=xxx
export TELEGRAM_CHAT_ID=xxx
export ANTHROPIC_API_KEY=sk-ant-xxx
python main.py --auto
```

---

## 定时规则

GitHub Actions 默认 `cron: '0 2 * * *'` = 北京时间 10:00。

如需修改推送时间，编辑 `.github/workflows/daily_podcast.yml` 中的 cron 表达式：
```
# 北京时间 8:00 = UTC 0:00
- cron: '0 0 * * *'

# 北京时间 21:00 = UTC 13:00
- cron: '0 13 * * *'
```
