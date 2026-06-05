# OfferGPT 配置文档

## 文档目标

本文档根据 `OfferGPT技术架构设计文档.md` 和 `docs/agent-team` 开发文档整理项目启动前需要完成的配置点。当前配置优先服务 P0 面试场景闭环，确保可以完成首页进入、简历/JD、创建会话、实时对话、轻纠正、Offer Report 和 VAR 时间轴。

## 配置优先级


| 优先级   | 配置范围                                                   | 当前策略          |
| ----- | ------------------------------------------------------ | ------------- |
| P0 必填 | 面试场景、基础 API、WebSocket、LLM、ASR/TTS 兜底、数据库、Redis、Demo 数据 | 先完成并用于首个可运行版本 |
| P1 后续 | 餐厅点餐场景、服务员角色、点餐报告                                      | P0 回归通过后启用    |
| P2 后续 | 商务会议场景、会议角色、会议报告                                       | P0/P1 回归通过后启用 |


## 一、环境变量配置

建议在项目根目录准备 `.env.example` 和本地 `.env.local`。`.env.local` 不允许提交，`.env.example` 只保留变量名和说明。

环境变量的具体生成方式见 `docs/environment-variables.md`。Windows 使用 `scripts/setup-env.ps1`，Linux/macOS 使用 `scripts/setup-env.sh`，脚本会基于默认配置生成本地 `.env.local`。

### 1.0 配置加载策略

项目采用“默认配置 + 环境变量覆盖”的方案。代码中只保留可公开的默认值，例如默认场景、默认模型名称、超时时间和功能开关；所有服务地址、账号、密码、API Key、TOS 密钥等敏感信息必须通过环境变量注入，不允许写入代码、README 或 PR 描述。

推荐加载顺序如下：

1. 读取代码内默认配置。
2. 读取环境变量覆盖默认配置。
3. 启动时校验 P0 必填项，缺失敏感配置时直接给出中文错误。
4. Demo 模式允许 ASR、TTS、LLM 使用 mock 兜底，但数据库、Redis 和 TOS 仍使用服务器配置。

### 1.1 前后端通用配置


| 变量名                                 | 是否必填 | 示例值                     | 说明                                        |
| ----------------------------------- | ---- | ----------------------- | ----------------------------------------- |
| `APP_ENV`                           | 是    | `development`           | 运行环境，可选 `development`、`demo`、`production` |
| `APP_NAME`                          | 是    | `OfferGPT`              | 应用名称                                      |
| `APP_BASE_URL`                      | 是    | `http://localhost:3000` | 前端访问地址                                    |
| `API_BASE_URL`                      | 是    | `http://localhost:8000` | 后端 REST API 地址                            |
| `WS_BASE_URL`                       | 是    | `ws://localhost:8000`   | 后端 WebSocket 地址                           |
| `DEFAULT_SCENE`                     | 是    | `interview`             | P0 默认启用面试场景                               |
| `ENABLE_RESTAURANT_SCENE`           | 是    | `false`                 | P1 点餐场景开关                                 |
| `ENABLE_MEETING_SCENE`              | 是    | `false`                 | P2 会议场景开关                                 |
| `REALTIME_LIGHT_CORRECTION_ENABLED` | 是    | `true`                  | 是否默认开启实时轻纠正                               |
| `DEMO_MODE_ENABLED`                 | 是    | `true`                  | 是否启用无麦克风 Demo 兜底                          |


### 1.2 后端服务配置


| 变量名                       | 是否必填 | 示例值                         | 说明              |
| ------------------------- | ---- | --------------------------- | --------------- |
| `BACKEND_HOST`            | 是    | `0.0.0.0`                   | FastAPI 监听地址    |
| `BACKEND_PORT`            | 是    | `8000`                      | FastAPI 端口      |
| `CORS_ALLOW_ORIGINS`      | 是    | `http://localhost:3000`     | 前端跨域白名单         |
| `SESSION_TOKEN_SECRET`    | 是    | `replace-with-local-secret` | 会话令牌签名密钥，本地自行生成 |
| `SESSION_TTL_SECONDS`     | 是    | `7200`                      | 实时会话默认有效期       |
| `REQUEST_TIMEOUT_SECONDS` | 是    | `30`                        | 后端外部服务请求超时      |
| `LOG_LEVEL`               | 是    | `INFO`                      | 日志级别            |


### 1.3 数据库与缓存配置


| 变量名                       | 是否必填  | 示例值                                                    | 说明                          |
| ------------------------- | ----- | ------------------------------------------------------ | --------------------------- |
| `DATABASE_JDBC_URL`       | 是     | `jdbc:postgresql://118.145.179.97:5432/offergpt`       | 已连通的服务器 PostgreSQL JDBC 地址 |
| `DATABASE_URL`            | 是     | `postgresql://118.145.179.97:5432/offergpt`            | Python/FastAPI 兼容连接串；如驱动要求账号密码，可在 `.env.secrets.local` 中覆盖 |
| `REDIS_URL`               | 是     | `redis://:password@118.145.179.97:6379/1`              | 服务器 Redis 连接串，必须使用 DB1，DB0 已有数据不可使用 |
| `REDIS_HOST`              | 是     | `118.145.179.97`                                       | Redis 服务器地址 |
| `REDIS_PORT`              | 是     | `6379`                                                 | Redis 端口 |
| `REDIS_DB`                | 是     | `1`                                                    | Redis 数据库编号，固定使用 DB1 |
| `REDIS_PASSWORD`          | 是     | 空                                                      | Redis 密码，不允许提交 |
| `OBJECT_STORAGE_PROVIDER` | 是     | `tos`                                                  | 音频、简历和上传文件统一使用 TOS          |
| `TOS_ENDPOINT`            | 是     | `tos-cn-guangzhou.volces.com`                          | TOS Endpoint，广州地域 |
| `TOS_REGION`              | 是     | `cn-guangzhou`                                         | TOS 地域 |
| `TOS_BUCKET`              | 是     | `offer`                                                | TOS Bucket 名称 |
| `TOS_ACL`                 | 是     | `private`                                              | 默认使用私有读写，简历、音频和报告不公开 |
| `TOS_ACCESS_KEY_ID`       | 是     | 空                                                      | TOS Access Key，不允许提交        |
| `TOS_SECRET_ACCESS_KEY`   | 是     | 空                                                      | TOS Secret Key，不允许提交        |
| `VOLCENGINE_ACCESS_KEY_ID` | 是     | 空                                                      | 火山引擎访问密钥 ID，和 TOS Access Key 保持一致 |
| `VOLCENGINE_SECRET_ACCESS_KEY` | 是 | 空                                                      | 火山引擎访问密钥 Secret，和 TOS Secret Key 保持一致 |
| `TOS_PUBLIC_BASE_URL`     | P0 可选 | 空                                                      | 如使用 CDN 或公开读地址，在此配置         |
| `LOCAL_STORAGE_DIR`       | 仅本地兜底 | `./storage`                                            | 只在 TOS 不可用的本地调试场景使用         |


### 1.4 AI 服务配置


| 变量名                           | 是否必填              | 示例值                         | 说明                                       |
| ----------------------------- | ----------------- | --------------------------- | ---------------------------------------- |
| `LLM_PROVIDER`                | 是                 | `deepseek`                  | 主 LLM 服务商                                |
| `LLM_API_BASE_URL`            | 是                 | `https://api.deepseek.com/anthropic` | LLM API 地址，默认使用 DeepSeek Anthropic 兼容接口 |
| `LLM_MODEL`                   | 是                 | `deepseekV4pro`             | 实时对话主模型                                  |
| `LLM_REPORT_MODEL`            | 是                 | `deepseekV4pro`             | 报告生成模型                                   |
| `LLM_API_KEY`                 | 是                 | 空                           | 当前主 LLM API Key，统一从环境变量读取                |
| `DEEPSEEK_API_BASE_URL`       | 是                 | `https://api.deepseek.com/anthropic` | DeepSeek API 地址                          |
| `DEEPSEEK_API_KEY`            | 是                 | 空                           | DeepSeek API Key，不允许提交                   |
| `OPENAI_API_KEY`              | 仅切换 OpenAI 时必填    | 空                           | OpenAI API Key，不允许提交                     |
| `ASR_PROVIDER`                | 是                 | `whisper`                   | ASR 服务商，可选 `whisper`、`sensevoice`、`mock` |
| `ASR_API_BASE_URL`            | 使用云 ASR 时必填       | 空                           | ASR API 地址                               |
| `ASR_API_KEY`                 | 使用云 ASR 时必填       | 空                           | ASR API Key，不允许提交                        |
| `ASR_MODEL`                   | 是                 | `whisper-1`                 | ASR 模型名                                  |
| `TTS_PROVIDER`                | 是                 | `edgeTts`                   | TTS 服务商，可选 `edgeTts`、`cosyVoice`、`mock`  |
| `TTS_API_BASE_URL`            | 使用云 TTS 时必填       | 空                           | TTS API 地址                               |
| `TTS_API_KEY`                 | 使用云 TTS 时必填       | 空                           | TTS API Key，不允许提交                        |
| `TTS_VOICE`                   | 是                 | `en-US-JennyNeural`         | 默认英文语音                                   |
| `AI_PROVIDER_TIMEOUT_SECONDS` | 是                 | `20`                        | AI 服务调用超时时间                              |


### 1.5 前端配置


| 变量名                                   | 是否必填 | 示例值                     | 说明               |
| ------------------------------------- | ---- | ----------------------- | ---------------- |
| `NEXT_PUBLIC_API_BASE_URL`            | 是    | `http://localhost:8000` | 浏览器访问后端 API      |
| `NEXT_PUBLIC_WS_BASE_URL`             | 是    | `ws://localhost:8000`   | 浏览器访问 WebSocket  |
| `NEXT_PUBLIC_DEFAULT_SCENE`           | 是    | `interview`             | 默认场景             |
| `NEXT_PUBLIC_DEMO_MODE_ENABLED`       | 是    | `true`                  | 前端是否展示 Demo 兜底入口 |
| `NEXT_PUBLIC_ENABLE_RESTAURANT_SCENE` | 是    | `false`                 | 是否展示可进入的点餐场景     |
| `NEXT_PUBLIC_ENABLE_MEETING_SCENE`    | 是    | `false`                 | 是否展示可进入的会议场景     |


## 二、场景配置

场景配置由后端 `sceneService` 统一加载，并通过 `GET /api/scenes` 返回给前端。P0 阶段只允许 `interview` 可用，`restaurant` 和 `meeting` 可以展示为占位入口，但不得影响面试闭环。

### 2.1 P0 面试场景配置


| 配置项                       | 建议值                                                               | 说明                   |
| ------------------------- | ----------------------------------------------------------------- | -------------------- |
| `scene`                   | `interview`                                                       | 场景枚举                 |
| `enabled`                 | `true`                                                            | P0 必须启用              |
| `defaultTopic`            | `behavioral`                                                      | 默认行为面试               |
| `topics`                  | `behavioral`、`technical`、`culture`                                | P0 可先实现 `behavioral` |
| `roleModes`               | `founder`、`engineeringLeader`                                     | P0 至少实现一种 Persona    |
| `defaultRoleMode`         | `founder`                                                         | Demo 默认角色            |
| `durationMinutes`         | `15`                                                              | 默认训练时长               |
| `difficultyLevel`         | `middle`                                                          | 默认难度                 |
| `realtimeLightCorrection` | `true`                                                            | 默认开启轻纠正              |
| `rubric`                  | `english`、`logic`、`confidence`、`star`、`technical`、`communication` | Offer Score 评分维度     |


### 2.2 P1 点餐场景配置


| 配置项               | 建议值                                                                                | 说明         |
| ----------------- | ---------------------------------------------------------------------------------- | ---------- |
| `scene`           | `restaurant`                                                                       | 场景枚举       |
| `enabled`         | `false`                                                                            | P0 阶段禁用    |
| `releasePriority` | `P1`                                                                               | P0 回归通过后启用 |
| `topics`          | `reservation`、`ordering`、`complaint`、`checkout`                                    | 点餐子主题      |
| `roleModes`       | `friendlyWaiter`、`busyWaiter`、`impatientWaiter`                                    | 服务员角色      |
| `rubric`          | `english`、`politeness`、`functionalPhrases`、`taskCompletion`、`pronunciationFluency` | 点餐报告维度     |


### 2.3 P2 会议场景配置


| 配置项               | 建议值                                                                       | 说明          |
| ----------------- | ------------------------------------------------------------------------- | ----------- |
| `scene`           | `meeting`                                                                 | 场景枚举        |
| `enabled`         | `false`                                                                   | P0/P1 稳定后启用 |
| `releasePriority` | `P2`                                                                      | 后续增量        |
| `topics`          | `selfIntroduction`、`projectUpdate`、`suggestion`、`clarification`、`summary` | 会议子主题       |
| `roleModes`       | `meetingHost`、`colleague`、`manager`                                       | 会议角色        |
| `rubric`          | `english`、`logic`、`communication`、`functionalPhrases`、`meetingControl`    | 会议报告维度      |


## 三、Persona 与 Prompt 配置

Persona 和 Prompt 不应硬编码在业务逻辑中。P0 可以先使用 JSON 配置或数据库 `scenePresets` 表保存，后续再扩展为后台配置页面。

### 3.1 Persona 必配项


| 配置项                  | 是否必填 | 说明           |
| -------------------- | ---- | ------------ |
| `personaId`          | 是    | 例如 `founder` |
| `displayName`        | 是    | 前端展示名称       |
| `description`        | 是    | 角色说明         |
| `tone`               | 是    | 语气风格         |
| `questionBias`       | 是    | 提问偏好         |
| `followUpPolicy`     | 是    | 追问策略         |
| `scoringWeights`     | 是    | 评分权重         |
| `interruptionPolicy` | 是    | 打断规则         |
| `fallbackQuestions`  | 是    | LLM 失败时的问题池  |


### 3.2 Prompt 模板配置


| 模板                   | 使用时机          | P0 要求  |
| -------------------- | ------------- | ------ |
| `sceneRouterPrompt`  | 创建会话时加载场景配置   | 必填     |
| `personaPrompt`      | 创建面试会话时生成角色策略 | 必填     |
| `conversationPrompt` | 每轮实时回复        | 必填     |
| `grammarPrompt`      | 每轮异步语法分析      | 必填     |
| `starPrompt`         | 面试行为题分析       | 必填     |
| `reportPrompt`       | 会话结束生成报告      | 必填     |
| `restaurantPrompt`   | 点餐场景          | P1 后启用 |
| `meetingPrompt`      | 会议场景          | P2 后启用 |


## 四、接口与 WebSocket 配置

### 4.1 REST API 配置点


| 接口                                        | 配置依赖                   | P0 状态 |
| ----------------------------------------- | ---------------------- | ----- |
| `GET /api/scenes`                         | 场景配置、功能开关              | 必须可用  |
| `POST /api/resumes`                       | 文件上传大小、存储目录、解析策略       | 必须可用  |
| `POST /api/jobs`                          | JD 最大长度、解析模型           | 必须可用  |
| `POST /api/interviews`                    | 场景开关、会话 TTL、Persona 配置 | 必须可用  |
| `GET /api/interviews/{sessionId}`         | 数据库与会话状态               | 必须可用  |
| `POST /api/interviews/{sessionId}/finish` | Report Agent、队列或同步报告策略 | 必须可用  |
| `GET /api/interviews/{sessionId}/events`  | VAR 事件存储               | 必须可用  |
| `GET /api/interviews/{sessionId}/report`  | 报告存储与生成状态              | 必须可用  |


### 4.2 WebSocket 配置点


| 配置项                        | 建议值                                                                                                                               | 说明              |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| `audioCodec`               | `pcm16`                                                                                                                           | P0 默认音频编码       |
| `sampleRate`               | `16000`                                                                                                                           | P0 默认采样率        |
| `audioChunkMs`             | `20-100`                                                                                                                          | 单个音频分片大小        |
| `heartbeatIntervalSeconds` | `15`                                                                                                                              | 心跳间隔            |
| `reconnectAttempts`        | `1`                                                                                                                               | 前端断线后至少重连一次     |
| `maxTurnSilenceMs`         | `900`                                                                                                                             | 判断用户一轮回答结束的静音阈值 |
| `maxAnswerSeconds`         | `120`                                                                                                                             | 面试回答最长时间        |
| `enabledMessageTypes`      | `audio.input`、`asr.partial`、`asr.final`、`agent.text.delta`、`tts.audio.delta`、`timeline.event`、`correction.light`、`control.finish` | P0 必须兼容         |


## 五、数据库与 Redis 配置

### 5.1 数据库表配置

P0 阶段至少准备以下表或等价数据结构：


| 表名               | P0 用途                    |
| ---------------- | ------------------------ |
| `users`          | 用户基础信息，可先使用匿名用户          |
| `resumes`        | 简历原文、文件地址、结构化画像          |
| `jobs`           | JD 原文、岗位画像、难度等级          |
| `scenePresets`   | 面试 Persona、阶段配置、评分规则     |
| `interviews`     | 训练会话，P0 面试优先             |
| `timelineEvents` | VAR 时间轴事件                |
| `reports`        | Offer Report、成长建议、VAR 证据 |
| `agentLogs`      | Agent 输入摘要、输出、模型、耗时和错误   |


### 5.2 Redis Key 配置


| Key 模板                            | TTL   | 说明            |
| --------------------------------- | ----- | ------------- |
| `session:{sessionId}`             | `2h`  | 实时会话状态        |
| `scene:{scene}:{topic}`           | `24h` | 场景配置缓存        |
| `persona:{personaMode}:{jobHash}` | `24h` | Persona 上下文缓存 |
| `jd:{jdHash}`                     | `7d`  | JD 解析缓存       |
| `asr:partial:{sessionId}`         | `5m`  | 最新实时字幕        |
| `report:{sessionId}`              | `24h` | 报告缓存          |


## 六、Demo 与降级配置

比赛 Demo 必须可以在外部服务波动时继续演示。


| 配置项                          | 建议值             | 说明                     |
| ---------------------------- | --------------- | ---------------------- |
| `ENABLE_TEXT_INPUT_FALLBACK` | `true`          | ASR 或麦克风不可用时允许文本输入     |
| `ENABLE_MOCK_ASR`            | `true`          | 本地无 ASR Key 时可使用预置字幕   |
| `ENABLE_MOCK_TTS`            | `true`          | TTS 不可用时仍展示文本          |
| `ENABLE_PRESET_DEMO_DATA`    | `true`          | 提供预置简历、JD、会话和报告        |
| `ENABLE_REPORT_RETRY`        | `true`          | 报告失败时允许重试              |
| `REPORT_FALLBACK_MODE`       | `basicTemplate` | Report Agent 失败时返回基础报告 |


## 七、测试配置


| 配置项                     | 建议值                 | 说明                     |
| ----------------------- | ------------------- | ---------------------- |
| `TEST_DEFAULT_SCENE`    | `interview`         | P0 测试默认场景              |
| `TEST_USE_MOCK_AI`      | `true`              | 接口测试阶段避免依赖真实模型         |
| `TEST_USE_MOCK_AUDIO`   | `true`              | WebSocket 测试可使用预置音频或文本 |
| `TEST_DEMO_RESUME_PATH` | `./demo/resume.txt` | Demo 简历路径              |
| `TEST_DEMO_JD_PATH`     | `./demo/jd.txt`     | Demo JD 路径             |


P0 配置完成后，至少验证以下路径：

1. `GET /api/scenes` 返回 `interview.enabled = true`。
2. `POST /api/resumes` 返回 `resumeId`。
3. `POST /api/jobs` 返回 `jobId`。
4. `POST /api/interviews` 返回 `sessionId`、`sessionToken` 和 `websocketUrl`。
5. WebSocket 能接收 `audio.input`，并返回 `asr.partial` 或 `agent.text.delta`。
6. `POST /api/interviews/{sessionId}/finish` 后可以获取报告和 VAR 事件。

## 八、配置完成顺序

建议按以下顺序完成配置，避免前后端互相等待：

1. 配置 `.env.example` 和本地 `.env.local`。
2. 配置服务器 PostgreSQL 与服务器 Redis 连接。
3. 配置 TOS Endpoint、Bucket、Region 和访问密钥。
4. 配置 P0 `interview` 场景和 `founder` Persona。
5. 配置 LLM、ASR、TTS 的 API 地址、Key、默认模型与 mock 兜底。
6. 配置 `GET /api/scenes`、`POST /api/interviews` 所需的场景开关。
7. 配置前端 `NEXT_PUBLIC_API_BASE_URL` 和 `NEXT_PUBLIC_WS_BASE_URL`。
8. 配置 Demo 预置简历、JD、会话、报告和 VAR 数据。
9. 配置测试开关并跑通 P0 核心验收用例。

## 九、待确认事项


| 问题                             | 建议默认值 | 是否已确认 |
| ------------------------------ | ----- | ----- |
| 后端框架是否使用 FastAPI               | 是     | 已确认   |
| 前端框架是否使用 Next.js               | 是     | 已确认   |
| LLM API 地址和 Key 是否使用环境变量覆盖默认配置 | 是     | 已确认   |
| P0 主 LLM 是否使用 DeepSeek V4 Pro  | 是     | 已确认   |
| ASR 主路径是否使用 Whisper            | 是     | 已确认   |
| TTS 兜底是否使用 EdgeTTS             | 是     | 已确认   |
| 数据库是否使用服务器 PostgreSQL          | 是     | 已确认   |
| Redis 是否使用服务器 Redis            | 是     | 已确认   |
| 对象存储是否使用 TOS                   | 是     | 已确认   |
| P0 是否只启用面试场景                   | 是     | 已确认   |
| 点餐和会议是否先显示占位入口                 | 是     | 已确认   |


