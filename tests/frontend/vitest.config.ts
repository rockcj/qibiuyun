import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/** 前端 Vitest 配置，源码指向 frontend/src */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    environmentOptions: {
      jsdom: {
        url: "http://localhost:3000",
      },
    },
    globals: true,
    setupFiles: ["./setup.ts"],
    include: ["**/*.test.ts", "**/*.test.tsx"],
    pool: "threads",
    poolOptions: {
      threads: {
        singleThread: true,
      },
    },
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      include: ["../../frontend/src/**/*.{ts,tsx}"],
      exclude: ["**/*.d.ts", "**/layout.tsx", "**/page.tsx"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "../../frontend/src"),
      "next/navigation": path.resolve(__dirname, "./mocks/nextNavigation.ts"),
    },
  },
});
