/** SceneConfigForm 组件测试 – 面试跳转、点餐直接创建 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SceneConfigForm from "@/components/SceneConfigForm";
import type { SceneFull } from "@/types/api";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/i18n/LocaleContext", () => ({
  useLocale: () => ({
    t: (key: string) => key,
    locale: "zh",
  }),
}));

vi.mock("@/lib/api", () => ({
  createSession: vi.fn().mockResolvedValue({
    sessionId: "sess_123",
    sessionToken: "tok_sess_123",
    websocketUrl: "ws://localhost:8000/ws/interviews/sess_123",
    scene: "restaurant",
    topic: "ordering",
    persona: { mode: "friendlyWaiter", displayName: "友好服务员" },
    status: "created",
  }),
}));

const interviewScene: SceneFull = {
  scene: "interview",
  displayName: "求职面试",
  description: "desc",
  topics: [
    { topic: "behavioral", displayName: "行为面试" },
    { topic: "technical", displayName: "技术面试" },
  ],
  roleModes: [
    { roleMode: "founder", displayName: "Founder Mode" },
    { roleMode: "engineeringLeader", displayName: "Engineering Leader" },
  ],
  rubric: ["english", "logic"],
  requiresResumeJD: true,
};

const restaurantScene: SceneFull = {
  scene: "restaurant",
  displayName: "餐厅点餐",
  description: "desc",
  topics: [{ topic: "ordering", displayName: "点餐" }],
  roleModes: [{ roleMode: "friendlyWaiter", displayName: "友好服务员" }],
  rubric: ["english"],
  requiresResumeJD: false,
};

describe("SceneConfigForm", () => {
  beforeEach(() => {
    mockPush.mockClear();
    sessionStorage.clear();
  });

  it("面试场景点击下一步应跳转到 /interview/setup", async () => {
    const user = userEvent.setup();
    render(<SceneConfigForm scene={interviewScene} />);
    await user.click(screen.getByText("config.nextSetup"));
    expect(mockPush).toHaveBeenCalledWith(
      expect.stringContaining("/interview/setup")
    );
    expect(mockPush).toHaveBeenCalledWith(
      expect.stringContaining("topic=behavioral")
    );
  });

  it("应能切换子主题", async () => {
    const user = userEvent.setup();
    render(<SceneConfigForm scene={interviewScene} />);
    await user.click(screen.getByText("技术面试"));
    await user.click(screen.getByText("config.nextSetup"));
    expect(mockPush).toHaveBeenCalledWith(
      expect.stringContaining("topic=technical")
    );
  });

  it("点餐场景应直接创建会话并跳转", async () => {
    const user = userEvent.setup();
    const { createSession } = await import("@/lib/api");
    render(<SceneConfigForm scene={restaurantScene} />);
    await user.click(screen.getByText("scene.startTraining"));
    expect(createSession).toHaveBeenCalledWith(
      expect.objectContaining({ scene: "restaurant", topic: "ordering" })
    );
    // 等待异步完成
    await vi.waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/sessions/sess_123");
    });
  });
});
