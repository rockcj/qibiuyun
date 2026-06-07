# OfferGPT 实现总结文档

> 生成日期：2026-06-07 | 分支：`feat/demo-stability` | 基线提交：`a70659f`

---

## 一、已实现的 P0/P1 功能清单（对照 PRD）

### P0 核心必备功能（F001-F008）

| 编号 | 功能 | PRD 要求 | 实现状态 | 实现说明 |
|------|------|----------|----------|----------|
| F001 | 场景管理与角色选择 | 三场景入口（面试/点餐/会议），可切换子主题和角色 | ✅ 已实现 | 首页三个场景卡片，`SceneConfigForm` 支持选择 topic / roleMode / difficultyLevel / duration。后端 `scene_service.py` 提供三场景静态配置 |
| F002 | 简历上传与解析 | 上传 PDF/TXT，结构化提取技能、项目、风险信号 | ✅ 已实现 | `ResumeUploader` 组件 + `POST /api/resumes`，pypdf 提取文本，LLM/正则解析 |
| F003 | JD 输入与解析 | 输入岗位描述，提取技能、能力、难度等级 | ✅ 已实现 | `JobDescriptionEditor` 组件 + `POST /api/jobs`，LLM/正则解析 |
| F004 | 实时语音对话 | WebSocket 音频流，ASR→LLM→TTS 全链路 | ✅ 已实现 | `VoiceSessionPanel` + `useWebSocket` + `useMicrophone`，VAD→Whisper ASR→DeepSeek LLM→EdgeTTS |
| F005 | AI 连续追问与场景引导 | 根据用户回答动态追问/引导，非简单问答 | ✅ 已实现 | `ConversationService` 基于场景 System Prompt + 上下文摘要（最近 6 轮）流式生成回复 |
| F006 | 实时轻纠正 | 严重语法/发音错误一句话提示，不打断对话 | ✅ 已实现 | `GrammarAgent`（规则优先+LLM增强）→ `correction.light` WS 消息 → `CorrectionToast` 非模态提示 |
| F007 | 发音评测 | 语速(WPM)、停顿、ASR 置信度、Filler words | ✅ 已实现 | `PronunciationAgent` 计算 WPM/停顿/低置信度词，`ASRFilter` 过滤无效输入，前端实时显示 filler words 计数 |
| F008 | 课后场景报告 | 场景专属评分+雷达图+VAR时间轴+改进建议 | ✅ 已实现 | `SessionReportPanel` 展示 Offer/Restaurant/Meeting Score，`RadarChart` SVG 雷达图，`TimelineViewer` 时间轴，`TranscriptReplayPanel` 对话回放 |

### P1 差异化能力（F101-F104）

| 编号 | 功能 | PRD 要求 | 实现状态 | 实现说明 |
|------|------|----------|----------|----------|
| F101 | 多场景评分权重 | 不同场景使用不同评分维度和权重 | ✅ 已实现 | 面试 6 维度(English/Logic/Confidence/STAR/Technical/Communication)，点餐 5 维度(Politeness/Functional Phrases)，会议 5 维度(Meeting Control) |
| F102 | VAR 时间轴回放 | 可点击时间轴、音频片段定位、证据绑定 | ✅ 已实现 | `TimelineViewer` 按颜色区分事件类型(红/黄/绿)，`TimelineEvent` 模型绑定 transcript snippet / audio URL / evidence |
| F103 | 简历/JD 驱动的个性化面试 | 面试问题基于简历和 JD 生成 | ✅ 已实现 | 面试场景绑定 `resumeId` + `jobId`，Conversation Agent 在 System Prompt 中注入简历摘要和 JD 画像 |
| F104 | 多 ASR 模型切换 | 支持不同 ASR 模型运行时切换 | ✅ 已实现 | `POST /api/asr/switch` 支持 Whisper tiny/base/small 三档切换，前端 `ASRModelSelector` |

### P2 冠军功能（F201-F203）

| 编号 | 功能 | PRD 要求 | 实现状态 | 实现说明 |
|------|------|----------|----------|----------|
| F201 | Interview Twin（数字分身） | 基于简历+JD+面试表现生成职业画像 | ❌ 未实现 | 数据库预留 `twin_profile_json` 字段，`ReportAgent` 保留接口但未实现 |
| F202 | Growth Coach（成长路线图） | 7/14/30 天训练计划 | ❌ 未实现 | 数据库预留 `growth_plan_json` 字段，报告中无训练计划面板 |
| F203 | 压力面试模式 | 打断、质疑、限时追问 | ❌ 未实现 | `SceneConfigForm` 有难度选择(初级/中级/高级)，但无真正的打断控制和连续压力追问 |

### 超出 PRD 的额外实现

| 功能 | 说明 |
|------|------|
| JWT 用户认证系统 | 注册/登录/Token 刷新/路由保护，bcrypt 密码哈希 |
| 中英文国际化 | `LocaleContext` + 365 个翻译 key，前端完整 zh/en 切换 |
| 全局 Toast 通知 | `ToastContext` 统一错误/警告/成功提示，5 秒自动消失 |
| 离线 Demo 页面 | `/demo` 路由，三层降级（API→localStorage→静态数据），无需后端 |
| WebSocket 断线重连 | 自动重连 3 次（3s 间隔），心跳 ping 15s，恢复会话状态 |
| 训练记录管理 | `HistoryPage` 分页列表 + 场景筛选 + 删除确认，`SessionHistoryList` 首页最近 5 条 |
| 全局侧边栏导航 | `Sidebar` 组件，含场景快捷入口和历史记录链接 |
| 文本输入降级模式 | 无麦克风或 ASR 不可用时自动/手动切换为文本输入 |
| 浏览器 SpeechSynthesis 兜底 | TTS 不可用时使用浏览器内置语音朗读 |
| Docker 一键部署 | `docker-compose.yml` 启动 PostgreSQL 16 + Redis 7 |
| SQLite 开发模式 | 无 PostgreSQL/Redis 时自动降级为 SQLite + 内存缓存 |
| ASR 语言自动检测 | Whisper 自动检测输入语言 |
| 音频回放 | 整场录音和单轮录音均可回放，前端 `TranscriptReplayPanel` 播放 WAV/浏览器 TTS |

---

## 二、实际技术栈

### 前端

| 类别 | 技术 | 版本 |
|------|------|------|
| 框架 | Next.js (App Router + Turbopack) | 16.2.6 |
| UI 库 | React | 19.2.4 |
| 语言 | TypeScript | ^5 |
| 样式 | Tailwind CSS v4 + PostCSS | ^4 |
| 字体 | Geist (next/font/google) | - |
| 状态管理 | React Context（无第三方库） | - |
| 国际化 | 自建 `LocaleContext`（无 i18n 库） | - |
| 图表 | 纯 SVG `RadarChart`（无第三方图表库） | - |
| 测试框架 | Vitest（测试目录独立，不在 src 中） | - |

### 后端

| 类别 | 技术 | 版本 |
|------|------|------|
| Web 框架 | FastAPI | 0.115.6 |
| ASGI 服务器 | Uvicorn | 0.34.0 |
| ORM | SQLAlchemy (异步) | 2.0.36 |
| 数据验证 | Pydantic + pydantic-settings | 2.10.3 / 2.7.0 |
| 数据库 | PostgreSQL 16（生产）/ SQLite（开发兜底） | - |
| 数据库驱动 | asyncpg / aiosqlite | 0.30.0 / 0.20.0 |
| 缓存 | Redis 7（生产）/ 内存字典（开发兜底） | 5.2.1 |
| 认证 | JWT (python-jose + bcrypt) | ≥3.3.0 / ≥4.0.0 |
| 实时通信 | WebSocket (websockets) | 14.1 |
| LLM | DeepSeek V4 Flash (实时对话) / V4 Pro (报告) | - |
| LLM 客户端 | httpx (直接调用) / openai SDK | 0.28.1 / 2.41.0 |
| ASR | 本地 Whisper (openai-whisper) | 20250625 |
| TTS | EdgeTTS | 6.1.12 |
| 音频处理 | NumPy + PyTorch | ≥1.26.0 / ≥2.0.0 |
| PDF 解析 | pypdf | 5.1.0 |
| 文件上传 | python-multipart | 0.0.19 |
| 对象存储 | 火山引擎 TOS（tos SDK） | ≥2.6.0 |
| 测试框架 | pytest + pytest-asyncio | - |

### 基础设施

| 类别 | 技术 | 说明 |
|------|------|------|
| 容器化 | Docker Compose | PostgreSQL 16 Alpine + Redis 7 Alpine |
| 数据库迁移 | 原始 SQL 脚本（`backend/migrations/`） | Alembic 已安装但未集成到启动流程 |
| 包管理 | npm (前端) / pip (后端) | - |

---

## 三、与原架构设计的主要差异

### 3.1 LLM 层简化

| 架构设计 | 实际实现 | 差异说明 |
|----------|----------|----------|
| GPT-4o 主链路 + DeepSeek 报告 + Claude 润色 | DeepSeek V4 全家桶（Flash 对话 + Pro 报告） | 统一使用 DeepSeek API，未接入 OpenAI/Anthropic。节省成本和多供应商复杂度 |
| LLM Model Router（多模型路由） | 直接调用单一 API endpoint | 无路由/切换逻辑，所有 LLM 调用指向同一 DeepSeek 兼容 API |
| Response Cache / Semantic Cache | 无 LLM 响应缓存 | 对话每次都实时生成，仅在会话级别缓存 Prompt 模板 |
| Prompt Template Engine（模板渲染引擎） | 内联 Python f-string / `format()` | 无独立模板引擎，Prompt 在 `conversation_service.py` 中直接拼接 |

### 3.2 Agent 层简化

| 架构设计 | 实际实现 | 差异说明 |
|----------|----------|----------|
| 12 个专业化 Agent (Orchestrator + Specialists) | 服务层直接调用，无独立 Agent 框架 | Agent 职责被吸收到 `services/` 和 `websocket/handler.py` 中，调用链扁平 |
| Scene Router Agent | `scene_service.py` 静态配置 | 无需 LLM 参与场景路由，直接读 Python dict 配置 |
| Interview Agent (独立) | 合并到 `ConversationService` | 面试追问逻辑内嵌在对话 System Prompt 中 |
| Persona Agent (独立) | 角色配置作为 `SceneConfigForm` 的选项 | 无 JSON 配置驱动的 Persona Engine，Persona 模式通过 Prompt 文本体现 |
| STAR Agent | 简化集成在 `GrammarAgent` 和报告逻辑中 | 无独立的 STAR 四段式分析，报告中的 STAR 评估基于规则 + LLM |
| Replay Agent (独立) | `TimelineEvent` 由 `GrammarAgent` / `PronunciationAgent` / `ReportAgent` 直接写入 DB | 无独立 Replay Agent，事件在各分析环节生成 |
| Growth Coach Agent | ❌ 未实现 | 数据库预留字段，报告中无训练计划 |
| Interview Twin Agent | ❌ 未实现 | 数据库预留字段 |

### 3.3 实时语音链路简化

| 架构设计 | 实际实现 | 差异说明 |
|----------|----------|----------|
| 双层 VAD（客户端+服务端） | 单层：客户端能量 VAD + 服务端能量 VAD | 无 Silero 神经网络 VAD，两端均使用 RMS 能量阈值 |
| Semantic VAD（语义完整性判断） | 无 | Turn boundary 仅基于静音时长（500ms）判断 |
| Turn Manager（独立模块） | 在 WebSocket handler `ConnectionManager` 中内联处理 | 无独立 Turn Manager 类，状态机逻辑写在 `handler.py` 中 |
| Interrupt Controller（打断控制） | ❌ 未实现 | 不支持 Stress Mode 打断用户发言 |
| 流式 ASR（partial transcript） | 仅 final transcript | 不使用 ASR partial 结果，前端无实时字幕更新 |
| GPT-4o Realtime API | WebSocket + 本地 Whisper + HTTP LLM | 未使用任何 Realtime API，使用分段管线 |

### 3.4 TTS 简化

| 架构设计 | 实际实现 | 差异说明 |
|----------|----------|----------|
| CosyVoice2 主 + EdgeTTS 兜底 + FishSpeech 候选 | EdgeTTS 唯一 + 浏览器 SpeechSynthesis 兜底 | 仅使用 EdgeTTS 在线服务，无本地 TTS 模型部署 |
| 多音色（按 Persona 切换） | 单一音色 `en-US-JennyNeural` | 所有人格/角色共用同一个 TTS 语音 |
| TTS 缓存（CDN/Redis 常用片段） | 无缓存 | 每次实时合成 |

### 3.5 ASR 简化

| 架构设计 | 实际实现 | 差异说明 |
|----------|----------|----------|
| SenseVoice 主 + Whisper 兜底 + FunASR 本地 | 本地 Whisper 唯一方案 | 无多 ASR 供应商切换，运行时切换仅在同为 Whisper 的不同模型大小之间 |
| 流式 ASR 增量识别 | 非流式（等待静音后整段识别） | Whisper 在后台线程中转写完整音频段 |

### 3.6 消息队列与异步处理简化

| 架构设计 | 实际实现 | 差异说明 |
|----------|----------|----------|
| Redis Queue / Celery 任务队列 | Python `asyncio.create_task` 后台协程 | 无独立 Worker 进程，语法/发音分析在同一个 FastAPI 进程中异步执行 |
| Kafka/RabbitMQ (商业化) | 无消息队列 | 所有异步任务在进程内完成 |

### 3.7 存储层简化

| 架构设计 | 实际实现 | 差异说明 |
|----------|----------|----------|
| Vector DB (Embedding 匹配) | ❌ 无 | 无向量检索，简历/JD 匹配仅通过 LLM Prompt 实现 |
| 火山引擎 TOS 主存储 + 本地兜底 | TOS + 本地文件系统兜底 | 对象存储链路已实现但 TOS 为可选依赖，默认使用本地 `storage/` 目录 |

### 3.8 监控与运维简化

| 架构设计 | 实际实现 | 差异说明 |
|----------|----------|----------|
| OpenTelemetry + Sentry + 分布式追踪 | 仅 `AgentLog` 表记录 Agent 调用 | 无 APM/链路追踪/告警系统 |
| Metrics Dashboard (Grafana) | 无 | 无实时监控面板 |
| AI Quality Evaluation (Eval 平台) | 无 | 无模型输出质量评估 |
| `/health` 端点 | ✅ 已实现 | 返回环境、缓存状态、活跃 WebSocket 连接数 |

### 3.9 前端简化

| 架构设计 | 实际实现 | 差异说明 |
|----------|----------|----------|
| 独立的 API Gateway 层 (Auth/Rate Limit/Routing) | Next.js Route Middleware + Next.js rewrites 代理 | 无独立网关，鉴权在 middleware 和 API client 中处理 |
| Session Token (WebSocket 鉴权) | 无独立 session token | WebSocket 连接通过 URL path 中的 session_id 关联，前端 Auth Bearer token 已在 REST 层验证 |

### 3.10 架构差异总结

架构设计文档描述的是一个**7 层微服务化 Agent 平台**（含 12 个 Agent、消息队列、多模型路由、分布式追踪、AI 质量评估）。实际实现是一个**前后端分离的单体应用**：

- **后端**：单个 FastAPI 进程，WebSocket 和 REST 共存，异步任务在进程内通过 `asyncio` 完成
- **前端**：Next.js 单应用，无微前端，React Context 状态管理
- **AI 层**：单一 DeepSeek API 供应商，Agent 逻辑以 Python 函数/服务类形式组织
- **部署**：手动启动（`python main.py` + `npm run dev`），Docker 仅用于基础设施

这种简化在 **72 小时黑客松** 场景下是合理的取舍，核心体验闭环（场景选择→实时对话→纠错→报告→VAR 回放）完整可用。

---

## 四、已知问题与未完成项

### 4.1 未完成的 P2 功能

| 功能 | 当前状态 | 影响 |
|------|----------|------|
| Interview Twin（数字分身） | DB 预留 `twin_profile_json` 字段，无实现 | 无法展示长期职业画像和成长曲线 |
| Growth Coach（成长路线图） | DB 预留 `growth_plan_json` 字段，无实现 | 报告页缺少 7/14/30 天训练计划面板 |
| 压力面试模式 | 无打断控制/连续质疑/限时追问 | Stress Interview Persona 仅通过 Prompt 体现，无法真实打断用户 |
| 音素级发音分析 | 仅 WPM/停顿/置信度/填充词 | 无法检测元音准确度、重音位置等精细发音问题 |

### 4.2 已知技术问题

| 问题 | 严重程度 | 说明 |
|------|----------|------|
| ASR 非流式 | 中 | Whisper 整段识别而非流式，用户说完后需等待完整转写，增加感知延迟 |
| 无 ASR partial transcript | 低 | 前端无实时字幕更新，用户看不到"正在识别中"的中间结果 |
| TTS 单一音色 | 低 | 所有场景/角色共用 `en-US-JennyNeural`，无法体现 Persona 差异 |
| 无消息队列 | 低 | 语法/发音分析在主进程中异步执行，高并发时可能影响主链路延迟 |
| PyTorch 依赖体积大 | 低 | Whisper 依赖 PyTorch ≥2.0，后端环境体积约 2GB+，部署较重 |
| 无 CI/CD | 低 | 无 GitHub Actions 或其他自动化流水线，测试需手动运行 |
| Alembic 未集成 | 低 | 已安装 alembic 但迁移使用原始 SQL 脚本，无版本化管理 |
| 测试覆盖率有限 | 中 | 测试文件存在（后端 19 个 + 前端 7 个），但覆盖的边界场景和错误路径有限 |

### 4.3 稳定性与边界场景

| 场景 | 当前处理 | 改进空间 |
|------|----------|----------|
| LLM 响应超时 | 无显式超时处理 | 应添加 httpx timeout + 问题池兜底 |
| Whisper 模型加载慢 | 启动时预加载，但首次推理可能慢 | 可添加模型预热步骤 |
| 长篇对话内存占用 | 最近 6 轮上下文 | 上下文摘要（滚动压缩）已实现，但非 LLM 驱动的语义压缩 |
| WebSocket 并发连接 | 单进程处理 | 高并发场景缺乏连接池和负载均衡 |
| 数据库连接池 | SQLAlchemy 默认连接池 | 未显式配置池大小和超时参数 |
| 音频文件清理 | 无自动清理机制 | `storage/sessions/` 和 `storage/audio/` 会持续增长 |

### 4.4 代码质量

| 项目 | 状态 |
|------|------|
| 后端测试 | 19 个测试文件（服务/路由/Agent/WebSocket/集成），pytest |
| 前端测试 | 7 个测试文件（API client/类型契约/国际化/组件），Vitest |
| 代码注释 | 中文注释覆盖关键逻辑，符合 CLAUDE.md 规范 |
| 类型覆盖 | 前端 TypeScript 完整类型定义（`types/api.ts`），后端 Pydantic 模型完整 |
| Lint/Format | ESLint (前端)，无后端 linter 配置 |

### 4.5 文档完整性

| 文档 | 状态 |
|------|------|
| README.md | ✅ 完整（环境要求/快速启动/降级路径/检查清单） |
| PRD | ✅ OfferGPT产品需求文档.md v2.0 |
| 技术架构设计 | ✅ OfferGPT技术架构设计文档.md v2.0（1835 行） |
| 代码结构速查 | ✅ docs/前后端代码结构速查.md |
| 运行操作手册 | ✅ docs/运行操作手册.md |
| 环境变量文档 | ✅ docs/environment-variables.md |
| API 契约 | ✅ docs/agent-team/api-contract.md |
| 测试文档 | ✅ tests/README.md + docs/代码测试文档.md |
| 配置文档 | ✅ docs/configuration.md |

---

## 附录：项目统计

| 指标 | 数值 |
|------|------|
| 后端 Python 源文件 | ~25 个（含 services/realtime 子模块） |
| 前端 TypeScript/TSX 源文件 | ~45 个（含 pages/components/contexts/hooks） |
| 数据库表 | 8 张（users/resumes/jobs/scene_presets/interviews/timeline_events/reports/agent_logs） |
| REST API 端点 | 18 个 |
| WebSocket 消息类型 | 7 种上行 + 12 种下行 |
| 支持场景 | 3 个（interview/restaurant/meeting） |
| Git 提交数 | 63 个 |
| 前端依赖（运行时） | 3 个（next/react/react-dom） |
| 后端依赖（运行时） | 21 个 |
| 测试文件 | 26 个（后端 19 + 前端 7） |
