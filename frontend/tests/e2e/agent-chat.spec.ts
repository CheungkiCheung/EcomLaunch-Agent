import { expect, test } from "@playwright/test";

import { MOCK_THREAD_ID, mockLangGraphAPI } from "./utils/mock-api";

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
    const textarea = page.getByPlaceholder(
      /今天我能为你做些什么|how can i assist you/i,
    );
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

  test("ecom launch keeps chat on the left and shows cockpit on the right", async ({
    page,
  }) => {
    mockLangGraphAPI(page, { agents: MOCK_AGENTS });

    await page.goto("/workspace/agents/ecom-launch/chats/new");

    const textarea = page.getByPlaceholder(
      /今天我能为你做些什么|how can i assist you/i,
    );
    const cockpit = page.getByLabel("EcomLaunch live agent cockpit");

    await expect(textarea).toBeVisible({ timeout: 15_000 });
    await expect(cockpit).toBeVisible({ timeout: 15_000 });

    const textareaBox = await textarea.boundingBox();
    const cockpitBox = await cockpit.boundingBox();

    expect(textareaBox).not.toBeNull();
    expect(cockpitBox).not.toBeNull();
    expect(cockpitBox!.x).toBeGreaterThan(textareaBox!.x);
  });

  test("商铺运营使用中文欢迎页、自然数据入口和 Ultra 默认模式", async ({
    page,
  }) => {
    mockLangGraphAPI(page, { agents: MOCK_AGENTS });

    await page.goto("/workspace/agents/store-operator/chats/new");

    await expect(
      page.locator("form").getByText("商铺运营 Agent", { exact: true }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByText(/上传订单、商品、营销、退款、库存或履约数据/),
    ).toBeVisible();
    await expect(page.getByText("检查数据", { exact: true })).toBeVisible();
    await expect(page.getByText("Ultra", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "添加附件" })).toBeVisible();
    await expect(
      page.getByTestId("chat").getByRole("link", { name: "作战室" }),
    ).toHaveAttribute("href", /\/workspace\/agents\/store-operator\/war-room/);
  });

  test("ecom launch chat links the current thread to War Room", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      agents: MOCK_AGENTS,
      threads: [
        {
          thread_id: MOCK_THREAD_ID,
          title: "Live EcomLaunch thread",
          agent_name: "ecom-launch",
        },
      ],
    });

    await page.goto(`/workspace/agents/ecom-launch/chats/${MOCK_THREAD_ID}`);

    const warRoomLink = page
      .getByTestId("chat")
      .getByRole("link", { name: /war room/i });
    await expect(warRoomLink).toBeVisible({ timeout: 15_000 });
    await expect(warRoomLink).toHaveAttribute(
      "href",
      `/workspace/agents/ecom-launch/war-room?threadId=${MOCK_THREAD_ID}`,
    );
  });
});
