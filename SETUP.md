# 配置指南：开启每日 AI 新闻播客推送

## 一、LLM API Key（必需，三选一）

### 推荐：DeepSeek（便宜，中文效果好）
1. 注册 https://platform.deepseek.com
2. 获取 API Key: `sk-...`
3. 价格约 ¥1/百万 token，每天生成一次约 ¥0.003

### 备选：Anthropic Claude（效果好，稍贵）
1. 注册 https://console.anthropic.com
2. 获取 API Key: `sk-ant-...`

### 备选：OpenAI 或其他兼容 API
设置 `OPENAI_API_KEY` + `OPENAI_BASE_URL` 即可

### 添加到 GitHub Secrets
GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret：

| Secret Name | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key (推荐) |
| `ANTHROPIC_API_KEY` | Claude API Key (备选) |

系统会自动检测你设置了哪个 Key。如果同时设置了多个，可以通过 `LLM_PROVIDER` 变量指定：
- GitHub → Settings → Secrets and variables → Actions → Variables → New variable
- Name: `LLM_PROVIDER`, Value: `deepseek` 或 `anthropic`


## 二、Telegram 通道（推荐，5分钟配置）

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
- `TELEGRAM_BOT_TOKEN` → 你的 token
- `TELEGRAM_CHAT_ID` → 你的 chat id


## 三、微信测试号通道（可选，10分钟配置）

### 1. 申请测试号
访问 https://mp.weixin.qq.com/debug/cgi-bin/sandboxinfo?action=showinfo&t=sandbox/index
扫码登录后获取：`appID` 和 `appsecret`

### 2. 关注测试号 + 获取 openid
扫描测试号二维码关注，页面会显示你的 `openid`

### 3. 创建模板消息

点击"新增测试模板"，内容：
```
{{first.DATA}}
新闻摘要：{{keyword1.DATA}}
推送时间：{{keyword2.DATA}}
{{remark.DATA}}
```
记下 `template_id`

### 4. 添加到 GitHub Secrets
- `WX_APPID`, `WX_SECRET`, `WX_OPENID`, `WX_TEMPLATE_ID`


## 四、验证

### 手动触发测试：
GitHub 仓库 → Actions → Daily AI News Podcast → Run workflow

### 本地测试：
```bash
# DeepSeek
export DEEPSEEK_API_KEY=sk-...
python main.py --full

# 全管线 + 推送
export DEEPSEEK_API_KEY=sk-...
export TELEGRAM_BOT_TOKEN=xxx
export TELEGRAM_CHAT_ID=xxx
python main.py --auto
```


## 五、定时规则

默认 `cron: '0 2 * * *'` = 北京时间 10:00。

修改 `.github/workflows/daily_podcast.yml`：
```
# 北京时间 8:00 = UTC 0:00
- cron: '0 0 * * *'

# 北京时间 21:00 = UTC 13:00
- cron: '0 13 * * *'
```
