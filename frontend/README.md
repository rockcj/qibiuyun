# OfferGPT Frontend

基于 Next.js 16 的 OfferGPT AI 实时场景英语口语陪练平台前端。

## 项目简介

OfferGPT 是一个 AI 驱动的实时英语口语陪练平台，支持三大场景：求职面试（Interview）、餐厅点餐（Restaurant）、商务会议（Meeting）。前端提供实时语音对话、ASR 字幕、AI 文本流、TTS 音频播放、实时轻纠正、VAR 时间轴回放和多维度场景报告展示。

## 技术栈

- **Next.js 16** (App Router + Turbopack)
- **React 19**
- **TypeScript 5**
- **Tailwind CSS 4**
- **WebSocket** 实时语音通信
- **Web Audio API** 麦克风采集与 TTS 播放

## 快速启动

```bash
# 安装依赖
npm install

# 开发模式启动（默认代理到 localhost:8000 后端）
npm run dev

# 生产构建
npm run build
npm start
```

启动后访问：
- 首页：http://localhost:3000
- Demo 离线页面：http://localhost:3000/demo

## 页面结构

| 路由 | 说明 |
|------|------|
| `/` | 首页，展示三大场景入口卡片 |
| `/scenes/[scene]` | 场景配置页（主题/角色/难度/纠错开关） |
| `/interview/setup` | 简历上传 + JD 输入 + ASR 模型选择 |
| `/sessions/[sessionId]` | 实时对话页（语音/文本双模式） |
| `/reports/[sessionId]` | 场景报告页（评分/雷达图/VAR 时间轴/对话回放） |
| `/demo` | Demo 离线演示页（三层降级：API→localStorage→静态数据） |
| `/login` | 登录页 |
| `/register` | 注册页 |
| `/history` | 训练记录列表（分页 + 场景筛选 + 删除） |

## 目录结构

```
src/
├── app/                    # App Router 页面
│   ├── layout.tsx          # 根布局（AppShell + 字体 + Metadata）
│   ├── page.tsx            # 首页
│   ├── globals.css         # Tailwind + 自定义动画
│   ├── scenes/[scene]/     # 场景配置页
│   ├── interview/setup/    # 面试资料准备页
│   ├── sessions/[sessionId]/ # 实时对话页
│   ├── reports/[sessionId]/  # 报告详情页
│   ├── demo/               # Demo 离线页
│   ├── login/              # 登录页
│   ├── register/           # 注册页
│   └── history/            # 训练记录页
├── components/             # UI 组件
│   ├── AppShell.tsx        # 全局布局（侧边栏 + 内容区）
│   ├── HomeContent.tsx     # 首页内容（Hero + 场景卡片）
│   ├── SceneCard.tsx       # 场景入口卡片
│   ├── SceneConfigForm.tsx # 场景配置表单
│   ├── VoiceSessionPanel.tsx # 实时对话面板（核心组件）
│   ├── SessionReportPanel.tsx # 报告展示面板
│   ├── RadarChart.tsx      # SVG 雷达图
│   ├── TimelineViewer.tsx  # VAR 时间轴
│   ├── TranscriptReplayPanel.tsx # 对话回放面板
│   ├── CorrectionToast.tsx # 实时纠错提示
│   ├── Sidebar.tsx         # 侧边栏导航
│   ├── ResumeUploader.tsx  # 简历上传
│   ├── JobDescriptionEditor.tsx # JD 编辑器
│   ├── LoginForm.tsx       # 登录表单
│   ├── RegisterForm.tsx    # 注册表单
│   ├── Pagination.tsx      # 分页组件
│   ├── ConfirmDialog.tsx   # 确认对话框
│   ├── LanguageSwitcher.tsx # 中英文切换
│   └── ...
├── hooks/                  # 自定义 Hooks
│   ├── useWebSocket.ts     # WebSocket 连接管理（自动重连）
│   └── useMicrophone.ts    # 麦克风音频采集（VAD 检测）
├── contexts/               # React Context
│   ├── AuthContext.tsx      # JWT 认证状态管理
│   ├── ToastContext.tsx     # 全局 Toast 通知
│   └── LocaleContext.tsx    # 中英文国际化
├── lib/
│   └── api.ts              # REST API 客户端（自动 Token 刷新）
├── types/
│   └── api.ts              # TypeScript 类型定义
├── i18n/
│   └── translations.ts     # 365 个中英文翻译 key
└── data/
    └── demoData.ts         # 三层 Demo 静态兜底数据
```

## Demo 降级路径

Demo 页面 `/demo` 实现了三层降级策略，确保在任何情况下都能演示：

1. **API 层** — 从后端 `/api/demo` 获取实时 Demo 数据
2. **localStorage 层** — 使用浏览器缓存的 Demo 数据
3. **静态数据层** — 使用 `demoData.ts` 内置的预置数据（完全离线）

## 开发说明

- 使用 `npm run dev` 启动时，Next.js 自动将 `/api/*` 请求代理到 `http://localhost:8000`
- WebSocket 连接自动重连（最多 3 次，间隔 3 秒）
- 无麦克风权限时自动切换到文本输入模式
- TTS 不可用时使用浏览器 `speechSynthesis` 朗读
- 所有错误提示使用中英文双语
