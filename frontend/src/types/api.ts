/** API 契约类型定义，与 api-contract.md 保持一致 */

export type SceneType = "interview" | "restaurant" | "meeting";

export interface SceneTopic {
  topic: string;
  displayName: string;
}

export interface SceneRoleMode {
  roleMode: string;
  displayName: string;
}

export interface SceneFull {
  scene: SceneType;
  displayName: string;
  description: string;
  icon?: string;
  color?: string;
  enabled?: boolean;
  releasePriority?: string;
  disabledReason?: string;
  topics: SceneTopic[];
  roleModes: SceneRoleMode[];
  rubric: string[];
  requiresResumeJD: boolean;
}

export interface ResumeProject {
  name: string;
  role: string;
  impact: string;
}

export interface ResumeParsedProfile {
  skills: string[];
  projects: ResumeProject[];
  riskSignals: string[];
}

export interface ResumeUploadResponse {
  resumeId: string;
  parseStatus: string;
  parsedProfile: ResumeParsedProfile;
}

export interface JobParsedProfile {
  requiredSkills: string[];
  competencies: string[];
  difficultyLevel: string;
}

export interface JobCreateResponse {
  jobId: string;
  parsedProfile: JobParsedProfile;
}

export interface SceneConfigState {
  topic: string;
  roleMode: string;
  difficultyLevel: string;
  durationMinutes: number;
  realtimeLightCorrection: boolean;
  personaMode: string;
}

export interface CreateSessionRequest {
  scene: SceneType;
  topic: string;
  roleMode: string;
  resumeId?: string;
  jobId?: string;
  personaMode?: string;
  durationMinutes: number;
  difficultyLevel: string;
  realtimeLightCorrection: boolean;
}

export interface SessionPersona {
  mode: string;
  displayName: string;
}

export interface CreateSessionResponse {
  sessionId: string;
  sessionToken: string;
  websocketUrl: string;
  scene: SceneType;
  topic: string;
  persona: SessionPersona | null;
  status: string;
}

export interface ApiErrorBody {
  errorCode: string;
  message: string;
  requestId: string;
}

// ============================================================================
// WebSocket 消息类型（与 api-contract.md 保持一致）
// ============================================================================

/** 音频上行 */
export interface WsAudioInput {
  type: "audio.input";
  sessionId: string;
  sequenceId: number;
  timestampMs: number;
  codec: "pcm16";
  sampleRate: 16000;
  payload: string; // base64
}

/** 文本上行（Demo 主路径） */
export interface WsTextInput {
  type: "text.input";
  sessionId: string;
  text: string;
}

/** ASR 实时字幕 */
export interface WsAsrPartial {
  type: "asr.partial";
  sessionId: string;
  turnId: string;
  startMs?: number;
  endMs?: number;
  partialTranscript: string;
}

/** ASR 最终文本 */
export interface WsAsrFinal {
  type: "asr.final";
  sessionId: string;
  turnId: string;
  finalTranscript: string;
  /** 置信度 0-1（Whisper no_speech_prob + avg_logprob 综合），文本输入固定为 1.0 */
  confidence: number;
}

/** AI 文本流 */
export interface WsAgentTextDelta {
  type: "agent.text.delta";
  sessionId: string;
  turnId: string;
  delta: string;
}

/** AI 文本完成 */
export interface WsAgentTextDone {
  type: "agent.text.done";
  sessionId: string;
  turnId: string;
}

/** TTS 音频流 */
export interface WsTtsAudioDelta {
  type: "tts.audio.delta";
  sessionId: string;
  turnId: string;
  codec: "mp3";
  payload: string; // base64
  text?: string;
}

/** 服务端 TTS 不可用，前端应使用浏览器 speechSynthesis 降级朗读 */
export interface WsTtsUnavailable {
  type: "tts.unavailable";
  sessionId: string;
  turnId: string;
  text: string;
}

/** 实时轻纠正 */
export interface WsCorrectionLight {
  type: "correction.light";
  sessionId: string;
  turnId: string;
  severity: "low" | "medium" | "high";
  originalText: string;
  correctedText: string;
  spokenTip: string;
}

/** 语气词/分析计数器 */
export interface WsAnalysisCounter {
  type: "analysis.counter";
  sessionId: string;
  fillerCounts: Record<string, number>;
  totalFillers: number;
}

/** 实时纠正开关状态（下行同步） */
export interface WsCorrectionState {
  type: "correction.state";
  sessionId: string;
  enabled: boolean;
}

/** 运行时轻纠正开关（上行） */
export interface WsControlCorrection {
  type: "control.correction";
  sessionId: string;
  enabled: boolean;
}

/** 结束控制 */
export interface WsControlFinish {
  type: "control.finish";
  sessionId: string;
  reason: string;
  reportStatus: string;
}

/** ASR 不可用提示 */
export interface WsAsrUnavailable {
  type: "asr.unavailable";
  sessionId: string;
  message: string;
}

/** 错误 */
export interface WsError {
  type: "error";
  sessionId: string;
  message: string;
}

/** Pong */
export interface WsPong {
  type: "pong";
  sessionId: string;
}

/** ASR 无结果 */
export interface WsAsrNoResult {
  type: "asr.no_result";
  sessionId: string;
  message: string;
  /** 过滤原因，便于前端展示对应提示 */
  reason?: string;
}

/** 所有下行 WebSocket 消息联合类型 */
export type WsServerMessage =
  | WsAsrPartial
  | WsAsrNoResult
  | WsAsrFinal
  | WsAgentTextDelta
  | WsAgentTextDone
  | WsTtsAudioDelta
  | WsTtsUnavailable
  | WsCorrectionLight
  | WsCorrectionState
  | WsAnalysisCounter
  | WsControlFinish
  | WsAsrUnavailable
  | WsError
  | WsPong;

/** 对话轮次记录 */
export interface TurnRecord {
  id: string;  // 稳定唯一 key，避免 React re-render 抖动
  turnId: string;
  userText: string;
  aiText: string;
  correction?: { original: string; corrected: string };
}

/** 单轮发音分析记录 */
export interface PronunciationRecord {
  turnId: string;
  wordsPerMinute: number;
  pauseCount: number;
  lowConfidenceWords: string[];
  durationSeconds?: number;
  wordCount?: number;
  overallConfidence?: number;
}

/** 语法纠正记录（含轻微错误） */
export interface CorrectionRecord {
  turnId: string;
  original: string;
  corrected: string;
  severity: "none" | "minor" | "serious";
  transcript?: string;
}

/** 课后分析汇总（GET /api/interviews/{id}/analysis） */
export interface SessionAnalysisResponse {
  sessionId: string;
  pronunciation: PronunciationRecord[];
  corrections: CorrectionRecord[];
  fillerCounts: Record<string, number>;
}

/** 场景报告（GET /api/interviews/{id}/report） */
export interface SessionReportResponse {
  reportId: string | null;
  sessionId: string;
  scene: string;
  scoreName: string;
  sceneScore: number;
  dimensionScores: Record<string, number>;
  finalRecommendation: string;
  finalRecommendationEn?: string;
  highlights?: string[];
  highlightsEn?: string[];
  improvements?: string[];
  improvementsEn?: string[];
  evidenceList?: EvidenceEntry[];
  reportStatus?: "generating" | "ready" | "error";
}

/** 评分证据条目 */
export interface EvidenceEntry {
  dimension: string;
  score: number;
  evidence: string;
}

/** VAR 时间轴事件 */
export interface TimelineEventItem {
  eventId: string;
  turnId: string;
  eventType: string;
  severity: "low" | "medium" | "high";
  title: string;
  description: string;
  startMs: number;
  endMs: number;
  transcriptSnippet?: string;
  evidence?: Record<string, unknown>;
  suggestion?: string;
  displayPriority?: number;
  aiResponse?: string | null;  // AI 针对该轮次的回复文本
}

/** 时间轴事件列表响应 */
export interface SessionEventsResponse {
  sessionId: string;
  events: TimelineEventItem[];
}

/** 会话详情（GET /api/interviews/{id}） */
export interface SessionDetail {
  sessionId: string;
  scene: string;
  topic?: string;
  roleMode?: string;
  status: string;
  startedAt?: string;
  durationSeconds?: number;
  audioUrl?: string | null;  // 录音文件地址
}
