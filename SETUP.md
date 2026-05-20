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


## 四、飞书（Feishu）通道（推荐，10分钟配置）

飞书支持直接推送 MP3 播客文件和文字摘要，是除 Telegram 外唯一能发送完整音频的通道。

### 1. 创建飞书应用

1. 打开 https://open.feishu.cn ，登录后进入 **开发者后台**
2. 点击 **创建企业自建应用**，填写应用名称（如"AI新闻播客"）
3. 创建后在应用页面获取：
   - **APP ID**: `cli_xxxxxxxxxxxxxxxx`
   - **APP SECRET**: 点击"显示"获取

### 2. 添加机器人能力

1. 左侧菜单 → **应用能力** → **机器人** → 点击开启
2. 填写机器人名称和描述，保存

### 3. 配置权限

1. 左侧菜单 → **权限管理**
2. 搜索并开通以下权限：
   - `contact:user.id:readonly` — 通过手机号或邮箱获取用户 ID
3. 左侧菜单 → **版本管理与发布** → **创建版本** → 填写版本号（如 `1.0.0`）→ **发布**

### 4. 获取 RECEIVE ID（Open ID）

**方法一：通过 API 查询（推荐）**

确保应用已发布后，用以下命令查询（替换手机号和凭证）：

```bash
# 1. 获取 token
TOKEN=$(curl -s -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"app_id":"你的APP_ID","app_secret":"你的APP_SECRET"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['tenant_access_token'])")

# 2. 查询 open_id
curl -s -X POST "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"mobiles":["你的手机号"]}'
```

返回示例：`"user_id":"ou_b4a3d022abb1e16007c7008e45751c0f"` — 这就是你的 RECEIVE ID。

**方法二：通过 API 调试台**

在开发者后台 → **API 调试台** → 搜索 `batch_get_id` → 选择 **查询用户 ID**，填入手机号直接运行。

### 5. 测试推送

```bash
curl -s -X POST "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{"receive_id":"你的open_id","msg_type":"text","content":"{\"text\":\"测试推送\"}"}'
```

飞书中收到"测试推送"即表示配置成功。

### 6. 添加环境变量

在 `.env` 文件中填写：

```
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=你的secret
FEISHU_RECEIVE_ID=ou_xxxxxxxxxxxxxxxx
FEISHU_RECEIVE_ID_TYPE=open_id
```

或者直接在 Web UI 推送区域点击 **推送到飞书**，在展开的表单中填入以上三个值即可，无需修改 .env。

### 7. 添加到 GitHub Secrets
- `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_RECEIVE_ID`

### 8. 踩坑记录

以下是实际配置过程中遇到的全部问题和解决方案：

**坑1：权限开通后不生效 —— 必须发布新版本**

在"权限管理"中开通权限后，API 依然返回 `99991672 Access denied`。这是因为飞书的权限变更需要**发布新版本**才会生效：

1. 左侧菜单 → **版本管理与发布** → **创建版本**
2. 填写版本号（如 `1.0.0`）→ **发布**
3. 等待 1-2 分钟，新版本生效后再调用 API

每次增删权限后都需要重新发布。

**坑2：缺少 `im:resource:upload` 权限 —— 文本能发但文件发不了**

飞书机器人发文本消息不需要额外权限，但上传文件（MP3）需要 `im:resource:upload` 和 `im:resource`。如果只开了通讯录权限，文本推送正常但文件上传会静默失败，排查时容易忽略。务必在**权限管理**中搜索并开通：

- `im:resource:upload` — 上传文件到 IM
- `im:resource` — 获取 IM 资源
- `contact:user.id:readonly` — 通过手机号/邮箱获取用户 ID

**坑3：API 请求 Content-Type 需要显式指定 charset**

部分飞书 API 对 `Content-Type` 头敏感，建议统一使用：

```
Content-Type: application/json; charset=utf-8
```

缺少 `charset=utf-8` 可能导致 `batch_get_id` 等接口返回空响应或解析失败。


## 五、验证

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


## 六、定时规则

默认 `cron: '0 2 * * *'` = 北京时间 10:00。

修改 `.github/workflows/daily_podcast.yml`：
```
# 北京时间 8:00 = UTC 0:00
- cron: '0 0 * * *'

# 北京时间 21:00 = UTC 13:00
- cron: '0 13 * * *'
```

## 七、多领域模块配置

### 启用新领域

编辑 `config.yaml`，将对应领域的 `enabled` 设为 `true`：

```yaml
domains:
  finance:
    enabled: true   # 改为 true 即可
```

或运行交互式菜单：

```bash
python cli_menu.py
# 选择 "选择领域模块" → 输入对应编号 → 保存
```

### 可用领域

| 领域 | 信息源 | 适用人群 |
|------|--------|---------|
| 技术资讯 (tech) | GitHub Trending + Hacker News | 开发者、AI 从业者 |
| 财经资讯 (finance) | 雪球热帖 + 财联社电报 | 股民、金融从业者 |
| 学术前沿 (academic) | arXiv 最新论文 | 研究人员、研究生 |
| 综合新闻 (general) | 微博热搜 + 知乎热榜 + 新浪要闻 | 大众用户 |

### 自定义领域 Prompt

每个领域的 `prompt_extra` 字段决定 LLM 生成播客时的侧重方向，例如：

```yaml
finance:
  prompt_extra: "重点关注 A 股市场、宏观经济政策、行业轮动"
```

修改后播客内容会更聚焦于你关心的方向。
```
