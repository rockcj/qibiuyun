# AgentTeam 接口契约文档

## 文档目标

本文档定义 OfferGPT 前后端协作所需的 REST API 与 WebSocket 消息契约。接口命名以 72 小时 MVP 可落地为优先，业务上支持面试、餐厅点餐和商务会议三类场景。

## 通用约定

| 项目 | 约定 |
|---|---|
| 数据格式 | REST 请求和响应默认使用 JSON |
| 时间格式 | 使用 ISO 8601 字符串或毫秒时间戳 |
| ID 命名 | 对外使用 `sessionId`，数据库可沿用 `interviewId` |
| 场景枚举 | `interview`、`restaurant`、`meeting` |
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
      "scene": "restaurant",
      "displayName": "餐厅点餐",
      "topics": [
        {
          "topic": "ordering",
          "displayName": "点餐"
        }
      ],
      "roleModes": [
        {
          "roleMode": "busyWaiter",
          "displayName": "忙碌的服务员"
        }
      ],
      "rubric": ["english", "politeness", "functionalPhrases", "taskCompletion"]
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

点餐场景请求：

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
  "scene": "restaurant",
  "topic": "ordering",
  "persona": {
    "mode": "busyWaiter",
    "displayName": "Busy Waiter"
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
  "scene": "restaurant",
  "topic": "ordering",
  "roleMode": "busyWaiter",
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
      "description": "用户使用了 have did，应改为 have made。",
      "startMs": 31020,
      "endMs": 34720,
      "transcriptSnippet": "I have did a reservation.",
      "suggestion": "I have made a reservation."
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
  "reportId": "rep_456",
  "sessionId": "iv_123",
  "scene": "restaurant",
  "scoreName": "Restaurant Practice Score",
  "sceneScore": 86,
  "dimensionScores": {
    "english": 82,
    "politeness": 90,
    "functionalPhrases": 88,
    "taskCompletion": 84,
    "pronunciationFluency": 80
  },
  "recommendedExpressions": [
    "Could I have the steak, please?",
    "I'm allergic to nuts. Could you make sure there are no nuts in this dish?"
  ],
  "finalRecommendation": "用户可以完成基础点餐流程，下一步建议练习投诉处理。"
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
  "finalTranscript": "I would like to order a steak, please."
}
```

### AI 文本流

```json
{
  "type": "agent.text.delta",
  "sessionId": "iv_123",
  "turnId": "turn_006",
  "delta": "Sure, how would you like your steak cooked?"
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

```json
{
  "type": "correction.light",
  "sessionId": "iv_123",
  "turnId": "turn_006",
  "severity": "high",
  "originalText": "I have did a reservation.",
  "correctedText": "I have made a reservation.",
  "spokenTip": "Just a quick tip: we say 'I have made a reservation'."
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
    "eventType": "highlight",
    "severity": "low",
    "title": "礼貌表达正确",
    "startMs": 31000,
    "endMs": 36500,
    "transcriptSnippet": "Could I have the steak, please?"
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
