import { defineConfig, devices } from "@playwright/test";

const frontendPort = process.env.OPENSKU_REPLAY_FRONTEND_PORT ?? "3112";
const gatewayPort = process.env.OPENSKU_REPLAY_GATEWAY_PORT ?? "8112";
const frontendURL = `http://localhost:${frontendPort}`;
const gatewayURL = `http://127.0.0.1:${gatewayPort}`;
const reuseExistingServer = process.env.OPENSKU_REPLAY_REUSE_SERVER === "1";

/**
 * Product-level replay E2E. Both servers are real; only the LLM provider is a
 * committed hash-keyed replay fixture, so no external API key is needed.
 */
export default defineConfig({
  testDir: "./tests/e2e-opensku-replay",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "html",
  timeout: 120_000,

  use: {
    baseURL: frontendURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  webServer: [
    {
      command: `uv run python scripts/run_replay_gateway.py --profile opensku --fixture tests/fixtures/replay/opensku_product_flows.json --port ${gatewayPort} --cors ${frontendURL}`,
      cwd: "../backend",
      url: `${gatewayURL}/health`,
      reuseExistingServer,
      timeout: 180_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        AUTH_JWT_SECRET: "opensku-browser-replay-secret-32-bytes",
      },
    },
    {
      command: `pnpm build && pnpm start --port ${frontendPort}`,
      url: frontendURL,
      reuseExistingServer,
      timeout: 240_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        SKIP_ENV_VALIDATION: "1",
        DEER_FLOW_AUTH_DISABLED: "1",
        BETTER_AUTH_SECRET: "opensku-browser-replay-local-secret",
        DEER_FLOW_INTERNAL_GATEWAY_BASE_URL: gatewayURL,
      },
    },
  ],
});
