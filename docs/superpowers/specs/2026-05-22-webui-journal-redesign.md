# Web UI Redesign: 日式手帳日志风

## Context

将 TayPoadcast 的 Web UI 从深色暖调主题改造为日式手帳日志风格（茶纸浅底 + 复古感），不改动任何后端逻辑、JS 交互和 API 路由。所有改动集中在 `web_app.py` 的 `_HTML` 字符串内的 CSS 和 HTML 结构。

## Design Tokens

### 配色

| Token | Value | Usage |
|---|---|---|
| `--bg-page` | `linear-gradient(180deg, #f5efe0, #ede4d3)` | 页面底色 |
| `--bg-card` | `#faf5eb` | 卡片底色 |
| `--text-primary` | `#3d3226` | 主文字 |
| `--text-secondary` | `#8b7355` | 辅文字 |
| `--text-muted` | `#b8a48e` | 弱化文字 |
| `--accent` | `#6b8a7a` | 主强调色(靛绿) |
| `--accent-rose` | `#9b6a72` | 晓晓标签(玫棕) |
| `--accent-slate` | `#5a7a8a` | 云扬标签(灰蓝) |
| `--border` | `#d4c5b0` | 卡片边框 |
| `--border-light` | `#e0d7c5` | 细线 |
| `--success` | `#6b8a7a` | 成功/完成 |

### 字体

```
--font-display: "Noto Serif SC", "Songti SC", "SimSun", serif;
--font-body: "LXGW WenKai", "KaiTi", "STKaiti", serif;
```

保持不变。

## 视觉元素

### 纸张纹理
CSS `radial-gradient` 点阵叠加，模拟手帳纸张的微颗粒感：
```css
background: radial-gradient(circle at 20% 30%, #8b7355 1px, transparent 1px);
background-size: 4px 4px;
opacity: 0.03;
```

### 标题栏
- 顶部小框线徽章（英文 "Daily AI Podcast"）
- 主标题大字间距
- 细线分隔
- 右上角日期戳

### 领域卡片
- 茶白底 `--bg-card`，枯茶细框 `--border`
- 选中态：靛绿 3px 左边框 + 浅靛绿底色
- 圆形勾选指示器（实心靛绿 / 空心枯茶）
- hover 微右移

### 生成按钮
- 靛绿渐变 `linear-gradient(135deg, #6b8a7a, #5a7a6a)`
- 茶白文字
- hover 上浮 + 投影

### 结果卡片
- 与领域卡片统一风格
- 生成中：枯茶左边框 + 脉冲动画
- 完成：靛绿左边框 + 浅靛绿底
- 失败：玫棕左边框
- 播放按钮：圆形靛绿边框，播放中实心靛绿 + 光晕呼吸闪烁

### 播放器
- 波形可视化（装饰性竖柱，播放时跳动）
- 靛绿进度条 + 圆点拖拽手柄
- 播放/暂停大圆按钮 + 光晕呼吸动画（Box-shadow 2s ease-in-out 呼吸）
- 跳过按钮（弱化枯茶色）
- 倍速标签（细框小标签）
- CSS 动画：`@keyframes glowPulse`

### 标签导航
- 枯茶底边线，靛绿激活下划线
- 字体字间距

### 推送区域
- 虚线上下分隔 `— 推送到通讯软件 —`
- 按钮：枯茶细框 + 茶白底，hover 靛绿边框
- 已发送：靛绿边框 + 靛绿文字
- 飞书配置表单：浅靛绿背景区

### 文稿 Tab
- 晓晓标签：玫棕细框 + 浅玫棕底
- 云扬标签：灰蓝细框 + 浅灰蓝底
- 底部迷你播放条（mini waveform + 时间 + 播放按钮）

### 速览 Tab
- 仓库名靛绿强调色
- 星数/语言弱化灰色
- 简介正文色

### 装饰元素
- 底部「手帳」圆印章（旋转 -12deg，枯茶边框）
- 虚线分隔符

## 不改动

- `web_app.py` 所有路由、API、线程逻辑
- JS 脚本（`<script>` 标签内所有代码）
- Google Fonts 引用
- HTML 结构保持不变，仅调整 class 和添加装饰元素

## Verification

1. `python3 web_app.py` 启动后浏览器访问 `http://localhost:5001`
2. 确认页面为浅茶底色、靛绿 accent、纸纹质感
3. 选择领域 → 生成播客 → 确认卡片动画和播放器光晕效果
4. 切换到文稿/速览 Tab → 确认样式一致
5. 推送按钮区域 → 确认飞书配置表单样式
6. 深色/浅色切换验证（若保留切换功能）
