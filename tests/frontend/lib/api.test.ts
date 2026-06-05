/** API 客户端单元测试 – 请求构造、错误解析、契约字段 */

import { createJob, createSession, fetchScenes, uploadResume } from "@/lib/api";

const mockFetch = vi.fn();
global.fetch = mockFetch;

function jsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("fetchScenes", () => {
  it("应请求 /api/scenes 并返回场景数组", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ scenes: [{ scene: "interview", displayName: "求职面试" }] })
    );
    const scenes = await fetchScenes(true);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/scenes?full=true"),
      expect.objectContaining({ cache: "no-store" })
    );
    expect(scenes).toHaveLength(1);
    expect(scenes[0].scene).toBe("interview");
  });

  it("请求失败时应返回空数组", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}, 500));
    const scenes = await fetchScenes();
    expect(scenes).toEqual([]);
  });
});

describe("uploadResume", () => {
  it("应使用 FormData 上传文件并返回 resumeId", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        resumeId: "res_123",
        parseStatus: "success",
        parsedProfile: { skills: ["Python"], projects: [], riskSignals: [] },
      })
    );
    const file = new File(["resume content"], "resume.txt", { type: "text/plain" });
    const result = await uploadResume(file);
    expect(result.resumeId).toBe("res_123");
    expect(result.parseStatus).toBe("success");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/resumes"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("上传失败时应抛出中文错误消息", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(
        { errorCode: "FILE_EMPTY", message: "上传的文件为空", requestId: "req_abc" },
        400
      )
    );
    const file = new File([""], "empty.txt");
    await expect(uploadResume(file)).rejects.toThrow("上传的文件为空");
  });
});

describe("createJob", () => {
  it("应 POST JSON 并返回 jobId 和 parsedProfile", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        jobId: "job_123",
        parsedProfile: {
          requiredSkills: ["LLM"],
          competencies: ["problemSolving"],
          difficultyLevel: "senior",
        },
      })
    );
    const result = await createJob({
      title: "AI Engineer",
      company: "Demo",
      jdText: "Looking for LLM engineer with Python experience",
    });
    expect(result.jobId).toBe("job_123");
    expect(result.parsedProfile.difficultyLevel).toBe("senior");
  });
});

describe("createSession", () => {
  it("应返回 sessionId、sessionToken 和 websocketUrl", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        sessionId: "iv_123",
        sessionToken: "tok_iv_123",
        websocketUrl: "ws://localhost:8000/ws/interviews/iv_123",
        scene: "interview",
        topic: "behavioral",
        persona: { mode: "founder", displayName: "Founder Mode" },
        status: "created",
      })
    );
    const result = await createSession({
      scene: "interview",
      topic: "behavioral",
      roleMode: "founder",
      resumeId: "res_1",
      jobId: "job_1",
      durationMinutes: 15,
      difficultyLevel: "senior",
      realtimeLightCorrection: true,
    });
    expect(result.sessionId).toBe("iv_123");
    expect(result.websocketUrl).toContain("/ws/interviews/");
    expect(result.status).toBe("created");
  });
});
