# AgentTeam 后端开发文档

## 文档目标

本文档面向后端 Agent，负责 OfferGPT 的 API、实时语音链路、Agent 编排、数据存储、报告生成和稳定性兜底。后端使用 FastAPI + WebSocket + PostgreSQL + Redis 实现，三大场景（面试/点餐/会议）均已完整实现。

## 开发优先级

| 优先级 | 场景模块 | 后端目标 | 当前状态 |
|---|---|---|---|
| P0 | 面试场景 | 完成简历/JD 解析、面试会话、实时问答、面试 Agent、Offer Report 和 VAR | ✅ 已实现 |
| P1 | 餐厅点餐 | 复用场景会话能力，新增点餐配置、角色 Prompt 和点餐报告 | ✅ 已实现 |
| P2 | 商务会议 | 复用场景会话能力，新增会议配置、会议角色和会议报告 | ✅ 已实现 |

## 后端职责边界

后端负责业务规则、实时链路、Agent 调用和数据持久化，不负责页面布局和视觉展示。

| 模块 | 后端职责 | 输出给前端 |
|---|---|---|
| 场景管理 | 加载三大场景、Persona、评分权重和 Prompt 配置 | 场景配置 JSON |
| 简历/JD 解析 | 抽取文本并生成结构化画像 | `resumeId`、`jobId`、解析摘要 |
| 会话管理 | 创建、恢复、结束训练会话 | `sessionId`、`sessionToken`、状态 |
| 实时服务 | 接收音频、ASR、Turn 判断、TTS 下发 | 字幕、AI 文本流、AI 音频流 |
| Agent 编排 | 路由 Conversation、Grammar、Report 等 Agent | 回复、评分信号、事件 |
| 报告生成 | 生成场景报告、成长建议和 VAR 证据链 | report JSON |
| 可观测性 | 记录日志、耗时、错误和 Agent 调用信息 | 调试面板数据 |

## 推荐技术栈

| 层级 | 推荐方案 | 说明 |
|---|---|---|
| API 服务 | FastAPI | 适合 Python AI 生态和结构化接口 |
| 实时通信 | WebSocket | 72 小时版本比 WebRTC 更容易落地 |
| 数据库 | PostgreSQL | 存储用户、简历、会话、事件和报告 |
| 缓存 | Redis | 存储会话状态、ASR partial、Prompt 缓存 |
| ASR | Whisper / SenseVoice | 主路径使用云服务或可用 API |
| LLM | GPT-4o + DeepSeek | 实时对话主模型和报告分析模型分离 |
| TTS | EdgeTTS / CosyVoice2 | EdgeTTS 作为比赛兜底 |

## 服务模块划分

| 模块 | 说明 |
|---|---|
| `sceneService` | 管理三大场景配置、Persona、阶段和评分权重 |
| `resumeService` | 处理简历上传、文本抽取和结构化解析 |
| `jobService` | 处理 JD 输入、岗位画像和难度判断 |
| `sessionService` | 创建、查询、结束和恢复会话 |
| `realtimeService` | 管理 WebSocket、音频帧、ASR、TTS |
| `agentOrchestrator` | 编排 Scene Router、Persona、Conversation、Grammar、Report 等 Agent |
| `timelineService` | 生成和查询 VAR 时间轴事件 |
| `reportService` | 聚合评分信号并生成场景报告 |
| `monitorService` | 写入 Agent 日志、接口耗时和错误信息 |

## Agent 调用策略

实时主链路只允许低延迟 Agent 参与，分析类 Agent 必须异步执行。

| Agent | 调用时机 | 同步性 |
|---|---|---|
| Scene Router Agent | 创建会话时 | 同步 |
| Persona Agent | 创建会话时 | 同步 |
| Conversation Agent | 每轮用户回答结束后 | 同步 |
| Interview Agent | 面试场景追问时 | 同步 |
| Grammar Agent | 每轮回答后 | 异步，严重错误可回传轻纠正 |
| Pronunciation Agent | 每轮回答后 | 异步 |
| STAR Agent | 面试行为题回答后 | 异步 |
| Replay Agent | 收到分析信号后 | 异步 |
| Report Agent | 会话结束后 | 异步或同步等待 |
| Growth Coach Agent | 报告生成后 | 异步 |

## 实时语音链路

```text
前端发送 audio.input
  ↓
Realtime Service 校验 sessionToken
  ↓
写入会话音频队列
  ↓
ASR 输出 partial 和 final
  ↓
Turn Manager 判断本轮结束
  ↓
Agent Orchestrator 生成 AI 回复
  ↓
TTS 生成音频片段
  ↓
WebSocket 下发字幕、文本、音频和事件
```

## 数据库表范围

| 表 | 用途 |
|---|---|
| `users` | 用户基础信息 |
| `resumes` | 简历原文、文件地址和结构化画像 |
| `jobs` | JD 原文、岗位画像和难度等级 |
| `scenePresets` | 三大场景 Persona、阶段配置和评分规则 |
| `interviews` | 多场景训练会话（面试/点餐/会议） |
| `timelineEvents` | VAR 时间轴事件 |
| `reports` | 场景报告、成长计划和数字分身 |
| `agentLogs` | Agent 输入摘要、输出、模型、耗时和错误 |

## Redis Key 约定

| Key | 用途 | TTL |
|---|---|---:|
| `session:{sessionId}` | 实时会话状态 | 2h |
| `scene:{scene}:{topic}` | 场景配置缓存 | 24h |
| `persona:{personaMode}:{jobHash}` | Persona 上下文 | 24h |
| `jd:{jdHash}` | JD 解析结果 | 7d |
| `asr:partial:{sessionId}` | 最新字幕 | 5m |
| `report:{sessionId}` | 报告缓存 | 24h |

## 降级策略

- ASR 不可用时，允许前端切换文本输入。
- TTS 不可用时，仍返回 `agent.text.delta`。
- LLM 超时后，使用场景问题池生成保守追问。
- VAR 生成失败时，结束后基于 transcript 补偿生成。
- 报告生成失败时，返回基础评分模板和错误标记。

## 后端验收标准

- `GET /api/scenes` 返回三大场景配置，各场景可通过环境变量独立控制开关。
- `POST /api/interviews` 可以创建任意场景的训练会话。
- WebSocket 能接收 `audio.input` 并返回至少一种字幕或 AI 文本消息。
- 任意场景会话结束后可以生成对应的场景报告和 VAR 事件。
- 关键 Agent 调用必须写入 `agentLogs`，方便答辩展示工程深度。
- 新增功能不得破坏现有场景的接口、实时链路或报告功能。
