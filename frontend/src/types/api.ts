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
