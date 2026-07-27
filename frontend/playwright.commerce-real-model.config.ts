import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e-real-model",
  testMatch: "commerce-chat-persistent.spec.ts",
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: "line",
  timeout: 10 * 60_000,
  expect: {
    timeout: 30_000,
  },
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium-real-deepseek-v4",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
