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

/** 所有下行 WebSocket 消息联合类型 */
export type WsServerMessage =
  | WsAsrPartial
  | WsAsrFinal
  | WsAgentTextDelta
  | WsAgentTextDone
  | WsTtsAudioDelta
  | WsCorrectionLight
  | WsControlFinish
  | WsAsrUnavailable
  | WsError
  | WsPong;

/** 对话轮次记录 */
export interface TurnRecord {
  turnId: string;
  userText: string;
  aiText: string;
  correction?: { original: string; corrected: string };
}
