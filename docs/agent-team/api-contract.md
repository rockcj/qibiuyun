# AgentTeam 接口契约文档

## 文档目标

本文档定义 OfferGPT 前后端协作所需的 REST API 与 WebSocket 消息契约。接口命名以 72 小时 MVP 可落地为优先，P0 阶段先完整支持面试场景，餐厅点餐和商务会议分别作为 P1/P2 后续模块接入。

## 接口开发优先级

| 优先级 | 场景模块 | 接口范围 | 进入下一阶段条件 |
|---|---|---|---|
| P0 | 面试场景 | 场景配置、简历、JD、面试会话、WebSocket、Offer Report、VAR | 面试接口测试全部通过 |
| P1 | 餐厅点餐 | 点餐配置、点餐会话、点餐报告 | P0 面试接口回归通过 |
| P2 | 商务会议 | 会议配置、会议会话、会议报告 | P0/P1 接口回归通过 |

## 通用约定

| 项目 | 约定 |
|---|---|
| 数据格式 | REST 请求和响应默认使用 JSON |
| 时间格式 | 使用 ISO 8601 字符串或毫秒时间戳 |
| ID 命名 | 对外使用 `sessionId`，数据库可沿用 `interviewId` |
| 场景枚举 | P0 启用 `interview`，P1/P2 再启用 `restaurant`、`meeting` |
| 错误响应 | 必须包含 `errorCode`、`message`、`requestId` |
| 鉴权 | MVP 可使用临时 `sessionToken`，后续接入用户登录 |

## 通用错误格式

```json
{
  "errorCode": "SESSION_NOT_FOUND",
  "message": "会话不存在或已过期",
  "requestId": "req_123"
}
```

## REST API

### 获取场景配置

```http
GET /api/scenes
```

响应：

```json
{
  "scenes": [
    {
      "scene": "interview",
      "displayName": "求职面试",
      "enabled": true,
      "topics": [
        {
          "topic": "behavioral",
          "displayName": "行为面试"
        }
      ],
      "roleModes": [
        {
          "roleMode": "founder",
          "displayName": "Founder Mode"
        }
      ],
      "rubric": ["english", "logic", "confidence", "star", "technical", "communication"]
    },
    {
      "scene": "restaurant",
      "displayName": "餐厅点餐",
      "enabled": false,
      "releasePriority": "P1",
      "disabledReason": "P0 阶段先完成面试闭环"
    },
    {
      "scene": "meeting",
      "displayName": "商务会议",
      "enabled": false,
      "releasePriority": "P2",
      "disabledReason": "P0/P1 稳定后再接入"
    }
  ]
}
```

### 上传简历

```http
POST /api/resumes
Content-Type: multipart/form-data
```

响应：

```json
{
  "resumeId": "res_123",
  "parseStatus": "success",
  "parsedProfile": {
    "skills": ["Python", "FastAPI", "LLM", "React"],
    "projects": [
      {
        "name": "AI Interview System",
        "role": "Backend Developer",
        "impact": "Reduced response latency by 35%"
      }
    ],
    "riskSignals": ["Few quantified business outcomes"]
  }
}
```

### 创建 JD

```http
POST /api/jobs
Content-Type: application/json
```

请求：

```json
{
  "title": "AI Application Engineer",
  "company": "Demo Company",
  "jdText": "We are looking for an engineer with LLM application experience..."
}
```

响应：

```json
{
  "jobId": "job_123",
  "parsedProfile": {
    "requiredSkills": ["LLM", "Python", "RAG", "API Design"],
    "competencies": ["systemDesign", "problemSolving", "communication"],
    "difficultyLevel": "middle"
  }
}
```

### 创建场景会话

```http
POST /api/interviews
Content-Type: application/json
```

面试场景请求：

```json
{
  "scene": "interview",
  "topic": "behavioral",
  "roleMode": "founder",
  "resumeId": "res_123",
  "jobId": "job_123",
  "personaMode": "founder",
  "durationMinutes": 15,
  "difficultyLevel": "senior",
  "realtimeLightCorrection": true
}
```

点餐场景请求（P1 后启用，P0 阶段不得影响面试接口）：

```json
{
  "scene": "restaurant",
  "topic": "ordering",
  "roleMode": "busyWaiter",
  "durationMinutes": 8,
  "difficultyLevel": "daily",
  "realtimeLightCorrection": true
}
```

响应：

```json
{
  "sessionId": "iv_123",
  "sessionToken": "signed_session_token",
  "websocketUrl": "wss://api.offergpt.ai/ws/interviews/iv_123",
  "scene": "interview",
  "topic": "behavioral",
  "persona": {
    "mode": "founder",
    "displayName": "Founder Mode"
  },
  "status": "created"
}
```

### 获取会话详情

```http
GET /api/interviews/{sessionId}
```

响应：

```json
{
  "sessionId": "iv_123",
  "scene": "interview",
  "topic": "behavioral",
  "roleMode": "founder",
  "status": "running",
  "startedAt": "2026-06-05T03:30:00Z",
  "durationSeconds": 180
}
```

### 结束会话

```http
POST /api/interviews/{sessionId}/finish
```

响应：

```json
{
  "sessionId": "iv_123",
  "status": "completed",
  "reportStatus": "generating"
}
```

### 获取 VAR 时间轴

```http
GET /api/interviews/{sessionId}/events
```

响应：

```json
{
  "events": [
    {
      "eventId": "evt_001",
      "turnId": "turn_003",
      "eventType": "grammarIssue",
      "severity": "medium",
      "title": "严重语法错误",
      "description": "用户使用了 I have did，应改为 I have done。",
      "startMs": 31020,
      "endMs": 34720,
      "transcriptSnippet": "I have did a project.",
      "suggestion": "I have done a project."
    }
  ]
}
```

### 获取场景报告

```http
GET /api/interviews/{sessionId}/report
```

响应：

```json
{
  "reportId": "rep_123",
  "sessionId": "iv_123",
  "scene": "interview",
  "scoreName": "Offer Score",
  "sceneScore": 78,
  "offerProbability": "mediumHigh",
  "dimensionScores": {
    "english": 82,
    "logic": 74,
    "confidence": 70,
    "star": 68,
    "technical": 80,
    "communication": 77
  },
  "strengths": [
    {
      "title": "技术项目表达清晰",
      "evidenceEventIds": ["evt_010"],
      "description": "用户能说明项目职责和关键技术选择。"
    }
  ],
  "risks": [
    {
      "title": "STAR 结果描述不足",
      "evidenceEventIds": ["evt_003"],
      "suggestion": "每个项目故事最后补充可量化结果。"
    }
  ],
  "finalRecommendation": "具备初筛通过潜力，需要加强 STAR 结果表达。"
}
```

## WebSocket 契约

连接地址：

```text
wss://api.offergpt.ai/ws/interviews/{sessionId}?token={sessionToken}
```

### 用户音频上行

```json
{
  "type": "audio.input",
  "sessionId": "iv_123",
  "sequenceId": 128,
  "timestampMs": 31020,
  "codec": "pcm16",
  "sampleRate": 16000,
  "payload": "base64_audio_chunk"
}
```

### ASR 实时字幕

```json
{
  "type": "asr.partial",
  "sessionId": "iv_123",
  "turnId": "turn_006",
  "startMs": 31000,
  "endMs": 34720,
  "partialTranscript": "I would like to"
}
```

### ASR 最终文本

```json
{
  "type": "asr.final",
  "sessionId": "iv_123",
  "turnId": "turn_006",
  "startMs": 31000,
  "endMs": 36500,
  "finalTranscript": "I led the backend design for an AI interview system."
}
```

### AI 文本流

```json
{
  "type": "agent.text.delta",
  "sessionId": "iv_123",
  "turnId": "turn_006",
  "delta": "You mentioned leading the backend design. What specific trade-off did you make?"
}
```

### AI 音频流

```json
{
  "type": "tts.audio.delta",
  "sessionId": "iv_123",
  "turnId": "turn_006",
  "codec": "mp3",
  "payload": "base64_audio_chunk"
}
```

### 实时轻纠正

由独立 Grammar Agent 异步检测严重语法错误后下发，不阻塞主对话链路。

```json
{
  "type": "correction.light",
  "sessionId": "iv_123",
  "turnId": "turn_006",
  "severity": "high",
  "originalText": "I have did a project.",
  "correctedText": "I have done a project.",
  "spokenTip": "Just a tip: we say 'I have done a project' instead of 'I have did a project'."
}
```

### 语气词/分析计数器

Grammar Agent 统计语气词（um/uh 等）后下发，前端显示计数器。

```json
{
  "type": "analysis.counter",
  "sessionId": "iv_123",
  "fillerCounts": {"um": 2, "uh": 1},
  "totalFillers": 3
}
```

### 运行时轻纠正开关（上行）

前端会话内开关，关闭后不再触发 `correction.light`。

```json
{
  "type": "control.correction",
  "sessionId": "iv_123",
  "enabled": false
}
```

### 课后分析接口

`GET /api/interviews/{sessionId}/analysis`

返回发音/语法分析汇总，供课后报告使用。

```json
{
  "sessionId": "iv_123",
  "pronunciation": [
    {
      "turnId": "turn_001",
      "wordsPerMinute": 120.5,
      "pauseCount": 2,
      "lowConfidenceWords": ["project"],
      "durationSeconds": 3.2,
      "wordCount": 8,
      "overallConfidence": 0.85
    }
  ],
  "corrections": [
    {
      "turnId": "turn_001",
      "original": "have did",
      "corrected": "have done",
      "severity": "serious",
      "transcript": "I have did a project"
    }
  ],
  "fillerCounts": {"um": 2, "uh": 1}
}
```

### VAR 事件增量

```json
{
  "type": "timeline.event",
  "sessionId": "iv_123",
  "event": {
    "eventId": "evt_010",
    "turnId": "turn_006",
    "eventType": "starIssue",
    "severity": "medium",
    "title": "STAR 结果缺失",
    "startMs": 31000,
    "endMs": 36500,
    "transcriptSnippet": "I led the backend design for an AI interview system."
  }
}
```

### 结束控制消息

```json
{
  "type": "control.finish",
  "sessionId": "iv_123",
  "reason": "userFinished",
  "reportStatus": "generating"
}
```

## 字段命名要求

- JSON 字段统一使用 camelCase。
- 接口路径使用小写复数名词。
- 前端变量、后端 DTO 字段和文档示例保持同名。
- 对外统一使用 `sessionId`，内部如果沿用 `interviewId`，必须在接口层转换。

## 联调验收标准

- 前端可仅根据本文件完成 Mock 数据开发。
- 后端实现必须保持响应字段与示例字段兼容。
- WebSocket 消息必须包含 `type` 和 `sessionId`。
- 任何失败响应都必须返回中文 `message`。
- 每次接口变更必须同步更新本文档。
- P0 阶段必须优先保证 interview 接口可用，restaurant 和 meeting 未启用时必须返回明确禁用状态。
