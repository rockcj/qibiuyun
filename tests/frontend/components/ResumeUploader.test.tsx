/** ResumeUploader 组件测试 – 文件校验、上传、解析预览 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ResumeUploader from "@/components/ResumeUploader";

vi.mock("@/i18n/LocaleContext", () => ({
  useLocale: () => ({ t: (key: string) => key, locale: "zh" }),
}));

const mockUploadResume = vi.fn();
vi.mock("@/lib/api", () => ({
  uploadResume: (...args: unknown[]) => mockUploadResume(...args),
}));

describe("ResumeUploader", () => {
  const onUploaded = vi.fn();

  beforeEach(() => {
    onUploaded.mockClear();
    mockUploadResume.mockReset();
  });

  it("应渲染上传区域", () => {
    render(<ResumeUploader onUploaded={onUploaded} />);
    expect(screen.getByText("resume.title")).toBeInTheDocument();
    expect(screen.getByText("resume.dropzone")).toBeInTheDocument();
  });

  it("上传成功应展示技能标签并回调 onUploaded", async () => {
    mockUploadResume.mockResolvedValue({
      resumeId: "res_abc",
      parseStatus: "success",
      parsedProfile: {
        skills: ["Python", "FastAPI"],
        projects: [{ name: "AI System", role: "Dev", impact: "35%" }],
        riskSignals: [],
      },
    });

    const user = userEvent.setup();
    render(<ResumeUploader onUploaded={onUploaded} />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["resume text"], "resume.txt", { type: "text/plain" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(onUploaded).toHaveBeenCalledWith("res_abc", expect.any(Object));
      expect(screen.getByText("Python")).toBeInTheDocument();
    });
  });

  it("不支持的文件类型应显示错误", async () => {
    const user = userEvent.setup();
    render(<ResumeUploader onUploaded={onUploaded} />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["data"], "resume.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getByText("resume.error.type")).toBeInTheDocument();
    expect(mockUploadResume).not.toHaveBeenCalled();
  });
});
