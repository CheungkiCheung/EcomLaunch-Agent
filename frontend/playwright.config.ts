import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "html",
  timeout: 30_000,

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    command: "pnpm exec next build --webpack && pnpm start",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      SKIP_ENV_VALIDATION: "1",
      DEER_FLOW_AUTH_DISABLED: "1",
      NEXT_PUBLIC_COMMERCE_CASE_AGENT_ENABLED: "true",
      NEXT_PUBLIC_COMMERCE_WORKSPACE_ID: "wsp_0123456789abcdef0123456789abcdef",
      NEXT_PUBLIC_COMMERCE_ACTOR_ID: "commerce-operator",
    },
  },
});
