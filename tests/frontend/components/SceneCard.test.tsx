/** SceneCard 组件测试 – 渲染、点击导航、占位标签 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SceneCard, { type SceneCardData } from "@/components/SceneCard";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock("@/i18n/LocaleContext", () => ({
  useLocale: () => ({ t: (key: string) => key, locale: "zh" }),
}));

const interviewScene: SceneCardData = {
  scene: "interview",
  displayName: "求职面试",
  description: "模拟真实英文面试",
  icon: "briefcase",
  color: "#4F46E5",
  enabled: true,
};

const restaurantScene: SceneCardData = {
  scene: "restaurant",
  displayName: "餐厅点餐",
  description: "练习点餐英语",
  icon: "utensils",
  color: "#F59E0B",
  enabled: false,
  releasePriority: "P1",
  disabledReason: "P0 阶段先完成面试闭环",
};

describe("SceneCard", () => {
  beforeEach(() => {
    mockPush.mockClear();
  });

  it("应渲染场景名称和描述", () => {
    render(<SceneCard scene={interviewScene} index={0} />);
    expect(screen.getByText("求职面试")).toBeInTheDocument();
    expect(screen.getByText("模拟真实英文面试")).toBeInTheDocument();
  });

  it("点击应导航到场景配置页", async () => {
    const user = userEvent.setup();
    render(<SceneCard scene={interviewScene} index={0} />);
    await user.click(screen.getByRole("button"));
    expect(mockPush).toHaveBeenCalledWith("/scenes/interview");
  });

  it("未启用场景应显示 P1/P2 占位标签", () => {
    render(<SceneCard scene={restaurantScene} index={1} />);
    expect(screen.getByText(/P1/)).toBeInTheDocument();
  });
});
