# OfferGPT

AI Real-Scene English Speaking Coach — 在真实场景中与 AI 角色对话，实时纠正发音/语法，生成可量化的口语成长报告。

## 环境要求

| 依赖 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Node.js | >= 20.x | 22 LTS | 前端运行环境 |
| Python | >= 3.11 | 3.12 | 后端运行环境 |
| PostgreSQL | >= 15 | 16 | 生产数据库 |
| Redis | >= 7 | 7 | 缓存与会话状态 |
| Docker | >= 24 | 27 | 一键启动基础设施（可选） |

## 快速启动

### 方式一：Docker 一键启动（推荐）

```bash
# 1. 配置环境变量
cp .env.docker .env.local

# 2. 启动 PostgreSQL + Redis
docker-compose up -d

# 3. 安装后端依赖并启动
cd backend
pip install -r requirements.txt
python main.py

# 4. 另开终端，安装前端依赖并启动
cd frontend
npm install
npm run dev
```

启动后：
- 前端页面：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs
- **离线 Demo 报告页**：http://localhost:3000/demo

> ⚠️ **重要**：`.env.docker` 中的 `DEEPSEEK_API_KEY` 为占位符 `sk-your-deepseek-api-key-here`。填入真实 DeepSeek API Key 后才能进行实时 AI 对话。即使没有 API Key，Demo 页面 `/demo` 仍可完整展示三个场景的报告、评分和 VAR 时间轴（离线兜底数据）。

### 两种体验模式

| 模式 | 需要 DeepSeek API Key | 可用功能 |
|------|----------------------|----------|
| **Demo 离线模式** | ❌ 不需要 | `/demo` 页面三场景报告（评分/雷达图/VAR/对话回放），无需后端 |
| **完整实时对话** | ✅ 需要 | 所有功能：实时语音对话、ASR 语音识别、LLM 流式回复、TTS 语音合成、课后报告生成 |

> 获取 DeepSeek API Key：[platform.deepseek.com](https://platform.deepseek.com) → API Keys → 创建新 Key → 填入 `.env.local` 的 `DEEPSEEK_API_KEY`

### 方式二：手动启动（开发模式，使用 SQLite）

```bash
# 后端（无需 PostgreSQL/Redis，自动使用 SQLite + 内存缓存）
cd backend
pip install -r requirements.txt
# 跳过登录（可选，创建 backend/.env 设置 DEMO 模式）
echo "DEMO_MODE_ENABLED=true" > backend/.env
python main.py

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

> **说明**：开发模式默认使用 SQLite 数据库（`backend/offergpt.db`，首次运行自动创建并写入种子数据）和内存缓存，无需安装 PostgreSQL/Redis。不设置 `DEMO_MODE_ENABLED` 则需先注册/登录。

### 数据库

- 开发环境使用 SQLite（自动创建 `backend/offergpt.db`）
- 生产/Docker 环境使用 PostgreSQL（通过 `DATABASE_URL` 配置）
- 迁移脚本：`backend/migrations/001_init.sql`
- 启动时自动建表和种子数据（demo 用户 + demo 会话）

## Demo 演示模式

项目预置了三个场景的完整演示数据，可用于无后端离线展示：

- **访问 Demo 页面**：打开 `http://localhost:3000/demo`，默认展示面试场景报告。可通过顶部切换器切换 💼求职面试 / 🍽️餐厅点餐 / 📊商务会议 三个场景
- **三层降级策略**：
  1. 在线模式 → 从后端 `/api/demo?scene=interview|restaurant|meeting` 获取最新数据
  2. 离线模式 → 从浏览器 localStorage 缓存加载
  3. 完全离线 → 使用前端内置静态兜底数据
- **Demo 会话**：
  - `demo_interview_001`（de000001）：Backend Engineer 面试，Offer 评分 78
  - `demo_restaurant_001`（de000002）：The Garden Bistro 点餐，点餐评分 82
  - `demo_meeting_001`（de000003）：Mobile App Redesign 项目汇报，会议评分 79
- **Demo 用户**：`demo@offergpt.local`（无需密码，适用于 DEMO_MODE）

## 降级路径

| 故障场景 | 降级方案 | 用户提示 |
|---------|---------|---------|
| 无麦克风 | 自动/手动切换到文本输入模式 | "麦克风权限被拒绝，请检查浏览器设置" |
| WebSocket 断开 | 自动重连 3 次（间隔 3s），恢复会话状态 | "连接断开，正在重连…（第 N/3 次）" |
| ASR 不可用 | 自动切为文本输入 | "语音识别暂不可用，已切换为文本输入模式" |
| TTS 不可用 | 浏览器 speechSynthesis 朗读 | "已切换为浏览器内置语音朗读" |
| 后端不可用 | /demo 页面使用 localStorage 缓存 | "Demo 演示数据 — 离线缓存模式" |
| 完全离线 | /demo 页面使用静态兜底数据 | "Demo 演示数据 — 离线可用（静态数据）" |
| LLM 报告生成失败 | 规则引擎兜底评分 | 后端自动处理，用户无感知 |
| Redis 不可用 | 自动降级为内存缓存 | 后端自动处理，用户无感知 |

所有错误提示均为中文，前端通过全局 Toast 统一展示。

## 项目结构

```
qibiuyun/
├── backend/                # FastAPI 后端
│   ├── main.py             # 应用入口
│   ├── config.py           # 配置管理
│   ├── database.py         # 数据库引擎
│   ├── models/             # SQLAlchemy 模型
│   ├── routers/            # API 路由
│   ├── services/           # 业务服务
│   ├── websocket/          # WebSocket 处理器
│   └── migrations/         # PostgreSQL 迁移脚本
├── frontend/               # Next.js 前端
│   └── src/
│       ├── app/            # App Router 页面
│       └── components/     # React 组件
└── docs/                   # 设计文档
    └── agent-team/         # Agent Team 协作规范
```

## 场景支持

| 场景 | API Scene ID | 子主题数 | 角色数 | 评分维度 | 追问规则 | 状态 |
|------|-------------|---------|-------|---------|---------|------|
| 求职面试 | `interview` | 5 | 5 | 6（English/Logic/Confidence/STAR/Technical/Communication） | 5 条 | ✅ 完整 |
| 餐厅点餐 | `restaurant` | 5 | 3 | 5（English/Politeness/FunctionalPhrases/TaskCompletion/PronunciationFluency） | 6 条 | ✅ 完整 |
| 商务会议 | `meeting` | 6 | 3 | 5（English/Logic/Communication/FunctionalPhrases/MeetingControl） | 6 条 | ✅ 完整 |

> 三场景均有独立 Prompt 追问策略、完整 Topic→Goal 映射和预置 Demo 数据。每场景 3 种 AI 角色可选，支持 5 种难度等级。

详见 [前后端代码结构速查](docs/前后端代码结构速查.md)（Bug 定位、数据流、模块职责）。

## 技术栈

- **前端**：Next.js 16 + TypeScript + Tailwind CSS 4
- **后端**：FastAPI + SQLAlchemy + SQLite/PostgreSQL
- **实时通信**：WebSocket
- **缓存**：Redis（可选，开发用内存缓存）
- **LLM**：DeepSeek V4 Pro（流式对话）
- **ASR/TTS**：本地 Whisper + EdgeTTS（免费方案已接入）

## 第三方依赖说明

> 依据项目规则：引用第三方库、框架或模板，必须在 README 中说明来源与用途。
> 除下表所列第三方依赖外，其余全部代码均为原创实现。

### 后端依赖（Python）

| 包名 | 版本 | 用途 | 来源 |
|------|------|------|------|
| fastapi | 0.115.6 | Web 框架，提供 REST API 和 WebSocket 支持 | 第三方开源 (MIT) |
| uvicorn | 0.34.0 | ASGI 服务器，运行 FastAPI 应用 | 第三方开源 (BSD) |
| sqlalchemy | 2.0.36 | 异步 ORM，数据库模型与查询 | 第三方开源 (MIT) |
| asyncpg | 0.30.0 | PostgreSQL 异步驱动（生产环境） | 第三方开源 (Apache 2.0) |
| aiosqlite | 0.20.0 | SQLite 异步驱动（开发环境兜底） | 第三方开源 (MIT) |
| psycopg2-binary | 2.9.10 | PostgreSQL 同步驱动（迁移脚本使用） | 第三方开源 (LGPL) |
| redis | 5.2.1 | Redis 客户端，缓存与会话状态 | 第三方开源 (MIT) |
| pydantic | 2.10.3 | 数据校验与序列化 | 第三方开源 (MIT) |
| pydantic-settings | 2.7.0 | 环境变量加载与配置管理 | 第三方开源 (MIT) |
| python-dotenv | 1.0.1 | `.env` 文件解析 | 第三方开源 (BSD) |
| httpx | 0.28.1 | 异步 HTTP 客户端（调用 LLM API / TTS） | 第三方开源 (BSD) |
| websockets | 14.1 | WebSocket 协议支持 | 第三方开源 (BSD) |
| python-multipart | 0.0.19 | 表单/文件上传解析 | 第三方开源 (Apache 2.0) |
| python-jose | ≥3.3.0 | JWT 令牌创建与验证 | 第三方开源 (MIT) |
| bcrypt | ≥4.0.0 | 密码哈希 | 第三方开源 (Apache 2.0) |
| email-validator | ≥2.0.0 | 邮箱格式校验 | 第三方开源 (Unlicense) |
| openai-whisper | 20250625 | 本地语音识别 (ASR) | 第三方开源 (MIT, OpenAI) |
| torch | ≥2.0.0 | 深度学习框架（Whisper 依赖） | 第三方开源 (BSD, Meta) |
| numpy | ≥1.26.0 | 数值计算（音频处理） | 第三方开源 (BSD) |
| edge-tts | 6.1.12 | 微软 Edge 在线文字转语音 | 第三方开源 (GPLv3) |
| pypdf | 5.1.0 | PDF 文件文本提取 | 第三方开源 (BSD) |
| openai | 2.41.0 | OpenAI SDK（兼容 DeepSeek API 调用） | 第三方开源 (Apache 2.0) |
| tos | ≥2.6.0 | 火山引擎对象存储 SDK（音频文件存储） | 火山引擎云服务 SDK |
| alembic | 1.14.0 | 数据库迁移工具（已安装，当前使用原始 SQL） | 第三方开源 (MIT) |

### 前端依赖（Node.js）

| 包名 | 版本 | 用途 | 来源 |
|------|------|------|------|
| next | 16.2.6 | React 全栈框架（App Router + Turbopack） | 第三方开源 (MIT, Vercel) |
| react | 19.2.4 | UI 组件库 | 第三方开源 (MIT, Meta) |
| react-dom | 19.2.4 | React DOM 渲染 | 第三方开源 (MIT, Meta) |
| tailwindcss | ^4 | 原子化 CSS 框架 | 第三方开源 (MIT) |
| @tailwindcss/postcss | ^4 | Tailwind CSS v4 PostCSS 插件 | 第三方开源 (MIT) |
| typescript | ^5 | JavaScript 类型检查 | 第三方开源 (Apache 2.0, Microsoft) |
| eslint | ^9 | JavaScript/TypeScript 代码检查 | 第三方开源 (MIT) |
| eslint-config-next | 16.2.6 | Next.js 项目 ESLint 预设规则 | 第三方开源 (MIT, Vercel) |

> **说明**：前端未使用任何第三方 UI 组件库（如 MUI、Ant Design、shadcn/ui），所有界面组件（RadarChart、TimelineViewer、Sidebar、Toast 等）均为纯原创实现。状态管理仅使用 React Context，未引入 Redux/Zustand 等第三方状态库。国际化自建 `LocaleContext`，未使用 i18next 等第三方库。

### 基础设施

| 软件 | 最低版本 | 用途 | 来源 |
|------|----------|------|------|
| PostgreSQL | 15 | 关系型数据库 | 第三方开源 (PostgreSQL License) |
| Redis | 7 | 内存缓存与会话状态 | 第三方开源 (BSD) |
| Docker | 24 | 容器化运行基础设施 | 第三方 (Docker Inc.) |

### LLM / AI 服务

| 服务 | 模型 | 用途 | 来源 |
|------|------|------|------|
| DeepSeek API | deepseek-v4-flash | 实时对话生成（流式） | 第三方云服务 (DeepSeek) |
| DeepSeek API | deepseek-v4-pro | 报告生成与结构化分析 | 第三方云服务 (DeepSeek) |
| EdgeTTS | en-US-JennyNeural | 在线文字转语音 | 第三方云服务 (Microsoft) |
| 火山引擎 TOS | — | 音频文件对象存储 | 第三方云服务 (字节跳动) |

### 原创代码范围

以下模块为**完全原创实现**，不依赖第三方框架或模板：

- **Agent 系统**：Grammar Agent（规则引擎 + LLM 增强）、Pronunciation Agent（WPM/停顿/置信度计算）、Report Agent（场景报告生成）、ASR Filter（8 层过滤）
- **实时语音管线**：EnergyVAD（能量语音活动检测）、ConnectionManager（WebSocket 消息路由）、Turn Manager（轮流对话状态机）
- **前端组件**：VoiceSessionPanel（实时对话面板）、SessionReportPanel（报告面板）、RadarChart（SVG 雷达图）、TimelineViewer（VAR 时间轴）、TranscriptReplayPanel（音频回放）
- **业务服务**：SceneService（三场景配置）、ConversationService（场景 Prompt 编排）、ResumeService（简历解析）、JobService（JD 解析）
- **降级系统**：三层 Demo 降级（API → localStorage → 静态数据）、WebSocket 断线重连、Redis → 内存缓存自动切换

## Step 4：实时轻纠正 & 异步发音/语法分析

### 原创功能说明

- **Grammar Agent**（`backend/services/realtime/grammar_agent.py`）：独立异步语法分析，规则优先 + LLM 增强，检测严重语法错误并触发 `correction.light` WebSocket 消息。
- **Pronunciation Agent**（`backend/services/realtime/pronunciation_agent.py`）：异步计算语速(WPM)、停顿次数、低置信度关键词，写入 cache 供课后报告。
- **Analysis Store**（`backend/services/realtime/analysis_store.py`）：基于 cache_service 的会话级分析数据存储。
- **CorrectionToast**（`frontend/src/components/CorrectionToast.tsx`）：非模态轻纠正提示，不打断对话流。

### 验证方式

1. 启动后端 + 前端，创建面试会话
2. 文本输入 `I have did a project last year`，观察 Toast 提示 "Just a tip: we say 'have done'..."
3. AI 仍正常回复，对话不中断
4. 顶部显示语气词计数器（如 `um:2`）
5. 关闭「实时轻纠正」开关后，不再弹出 Toast
6. 会话结束后访问 `GET /api/interviews/{sessionId}/analysis` 查看汇总数据

### 运行测试

```bash
python -m pytest tests/backend/test_grammar_agent.py tests/backend/test_pronunciation_agent.py tests/backend/test_websocket_handler.py -v
```

## Step 5-6：Demo 稳定性打磨与降级路径

### 新增功能

- **预置 Demo 数据**（`backend/database.py`）：启动时自动种子 `demo_interview_001` 完整会话（transcript + report + VAR 事件）
- **`/demo` 离线路由**（`frontend/src/app/demo/page.tsx`）：三层降级策略（API → localStorage → 静态数据），无需后端即可展示完整报告
- **WebSocket 断线重连 UI**（`frontend/src/hooks/useWebSocket.ts`）：断开时显示"连接断开，正在重连…（第 N/3 次）"，自动恢复会话状态
- **全局 Toast 通知**（`frontend/src/contexts/ToastContext.tsx`）：统一的错误/警告/成功/信息提示，5 秒自动消失
- **Docker 一键部署**（`docker-compose.yml`）：PostgreSQL 16 + Redis 7，3 分钟内启动完整系统
- **环境清单 + 降级路径文档**（README.md）

### 比赛现场检查清单

| # | 检查项 | 验证方式 |
|---|--------|---------|
| 1 | 首页三个场景入口均可点击 | 点击 interview/restaurant/meeting 卡片，进入场景配置页，三个场景均可创建会话并完成对话 |
| 2 | 面试场景完成简历+JD上传 | 上传 PDF/TXT 简历 + 粘贴 JD，点击"开始面试"进入对话 |
| 3 | 餐厅/会议场景直接创建会话 | 无需简历，选择主题和角色后直接开始对话练习 |
| 4 | 无麦克风切换到文本模式 | 拒绝麦克风权限 → 自动显示文本输入框 → 输入英文 → AI 回复 |
| 5 | WebSocket 断线重连 | 对话中关闭网络 → 显示"连接断开，正在重连…" → 5 秒内恢复 |
| 6 | 结束会话后报告展示 | 点击结束 → 跳转报告页 → 展示对应场景评分（Offer/点餐/会议）、雷达图、VAR 事件 |
| 7 | Demo 页面三场景切换 | 访问 `/demo` → 顶部切换💼面试/🍽️点餐/📊会议 → 断网刷新仍可展示 |
| 8 | 所有错误提示为中文 | 触发各类错误 → 提示均为中文（如"麦克风权限被拒绝，请检查浏览器设置"） |
| 9 | Docker 3 分钟启动 | `docker-compose up -d` → `python main.py` → `npm run dev` |
