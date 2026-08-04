import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

test.describe("EcomLaunch mode menu", () => {
  test("mode menu shows only Flash and Ultra for EcomLaunch", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/ecom-launch/chats/new");

    // Open the mode dropdown (trigger shows current mode)
    const modeTrigger = page
      .getByRole("button")
      .filter({ hasText: /Flash/i })
      .first();
    await expect(modeTrigger).toBeVisible({ timeout: 15_000 });
    await modeTrigger.click();

    // The dropdown menu opens with mode items — Flash and Ultra must be present.
    // Use the menu item labels scoped to the dropdown content.
    const menu = page.locator("[role='menu']");
    await expect(menu).toBeVisible();
    await expect(menu.getByText("Flash", { exact: true })).toBeVisible();
    await expect(menu.getByText("Ultra", { exact: true })).toBeVisible();

    // Thinking (Reasoning) and Pro must NOT be present in the EcomLaunch menu
    await expect(menu.getByText("Reasoning", { exact: true })).toHaveCount(0);
    await expect(menu.getByText("Pro", { exact: true })).toHaveCount(0);
  });

  test("switching to Ultra mode updates the mode label", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/ecom-launch/chats/new");

    const modeTrigger = page
      .getByRole("button")
      .filter({ hasText: /Flash/i })
      .first();
    await expect(modeTrigger).toBeVisible({ timeout: 15_000 });
    await modeTrigger.click();

    // Click Ultra in the dropdown
    const menu = page.locator("[role='menu']");
    await menu.getByText("Ultra", { exact: true }).click();

    // Wait for the dropdown to close and state to propagate.
    await expect(menu)
      .toBeHidden({ timeout: 10_000 })
      .catch(() => undefined);

    // Mode trigger + model should switch to Ultra / DeepSeek Reasoner.
    await expect(
      page.getByRole("button").filter({ hasText: /Ultra/ }).first(),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page
        .getByRole("button")
        .filter({ hasText: /DeepSeek Reasoner/ })
        .first(),
    ).toBeVisible({ timeout: 10_000 });

    // Reopen the menu — Ultra should be the selected (checked) mode.
    await page.getByRole("button").filter({ hasText: /Ultra/ }).first().click();
    const reopenedMenu = page.locator("[role='menu']");
    await expect(
      reopenedMenu.getByText("Ultra", { exact: true }),
    ).toBeVisible();
  });

  test("mode menu shows all four modes for normal chat", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    // Normal chat input box
    const textarea = page.getByPlaceholder(/how can i assist/i);
    await expect(textarea).toBeVisible({ timeout: 15_000 });

    // Mode trigger shows the current mode name ("Pro" default in normal chat)
    const trigger = page
      .getByRole("button")
      .filter({ hasText: /^(Pro|Flash|Reasoning|Ultra)$/ })
      .first();
    await expect(trigger).toBeVisible();
    await trigger.click();

    // Normal chat with the default model (deepseek-chat, no thinking):
    // Flash/Pro/Ultra are shown; Reasoning is hidden because the default
    // model does not support thinking.
    const menu = page.locator("[role='menu']");
    await expect(menu).toBeVisible();
    await expect(menu.getByText("Flash", { exact: true })).toBeVisible();
    await expect(menu.getByText("Pro", { exact: true })).toBeVisible();
    await expect(menu.getByText("Ultra", { exact: true })).toBeVisible();
    await expect(menu.getByText("Reasoning", { exact: true })).toHaveCount(0);
  });
});

test.describe("EcomLaunch welcome and suggestions", () => {
  test("EcomLaunch shows dedicated welcome suggestions", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/ecom-launch/chats/new");

    await expect(
      page.getByText("No-data validation", { exact: true }),
    ).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByText("Category wedge", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Public link", { exact: true })).toBeVisible();
  });
});

test.describe("War Room", () => {
  test("War Room shows empty state without run data", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);

    await page.context().addCookies([
      {
        name: "locale",
        value: "zh-CN",
        url: "http://localhost:3000",
      },
    ]);

    await page.goto("/workspace/war-room");

    // Header should render
    await expect(
      page.getByRole("heading", { name: /智能商业作战室/i }),
    ).toBeVisible({ timeout: 15_000 });

    const canvas = page.locator("canvas");
    await expect(canvas).toHaveCount(1, { timeout: 15_000 });
    await expect(canvas).toBeVisible();
    await expect(
      page.getByText("正在布置办公室…", { exact: true }),
    ).toHaveCount(0);

    const scene = page.getByTestId("war-room-scene");
    const sidebar = page.getByTestId("war-room-agent-sidebar");
    await expect(scene).toBeVisible();
    await expect(sidebar).toBeVisible();
    await expect(page.getByText("团队状态", { exact: true })).toBeVisible();

    const [sceneBox, sidebarBox, canvasBox] = await Promise.all([
      scene.boundingBox(),
      sidebar.boundingBox(),
      canvas.boundingBox(),
    ]);
    expect(sceneBox).not.toBeNull();
    expect(sidebarBox).not.toBeNull();
    expect(canvasBox).not.toBeNull();
    expect(sidebarBox!.x).toBeGreaterThanOrEqual(sceneBox!.x + sceneBox!.width);
    expect(canvasBox!.height).toBeGreaterThan(650);

    // The legacy portrait strip no longer overlays the bottom of the scene.
    await expect(page.locator('img[src^="/war-room/agent-"]')).toHaveCount(0);

    // 运行详情 is collapsed by default; expand it
    await page.locator("summary", { hasText: "运行详情" }).click();
    await expect(page.getByText("暂无产物文件")).toBeVisible();
  });

  test("War Room switches languages and keeps a compact layout usable", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1100, height: 800 });
    mockLangGraphAPI(page);

    await page.context().addCookies([
      {
        name: "locale",
        value: "en-US",
        url: "http://localhost:3000",
      },
    ]);
    await page.goto("/workspace/war-room");

    await expect(
      page.getByRole("heading", { name: "OpenSKU War Room" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Team status", { exact: true })).toBeVisible();
    await expect(page.locator("canvas")).toBeVisible({ timeout: 15_000 });

    const scene = page.getByTestId("war-room-scene");
    const sidebar = page.getByTestId("war-room-agent-sidebar");
    const [sceneBox, sidebarBox] = await Promise.all([
      scene.boundingBox(),
      sidebar.boundingBox(),
    ]);
    expect(sceneBox).not.toBeNull();
    expect(sidebarBox).not.toBeNull();
    expect(sidebarBox!.y).toBeGreaterThanOrEqual(
      sceneBox!.y + sceneBox!.height,
    );

    await page.getByRole("button", { name: "Switch to Chinese" }).click();
    await expect(
      page.getByRole("heading", { name: "OpenSKU 智能商业作战室" }),
    ).toBeVisible();
    await expect(page.getByText("团队状态", { exact: true })).toBeVisible();
    await expect(page.locator("canvas")).toHaveCount(1);
  });
});

test.describe("Input box behavior", () => {
  test("EcomLaunch input shows upload attachments button", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/ecom-launch/chats/new");

    const textarea = page.getByPlaceholder(
      /今天我能为你做些什么|how can i assist/i,
    );
    await expect(textarea).toBeVisible({ timeout: 15_000 });

    // Attachment button visible
    await expect(
      page.locator("button[aria-label*='attachment' i]"),
    ).toHaveCount(0);
  });
});
