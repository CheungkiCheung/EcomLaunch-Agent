import { defineConfig, devices } from "@playwright/test";

/**
 * Layer 2 of the record/replay e2e: the REAL Next.js frontend rendering data
 * from a REAL gateway whose LLM is the deterministic `ReplayChatModel` (no API
 * key). This is separate from `playwright.config.ts` (which mocks the backend)
 * so the mock-based suite is untouched.
 *
 * Two webServers are started: the replay gateway (:8011 by default) and an
 * isolated frontend (:3102 by default, pointed at the gateway). Auth uses a
 * throwaway test account the spec registers at runtime — no secrets.
 */
const frontendPort = process.env.OPENSKU_REAL_BACKEND_FRONTEND_PORT ?? "3102";
const gatewayPort = process.env.OPENSKU_REAL_BACKEND_GATEWAY_PORT ?? "8011";
const frontendURL = `http://localhost:${frontendPort}`;
const gatewayURL = `http://127.0.0.1:${gatewayPort}`;
const reuseExistingServer =
  process.env.OPENSKU_REAL_BACKEND_REUSE_SERVER === "1";

export default defineConfig({
  testDir: "./tests/e2e-real-backend",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "html",
  timeout: 90_000,

  use: {
    baseURL: frontendURL,
    trace: "on-first-retry",
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  webServer: [
    {
      command: `uv run python scripts/run_replay_gateway.py --port ${gatewayPort} --cors ${frontendURL}`,
      cwd: "../backend",
      url: `${gatewayURL}/health`,
      reuseExistingServer,
      timeout: 180_000,
      stdout: "pipe",
      stderr: "pipe",
      // Mount the test-only run/message seeder used by multi-run-order.spec.ts
      // (#3352). The endpoint exists only on this replay gateway, never in the
      // production app.
      env: { DEERFLOW_ENABLE_TEST_SEED: "1" },
    },
    {
      command: `pnpm build && pnpm start --port ${frontendPort}`,
      url: frontendURL,
      reuseExistingServer,
      timeout: 240_000,
      env: {
        SKIP_ENV_VALIDATION: "1",
        DEER_FLOW_AUTH_DISABLED: "1",
        BETTER_AUTH_SECRET: "opensku-real-backend-local-secret-32-bytes",
        // Leave NEXT_PUBLIC_* unset so the frontend uses its built-in
        // next.config rewrites (same-origin proxy) instead of talking to the
        // gateway cross-origin — cross-origin fetches drop the auth cookies.
        // Just point that proxy at the replay gateway.
        DEER_FLOW_INTERNAL_GATEWAY_BASE_URL: gatewayURL,
      },
    },
  ],
});
