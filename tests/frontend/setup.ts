import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";

/** 全局 fetch mock 重置 */
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
