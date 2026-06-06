# OfferGPT

AI Real-Scene English Speaking Coach — 在真实场景中与 AI 角色对话，实时纠正发音/语法，生成可量化的口语成长报告。

## 快速启动

### 后端 (FastAPI)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：http://localhost:8000/docs

### 前端 (Next.js)

```bash
cd frontend
npm install
npm run dev
```

前端页面：http://localhost:3000

### 数据库

- 开发环境使用 SQLite（自动创建 `backend/offergpt.db`）
- 生产环境切换到 PostgreSQL：修改 `backend/.env` 中的 `DATABASE_URL`
- 迁移脚本：`backend/migrations/001_init.sql`

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
