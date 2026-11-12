# 语音引擎对接说明（本地管线 / 豆包端到端实时语音）

本文档说明 OfferGPT 现在支持的两种语音引擎、云端引擎的接入方式与排错方法。

## 一、两种引擎

| 引擎 | 链路 | 音色 | 适用场景 |
| --- | --- | --- | --- |
| `local`（默认） | 浏览器麦克风 → 本地 Whisper ASR → DeepSeek LLM → EdgeTTS（或浏览器 `speechSynthesis`） | EdgeTTS / 浏览器内置 | 离线演示、无云账号、需要本地发音分析 |
| `volcengine` | 浏览器麦克风 → 后端中继 → 火山引擎豆包端到端实时语音（Seeduplex 全双工）S2S 模型 | 豆包音色（24kHz PCM） | 追求更自然、更低延迟的对话体验 |

前端在语音模式下多了一个「语音引擎」选择（本地语音 / 豆包实时语音），选择结果保存在
`localStorage`（key：`offergpt:voiceEngine`），下次进入会话自动恢复。云端未配置时该选项
置灰并显示原因。

## 二、SDK 调研结论：对接原始接口

需求要求「有 SDK 就用 SDK，没有才对接原始接口」。调研结果：

- 火山引擎官方为「端到端实时语音大模型」提供的是 **终端侧 Speech SDK**（Android / iOS /
  Web / Windows 以及官方示例工程），**没有面向 Python 服务端的 SDK**；
- 官方 Python SDK（`volcengine-python-sdk`）覆盖的是云服务器 / TOS 等 OpenAPI，不含语音
  对话协议；
- 社区包（如 LiveKit 的 `livekit-plugins-volcengine`、Rust `seeduplex-client`）要么绑定
  LiveKit RTC 全家桶，要么语言不匹配，直接引入会显著增加依赖体积与运行时不匹配风险。

因此本项目 **没有引入第三方 SDK**，而是在后端按官方协议直连 WebSocket（`services/volcengine/duplex_client.py`）。
这样做的附带好处：API Key 只存在于服务端，不会泄露到浏览器。

参考文档：
- [端到端实时语音（Seeduplex，全双工）](https://docs.volcengine.com/docs/doubao-voice/end-to-end-real-time-voice-full-duplex-version?lang=zh)
- [端到端实时语音 · 接入必读](https://docs.volcengine.com/docs/doubao-voice/access-must-read?lang=zh)

## 三、协议要点（本仓库实现的部分）

- 传输：`wss://openspeech.bytedance.com/api/v3/duplex/realtime/dialogue`，**纯 JSON 文本帧**，
  一帧一事件，事件类型由顶层 `type` 决定；
- 鉴权请求头：`X-Api-Key`（必填）、`X-Api-App-Id`（可选）、`X-Api-Resource-Id`（可选）、
  `X-Api-Connect-Id`（客户端生成的 UUID）；
- 上行：`session.create` → `input_audio_buffer.append`（base64 PCM）→（麦克风关闭时）
  `input_audio_mute.commit` / `input_audio_unmute.commit` → `speech_text_buffer.commit`（直接朗读文本）
  → `response.cancel`（打断）→ `session.close`；
- 下行：`session.created`、`conversation.item.input_audio_transcription.{delta,completed}`、
  `response.output_text.{delta,done}`、`response.output_audio.{started,delta,done}`、
  `response.done`、`error`；
- 音频：上行 16kHz / 单声道 / int16 小端（建议 20ms 一包），下行默认 24kHz `pcm_s16le`，
  均以 base64 内嵌 JSON；
- 模型：全双工版本固定 `session.model = 1.2.6.1`。

## 四、配置

在 `backend/.env` 或根目录 `.env.local` 中配置（后者优先）：

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `VOLCENGINE_SPEECH_API_KEY` | 是 | 豆包语音新版控制台创建的 API Key（请求头 `X-Api-Key`）。**与 TOS 的 `VOLCENGINE_ACCESS_KEY_ID/SECRET_ACCESS_KEY` 不是同一套凭证** |
| `VOLCENGINE_SPEECH_APP_ID` | 否 | 部分账号需要，作为 `X-Api-App-Id` 下发 |
| `VOLCENGINE_SPEECH_WS_URL` | 否 | 默认 `wss://openspeech.bytedance.com/api/v3/duplex/realtime/dialogue` |
| `VOLCENGINE_SPEECH_RESOURCE_ID` | 否 | 作为 `X-Api-Resource-Id` 下发，一般留空 |
| `VOLCENGINE_SPEECH_MODEL` | 否 | 默认 `1.2.6.1` |
| `VOLCENGINE_SPEECH_VOICE` | 否 | 音色名，默认 `zh_female_vv_jupiter_bigtts`；**英语练习请换成控制台「音色列表」中的英文音色** |
| `VOLCENGINE_SPEECH_SPEED` | 否 | 语速 `[-50, 100]`，默认 0 |
| `VOLCENGINE_SPEECH_ENABLED` | 否 | 默认 `true`；设为 `false` 可直接隐藏/禁用云端选项 |
| `VOLCENGINE_SPEECH_SESSION_JSON` | 否 | 覆盖 `session.create` 的 `session` 对象（整段 JSON，深合并），用于透传 `extension` 等高级参数 |
| `VOICE_ENGINE_DEFAULT` | 否 | 新会话默认引擎：`local`（默认）/ `volcengine` |

配置完成后访问 `GET /api/voices` 可确认云端引擎是否 `available`：

```bash
curl http://localhost:8000/api/voices
```

## 五、联调自检

```bash
# 1) 离线自检（不消耗额度，校验报文与事件桥接）
python backend/scripts/check_volcengine_duplex.py

# 2) 真实连通（发送 1 秒静音 + 监听 8 秒下行事件）
python backend/scripts/check_volcengine_duplex.py --live

# 3) 顺便验证音色是否有效
python backend/scripts/check_volcengine_duplex.py --live --say "Hello, welcome to the interview."
```

## 六、前后端消息协议新增

上行（浏览器 → 后端）：

| 消息 | 说明 |
| --- | --- |
| `control.voice_engine { voiceEngine: "local" \| "volcengine" }` | 切换语音引擎 |
| `control.listening { listening: boolean }` | 麦克风开关同步；云端据此发送 `input_audio_mute/unmute.commit` |

下行（后端 → 浏览器）：

| 消息 | 说明 |
| --- | --- |
| `voice.engine.state { voiceEngine, available, reason?, defaultEngine? }` | 引擎状态同步 / 切换结果 / 失败回落原因 |
| `tts.audio.delta { codec: "pcm16", sampleRate: 24000, payload }` | 云端音频（原来只有 `codec: "mp3"`） |

前端按 `codec` 分流：`pcm16` 走 WebAudio 直通播放（`hooks/usePcmPlayer.ts`），`mp3` 仍走
`<audio>` 队列。

## 七、实现要点

- **不经过本地 VAD**：云端引擎下 `audio.input` 直接中继给火山引擎，前端同时关闭麦克风
  RMS 静音门限（`useMicrophone({ silenceGate: false })`），保证音频流连续；
- **轮次对齐**：云端同时下发「用户转写」「AI 文本」「AI 音频」，`services/volcengine/bridge.py`
  以 `transcription.completed` 作为一轮的起点；若模型先开口，文本/音频先进入本轮缓冲，
  等 `asr.final` 发出后再补发，避免前端丢弃早到消息；
- **播放期间的上行**：AI 播报时前端会静音麦克风，云端引擎下会同时下发
  `control.listening=false`，后端转发 `input_audio_mute.commit`，避免服务端因收不到音频触发
  空闲超时（错误码 `52000042 DialogAudioIdleTimeoutError`）；
- **失败回落**：连接/鉴权失败会下发 `voice.engine.state`（`voiceEngine: local` + `reason`）
  并整体切回本地管线，会话不中断。

## 八、已知限制

1. **文本输入仍走本地管线**：全双工协议没有「发送用户文本」的事件（`speech_text_buffer`
   只用于让模型直接朗读），因此云端引擎下用文本输入时会由本地 LLM + EdgeTTS/浏览器朗读回复，
   音色与语音轮次不同；
2. **发音分析不产出**：发音分析依赖本地 Whisper 的音频缓冲，云端轮次只做语法/语气词分析，
   课后报告的「发音分析」仅统计本地轮次；
3. **音色列表**：默认音色是中文音色名，英语练习需在控制台中挑选英文音色并填入
   `VOLCENGINE_SPEECH_VOICE`；
4. **并发与计费**：每个会话一条云端 WebSocket，切换引擎/结束会话都会主动 `session.close`，
   异常断开会依赖服务端超时回收。

## 九、排错

| 现象 | 排查方向 |
| --- | --- |
| `GET /api/voices` 中云端 `available=false` | 检查 `VOLCENGINE_SPEECH_API_KEY` 是否为空、`VOLCENGINE_SPEECH_ENABLED` 是否为 `false` |
| 连接被拒 / 401 | API Key 是否为**新版控制台**的 Key（不是 TOS AK/SK）；账号是否已开通该模型；`X-Api-Resource-Id` 是否需要 |
| `session.create 被拒绝` | 音色名无效（换控制台音色列表中的值）、模型名不是 `1.2.6.1`、账号未开通全双工模型 |
| 模型一段时间不回应 | 客户端停止上行音频但未发送 `input_audio_mute.commit`（本仓库已处理，见 `duplex_client.set_muted`） |
| 前端听不到云端声音 | 浏览器控制台查看 `[PCM]` 日志；确认 `tts.audio.delta.codec === "pcm16"`；`AudioContext` 需在用户交互后才允许播放 |
