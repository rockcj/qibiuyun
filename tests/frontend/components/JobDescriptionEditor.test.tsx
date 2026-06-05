/** JobDescriptionEditor 组件测试 – 表单校验、JD 解析预览 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import JobDescriptionEditor from "@/components/JobDescriptionEditor";

vi.mock("@/i18n/LocaleContext", () => ({
  useLocale: () => ({ t: (key: string) => key, locale: "zh" }),
}));

const mockCreateJob = vi.fn();
vi.mock("@/lib/api", () => ({
  createJob: (...args: unknown[]) => mockCreateJob(...args),
}));

describe("JobDescriptionEditor", () => {
  const onCreated = vi.fn();

  beforeEach(() => {
    onCreated.mockClear();
    mockCreateJob.mockReset();
  });

  it("应渲染 JD 输入表单", () => {
    render(<JobDescriptionEditor onCreated={onCreated} />);
    expect(screen.getByText("jd.title")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("AI Application Engineer")).toBeInTheDocument();
  });

  it("缺少岗位名称应显示错误", async () => {
    const user = userEvent.setup();
    render(<JobDescriptionEditor onCreated={onCreated} />);
    await user.click(screen.getByText("jd.parse"));
    expect(screen.getByText("jd.error.title")).toBeInTheDocument();
    expect(mockCreateJob).not.toHaveBeenCalled();
  });

  it("解析成功应展示技能并回调 onCreated", async () => {
    mockCreateJob.mockResolvedValue({
      jobId: "job_xyz",
      parsedProfile: {
        requiredSkills: ["LLM", "Python"],
        competencies: ["systemDesign"],
        difficultyLevel: "senior",
      },
    });

    const user = userEvent.setup();
    render(<JobDescriptionEditor onCreated={onCreated} />);
    await user.type(screen.getByPlaceholderText("AI Application Engineer"), "AI Engineer");
    await user.type(
      screen.getByPlaceholderText("jd.placeholder"),
      "Looking for senior LLM engineer with Python and system design skills"
    );
    await user.click(screen.getByText("jd.parse"));

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith("job_xyz", expect.any(Object));
      expect(screen.getByText("LLM")).toBeInTheDocument();
      expect(screen.getByText("senior")).toBeInTheDocument();
    });
  });
});
