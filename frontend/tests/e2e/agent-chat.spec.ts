import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

const MOCK_AGENTS = [
  {
    name: "test-agent",
    description: "A test agent for E2E tests",
    system_prompt: "You are a test agent.",
  },
];

test.describe("Agent chat", () => {
  test("agent gallery page loads and shows agents", async ({ page }) => {
    mockLangGraphAPI(page, { agents: MOCK_AGENTS });

    await page.goto("/workspace/agents");

    // The agent card should appear with the agent name
    await expect(page.getByText("test-agent")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("agent chat page loads with input box", async ({ page }) => {
    mockLangGraphAPI(page, { agents: MOCK_AGENTS });

    await page.goto("/workspace/agents/test-agent/chats/new");

    // The prompt input textarea should be visible
    const textarea = page.getByPlaceholder(/how can i assist you/i);
    await expect(textarea).toBeVisible({ timeout: 15_000 });
  });

  test("agent chat page shows agent badge", async ({ page }) => {
    mockLangGraphAPI(page, { agents: MOCK_AGENTS });

    await page.goto("/workspace/agents/test-agent/chats/new");

    // The agent badge should display in the header (scoped to header to avoid
    // matching the welcome area which also shows the agent name)
    await expect(
      page.locator("header span", { hasText: "test-agent" }),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("Growth Analyst has a dedicated identity and quick actions", async ({
    page,
  }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/data-inspector/chats/new");

    await expect(
      page.locator("header span", { hasText: "Growth Analyst" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Data overview")).toBeVisible();
    await expect(page.getByText("Find anomalies")).toBeVisible();
    await expect(page.getByText("Improvement areas")).toBeVisible();
  });

  test("EcomLaunch keeps its crew available in the default Flash mode", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/ecom-launch/chats/new");

    await expect(page.getByRole("button", { name: "Flash" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByRole("heading", { name: "Launch Crew", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "默认 Flash 已保留计划和子智能体能力；四个专业角色会按需在这里显示真实分工状态。",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(page.getByText("开启 Ultra 后", { exact: false })).toHaveCount(
      0,
    );
    await expect(page.getByText("校准", { exact: true })).toHaveCount(0);
  });
});
