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

## 技术栈

- **前端**：Next.js 16 + TypeScript + Tailwind CSS 4
- **后端**：FastAPI + SQLAlchemy + SQLite/PostgreSQL
- **实时通信**：WebSocket
- **缓存**：Redis（可选，开发用内存缓存）
- **LLM**：GPT-4o + DeepSeek（待接入）
- **ASR/TTS**：Whisper + EdgeTTS（待接入）
