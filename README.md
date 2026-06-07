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

### 方式二：手动启动（开发模式，使用 SQLite）

```bash
# 后端
cd backend
pip install -r requirements.txt
python main.py

# 前端
cd frontend
npm install
npm run dev
```

> 开发模式无需 PostgreSQL/Redis，后端自动使用 SQLite + 内存缓存。设置 `DEMO_MODE_ENABLED=true` 可跳过登录。

### 数据库

- 开发环境使用 SQLite（自动创建 `backend/offergpt.db`）
- 生产/Docker 环境使用 PostgreSQL（通过 `DATABASE_URL` 配置）
- 迁移脚本：`backend/migrations/001_init.sql`
- 启动时自动建表和种子数据（demo 用户 + demo 会话）

## Demo 演示模式

项目预置了完整的演示数据，可用于无后端离线展示：

- **访问 Demo 页面**：打开 `http://localhost:3000/demo`，可查看完整面试报告（雷达图、VAR 时间轴、对话回放）
- **三层降级策略**：
  1. 在线模式 → 从后端 `/api/demo` 获取最新数据
  2. 离线模式 → 从浏览器 localStorage 缓存加载
  3. 完全离线 → 使用前端内置静态兜底数据
- **Demo 会话**：`demo_interview_001`，Backend Engineer 面试场景，含 5 轮英文对话、3 项亮点、3 条改进建议
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

| 场景 | API Scene ID | 角色示例 |
|------|-------------|---------|
| 求职面试 | `interview` | Founder, Product Thinker, Engineering Leader, Stress |
| 餐厅点餐 | `restaurant` | 友好/忙碌/不耐烦服务员 |
| 商务会议 | `meeting` | 主持人、同事、上级 |

详见 [前后端代码结构速查](docs/前后端代码结构速查.md)（Bug 定位、数据流、模块职责）。

## 技术栈

- **前端**：Next.js 16 + TypeScript + Tailwind CSS 4
- **后端**：FastAPI + SQLAlchemy + SQLite/PostgreSQL
- **实时通信**：WebSocket
- **缓存**：Redis（可选，开发用内存缓存）
- **LLM**：DeepSeek V4 Pro（流式对话）
- **ASR/TTS**：本地 Whisper + EdgeTTS（免费方案已接入）

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
| 1 | 首页三个场景入口均可点击 | 点击 interview/restaurant/meeting 卡片，进入场景配置页 |
| 2 | 面试场景完成简历+JD上传 | 上传 PDF/TXT 简历 + 粘贴 JD，点击"开始面试"进入对话 |
| 3 | 无麦克风切换到文本模式 | 拒绝麦克风权限 → 自动显示文本输入框 → 输入英文 → AI 回复 |
| 4 | WebSocket 断线重连 | 对话中关闭网络 → 显示"连接断开，正在重连…" → 5 秒内恢复 |
| 5 | 结束会话后报告展示 | 点击结束 → 跳转报告页 → 展示 Offer 评分、雷达图、VAR 事件 |
| 6 | Demo 页面离线可用 | 访问 `/demo` → 展示完整报告 → 断网刷新仍可展示 |
| 7 | 所有错误提示为中文 | 触发各类错误 → 提示均为中文（如"麦克风权限被拒绝，请检查浏览器设置"） |
| 8 | Docker 3 分钟启动 | `docker-compose up -d` → `python main.py` → `npm run dev` |
