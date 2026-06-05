/** API 类型契约一致性测试 – 确保类型定义覆盖 api-contract 关键字段 */

import type {
  ApiErrorBody,
  CreateSessionResponse,
  JobCreateResponse,
  ResumeUploadResponse,
  SceneFull,
} from "@/types/api";

describe("API 类型契约", () => {
  it("SceneFull 应包含场景配置必要字段", () => {
    const scene: SceneFull = {
      scene: "interview",
      displayName: "求职面试",
      description: "desc",
      topics: [{ topic: "behavioral", displayName: "行为面试" }],
      roleModes: [{ roleMode: "founder", displayName: "Founder Mode" }],
      rubric: ["english", "logic"],
      requiresResumeJD: true,
    };
    expect(scene.scene).toBe("interview");
    expect(scene.requiresResumeJD).toBe(true);
  });

  it("ResumeUploadResponse 应符合 api-contract 结构", () => {
    const resp: ResumeUploadResponse = {
      resumeId: "res_123",
      parseStatus: "success",
      parsedProfile: {
        skills: ["Python"],
        projects: [{ name: "AI System", role: "Dev", impact: "35% faster" }],
        riskSignals: ["Few quantified outcomes"],
      },
    };
    expect(resp.parsedProfile.skills).toContain("Python");
    expect(resp.parsedProfile.projects[0]).toHaveProperty("impact");
  });

  it("JobCreateResponse 应符合 api-contract 结构", () => {
    const resp: JobCreateResponse = {
      jobId: "job_123",
      parsedProfile: {
        requiredSkills: ["LLM"],
        competencies: ["systemDesign"],
        difficultyLevel: "middle",
      },
    };
    expect(resp.parsedProfile.difficultyLevel).toBeDefined();
  });

  it("CreateSessionResponse 应包含 WebSocket 连接信息", () => {
    const resp: CreateSessionResponse = {
      sessionId: "iv_123",
      sessionToken: "tok_iv_123",
      websocketUrl: "ws://localhost:8000/ws/interviews/iv_123",
      scene: "interview",
      topic: "behavioral",
      persona: { mode: "founder", displayName: "Founder Mode" },
      status: "created",
    };
    expect(resp.websocketUrl).toMatch(/ws:\/\/.*\/ws\/interviews\//);
  });

  it("ApiErrorBody 应包含 errorCode、message、requestId", () => {
    const err: ApiErrorBody = {
      errorCode: "RESUME_REQUIRED",
      message: "面试场景需要提供简历 resumeId",
      requestId: "req_123",
    };
    expect(err.errorCode).toBe("RESUME_REQUIRED");
    expect(err.message).toContain("简历");
  });
});
