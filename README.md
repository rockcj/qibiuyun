<p align="center">
  <img src="https://img.shields.io/badge/Platform-Web-blue?style=for-the-badge&logo=googlechrome" alt="Platform">
  <img src="https://img.shields.io/badge/Language-TypeScript%20%7C%20Python-3178C6?style=for-the-badge&logo=typescript" alt="Language">
  <img src="https://img.shields.io/badge/Framework-Next.js%2016%20%7C%20FastAPI-black?style=for-the-badge&logo=nextdotjs" alt="Framework">
  <img src="https://img.shields.io/badge/Database-PostgreSQL%20%7C%20Redis-4169E1?style=for-the-badge&logo=postgresql" alt="Database">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
</p>

<h1 align="center">SpeakUp AI</h1>

<p align="center">
  <b>AI 驱动的英语口语实战教练</b> — 真实场景 · 实时语音 · 智能纠错 · VAR 复盘
</p>

<p align="center">
  <sub>🏆 七牛云 × XEngineer 暑期实训营 · 题目一：AI 英语口语陪练</sub>
</p>

---

## 🎥 Demo

<p align="center">
  <a href="#">
    <img src="https://img.shields.io/badge/📺_演示视频-即将上线-gray?style=for-the-badge" alt="Demo">
  </a>
  &nbsp;
  <a href="http://localhost:3000/demo">
    <img src="https://img.shields.io/badge/🖥️_在线_Demo-立即体验-6366f1?style=for-the-badge" alt="Live Demo">
  </a>
</p>

---

## ✨ 主要功能

| | | |
|------|------|------|
| ✅ 三场景覆盖 | 求职面试 / 餐厅点餐 / 商务会议，各有独立评分体系 |
| ✅ 实时语音对话 | WebSocket 全双工管线：VAD → Whisper ASR → LLM → TTS |
| ✅ 简历/JD 驱动 | 上传简历和岗位描述，AI 个性化出题 |
| ✅ 实时轻纠正 | 语法 + 发音异步纠错，不打断对话流 |
| ✅ 场景量化报告 | 多维度评分 + SVG 雷达图 + VAR 时间轴回放 |
| ✅ 三层降级兜底 | API → localStorage → 静态数据，断网也能演示 |
| ✅ JWT 认证 | 注册 / 登录 / Token 刷新，Demo 模式可跳过 |
| ✅ 中英双语 | 全站 i18n，365 个翻译 key |

---

## 🛠 技术栈

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-16.2-black?logo=nextdotjs" alt="Next.js">
  <img src="https://img.shields.io/badge/React-19.2-61DAFB?logo=react" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript" alt="TypeScript">
  <img src="https://img.shields.io/badge/TailwindCSS-4-06B6D4?logo=tailwindcss" alt="TailwindCSS">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Redis-7-DC382D?logo=redis" alt="Redis">
  <img src="https://img.shields.io/badge/WebSocket-实时通信-010101?logo=socketdotio" alt="WebSocket">
  <img src="https://img.shields.io/badge/Whisper-ASR-412991?logo=openai" alt="Whisper">
  <img src="https://img.shields.io/badge/DeepSeek-V4-4D6BFE?logo=deepseek" alt="DeepSeek">
  <img src="https://img.shields.io/badge/EdgeTTS-TTS-0078D4?logo=microsoftedge" alt="EdgeTTS">
</p>

> 前端零第三方 UI 库依赖，所有组件（RadarChart、TimelineViewer、Sidebar 等）均为原创实现。

---

## 🚀 快速开始

### 环境要求

| 依赖 | 推荐版本 | 说明 |
|------|---------|------|
| Node.js | 22 LTS | 前端运行环境 |
| Python | 3.12+ | 后端运行环境 |
| PostgreSQL | 16 | 生产数据库 |
| Redis | 7 | 缓存与会话状态 |
| Docker | 27 | 一键启动基础设施（可选） |

### 方式一：Docker（推荐）

```bash
# 1. 环境变量
cp .env.docker .env.local

# 2. 启动数据库
docker-compose up -d

# 3. 后端
cd backend
pip install -r requirements.txt
python main.py

# 4. 前端（另开终端）
cd frontend
npm install
npm run dev
```

启动后访问：

| 地址 | 说明 |
|------|------|
| `http://localhost:3000` | 前端页面 |
| `http://localhost:8000/docs` | API 文档 (Swagger) |
| `http://localhost:3000/demo` | 离线 Demo（无需后端） |

> ⚠️ 实时对话需要 DeepSeek API Key → [platform.deepseek.com](https://platform.deepseek.com)。无 Key 仍可使用 `/demo` 查看完整效果。

### 方式二：SQLite 开发模式

```bash
# 后端（无需 PostgreSQL / Redis）
cd backend
pip install -r requirements.txt
echo "DEMO_MODE_ENABLED=true" > backend/.env
python main.py

# 前端
cd frontend
npm install
npm run dev
```

首次运行自动创建 SQLite 数据库并写入种子数据（3 个 Demo 会话）。

---

## 📦 项目结构

```
├── backend/                  # FastAPI 后端
│   ├── main.py               # 应用入口
│   ├── config.py             # 配置管理
│   ├── database.py           # 数据库引擎 + 种子数据
│   ├── auth/                 # JWT 认证模块
│   ├── models/               # SQLAlchemy ORM
│   ├── routers/              # REST API（auth/scenes/resumes/jobs/interviews）
│   ├── services/             # 业务服务
│   │   └── realtime/         # 实时分析（ASR 过滤/语法/发音 Agent）
│   ├── websocket/            # WebSocket 连接管理（1400+ 行）
│   └── migrations/           # PostgreSQL DDL
│
├── frontend/                 # Next.js 16 前端
│   └── src/
│       ├── app/              # App Router（首页/场景/对话/报告/Demo/登录/注册/历史）
│       ├── components/       # 20+ 原创 UI 组件
│       ├── hooks/            # useWebSocket / useMicrophone
│       ├── contexts/         # Auth / Toast / Locale
│       ├── i18n/             # 中英文国际化（365 key）
│       └── data/             # Demo 静态兜底数据
│
├── docs/                     # 设计文档
├── tests/                    # 17 个测试文件
├── scripts/                  # 运维脚本
└── docker-compose.yml        # 基础设施（PG + Redis）
```

---

## 🎯 场景支持

| 场景 | API ID | 子主题 | 角色 | 评分维度 | 状态 |
|------|--------|--------|------|----------|------|
| 💼 求职面试 | `interview` | 5 | 5 | English · Logic · Confidence · STAR · Technical · Communication | ✅ |
| 🍽️ 餐厅点餐 | `restaurant` | 5 | 3 | English · Politeness · FunctionalPhrases · TaskCompletion · Pronunciation | ✅ |
| 📊 商务会议 | `meeting` | 6 | 3 | English · Logic · Communication · FunctionalPhrases · MeetingControl | ✅ |

---

## 🔄 降级路径

| 故障场景 | 降级方案 |
|---------|---------|
| 无麦克风 | 自动切换文本输入 |
| WebSocket 断开 | 自动重连 3 次（3s 间隔），恢复会话状态 |
| ASR 不可用 | 文本输入兜底 |
| TTS 不可用 | 浏览器 speechSynthesis |
| LLM 超时 | 场景问题池兜底回复 |
| 后端不可用 | `/demo` localStorage 缓存 |
| 完全离线 | `/demo` 静态数据 |
| Redis 不可用 | 自动降级内存缓存 |

---

## 🧪 运行测试

```bash
# 安装测试依赖
pip install -r tests/backend/requirements-test.txt

# 运行后端测试
python -m pytest tests/backend/ -v
```

---

## 📄 License

MIT © 2026 SpeakUp AI

---

<p align="center">
  <sub>Built with ❤️ for 七牛云 × XEngineer 暑期实训营</sub>
</p>
