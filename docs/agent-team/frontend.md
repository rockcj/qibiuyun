# AgentTeam 前端开发文档

## 文档目标

本文档面向前端 Agent，负责把 SpeakUp AI 的产品流程转化为可演示、可交互、可回放的 Web Demo。前端使用 Next.js 实现，三大场景（面试/点餐/会议）均已完整落地，各场景独立可用。

## 开发优先级

| 优先级 | 场景模块 | 前端目标 | 当前状态 |
|---|---|---|---|
| P0 | 面试场景 | 完成简历上传、JD 输入、Persona 选择、实时面试、轻纠正、报告和 VAR | ✅ 已实现 |
| P1 | 餐厅点餐 | 在不破坏面试闭环的前提下新增点餐主题、服务员角色和点餐报告 | ✅ 已实现 |
| P2 | 商务会议 | 在 P0/P1 稳定后新增会议主题、会议角色和会议报告 | ✅ 已实现 |

## 前端职责边界

前端只负责用户交互、状态展示和浏览器侧音频采集，不在浏览器中实现核心评分、Agent 推理或报告生成逻辑。

| 模块 | 前端职责 | 不负责内容 |
|---|---|---|
| 场景选择 | 展示三大场景入口，各场景可独立进入 | 后端场景规则计算 |
| 会话配置 | 收集子主题、角色、Persona、简历和 JD | 简历/JD 深度解析 |
| 实时对话 | 采集音频、展示字幕、播放 AI 音频 | ASR、LLM、TTS 核心处理 |
| 轻纠正提示 | 展示严重语法或发音提醒 | 错误严重程度判断 |
| VAR 时间轴 | 展示事件、跳转回放、证据详情 | Timeline Event 生成 |
| 场景报告 | 展示总分、分项分、证据和建议 | 报告评分与总结生成 |

## 页面结构

| 页面 | 路由建议 | 核心功能 |
|---|---|---|
| 首页 | `/` | 展示三大场景入口卡片，各场景独立可用 |
| 场景配置页 | `/scenes/[scene]` | 各场景 Persona、难度和纠错配置 |
| 面试资料页 | `/interview/setup` | 简历上传、JD 输入、解析结果预览 |
| 实时对话页 | `/sessions/[sessionId]` | 麦克风状态、字幕、AI 回复、轻纠正、结束按钮 |
| 报告页 | `/reports/[sessionId]` | 场景分数、维度评分、建议、VAR 时间轴 |
| Demo 兜底页 | `/demo` | P0 提供面试预置演示数据，无麦克风时可直接演示 |

## 核心用户流程

```text
用户进入首页
  ↓
选择 interview 面试场景
  ↓
选择 Persona、难度和纠错开关
  ↓
上传简历并输入 JD
  ↓
调用创建会话接口
  ↓
进入实时语音对话页
  ↓
通过 WebSocket 发送音频并接收字幕、文本和音频
  ↓
结束会话后跳转报告页
```

## 组件拆分建议

| 组件 | 说明 |
|---|---|
| `SceneCard` | 展示单个训练场景的名称、说明和入口按钮 |
| `SceneConfigForm` | 收集子主题、角色、难度和纠错开关 |
| `ResumeUploader` | 上传简历文件并展示解析状态 |
| `JobDescriptionEditor` | 输入 JD 文本并展示岗位解析摘要 |
| `VoiceSessionPanel` | 管理实时对话主区域、字幕和 AI 回复 |
| `MicrophoneControl` | 控制麦克风权限、录音状态和错误提示 |
| `LightCorrectionToast` | 展示一句话实时轻纠正 |
| `TimelineEventList` | 展示 VAR 事件列表并支持点击定位 |
| `ScorePanel` | 展示总分、分项分和等级 |
| `ReportEvidenceCard` | 展示扣分证据、高光证据和建议 |

## 前端状态模型

```typescript
// 前端会话状态用于控制页面显示和 WebSocket 生命周期
type sessionStatus = "created" | "connecting" | "running" | "finishing" | "completed" | "failed";

// 场景类型与后端接口保持一致，三大场景均已实现
type sceneType = "interview" | "restaurant" | "meeting";
```

前端状态应围绕 `sessionId` 管理。创建会话成功后，页面不再依赖本地表单状态，而是以服务端返回的 `sessionToken`、`websocketUrl` 和 `sceneContext` 作为实时链路依据。

## WebSocket 前端处理

前端需要处理以下消息：

| 消息类型 | 前端动作 |
|---|---|
| `asr.partial` | 更新实时字幕，不写入最终对话记录 |
| `asr.final` | 写入用户本轮最终发言 |
| `agent.text.delta` | 追加 AI 文本流 |
| `tts.audio.delta` | 解码并播放 AI 音频片段 |
| `timeline.event` | 增量追加 VAR 时间轴事件 |
| `correction.light` | 显示轻纠正提示 |
| `control.interrupt` | 展示 AI 打断状态 |
| `control.finish` | 跳转或提示报告生成中 |

## Demo 稳定性要求

- 麦克风无权限时，必须给出清晰提示，并允许切换到文本输入或预置 Demo。
- WebSocket 断开时，前端应自动重连一次，并展示恢复状态。
- TTS 音频播放失败时，仍要展示 AI 文本回复。
- 报告未生成完成时，报告页应显示加载状态并轮询接口。
- 所有错误提示使用中文，方便比赛现场快速定位问题。

## 前端验收标准

- 三大场景均可从首页进入并完成配置。
- 面试场景可以上传简历、输入 JD、选择 Persona 并创建会话。
- 实时对话页可以展示用户字幕、AI 角色文本回复和轻纠正提示。
- 报告页可以展示场景评分、分项评分、建议和 VAR 时间轴。
- 各场景入口独立，互不影响。
- 无麦克风或后端异常时，预置 Demo 仍能完成演示闭环。
