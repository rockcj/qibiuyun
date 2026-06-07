# SpeakUp AI 测试目录说明

## 目录结构

```text
tests/
├── README.md                          # 本文件：运行方式
├── pytest.ini                         # 后端 pytest 配置
├── docs/
│   └── 代码测试文档.md                 # 风险评估、完整性、逻辑审查、优化建议
├── backend/
│   ├── conftest.py                    # 公共 fixture（内存 DB、HTTP 客户端）
│   ├── requirements-test.txt          # 后端测试依赖
│   ├── test_llm_service.py            # LLM/正则解析服务
│   ├── test_resume_service.py         # 简历文本抽取服务
│   ├── test_job_service.py            # JD 解析服务
│   ├── test_scene_service.py          # 场景配置服务
│   ├── test_cache_service.py          # 缓存服务
│   ├── test_exceptions.py             # 统一错误格式
│   ├── test_websocket_handler.py      # WebSocket 消息路由
│   ├── test_router_scenes.py          # GET /api/scenes
│   ├── test_router_resumes.py         # POST /api/resumes
│   ├── test_router_jobs.py            # POST /api/jobs
│   ├── test_router_interviews.py      # POST/GET /api/interviews
│   └── test_integration_flow.py       # 简历→JD→会话 端到端
└── frontend/
    ├── package.json                   # Vitest 测试依赖
    ├── vitest.config.ts               # Vitest 配置
    ├── setup.ts                       # 全局 setup
    ├── lib/api.test.ts                # API 客户端
    ├── types/api.test.ts              # 类型契约
    ├── i18n/translations.test.ts      # 国际化 key 对齐
    └── components/
        ├── SceneCard.test.tsx
        ├── SceneConfigForm.test.tsx
        ├── ResumeUploader.test.tsx
        └── JobDescriptionEditor.test.tsx
```

## 运行后端测试

```powershell
# 1. 安装依赖
cd backend
pip install -r requirements.txt
pip install -r ../tests/backend/requirements-test.txt

# 2. 执行全部测试
cd ../tests
pytest backend -v

# 3. 仅 P0 用例
pytest backend -v -m p0

# 4. 仅契约测试
pytest backend -v -m contract

# 5. 仅集成测试
pytest backend -v -m integration
```

## 运行前端测试

```powershell
cd tests/frontend
npm install
npm test
```

## 测试标记说明

| 标记 | 含义 |
|---|---|
| `p0` | P0 面试场景必测，PR 合并前必须通过 |
| `contract` | REST API 字段与 api-contract.md 一致性 |
| `integration` | 跨模块端到端链路，使用内存 SQLite |
