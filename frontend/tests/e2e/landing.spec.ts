import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

test.describe("Landing page", () => {
  test("renders the header and hero section", async ({ page }) => {
    await page.goto("/");

    // Header brand name
    await expect(
      page.locator("header h1", { hasText: "OpenSKU" }),
    ).toBeVisible();

    // CTA button in hero
    await expect(
      page.getByRole("link", { name: /开始验证你的产品/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: /查看中英文 demo/i }),
    ).toBeVisible();

    await expect(
      page.locator('link[rel="icon"][href="/favicon.svg"]'),
    ).toHaveCount(1);

    const favicon = await page.request.get("/favicon.svg");
    expect(favicon.ok()).toBe(true);
    expect(await favicon.text()).toContain("OpenSKU logo");
  });

  test("Get Started link navigates to ecom-launch workspace", async ({
    page,
  }) => {
    mockLangGraphAPI(page);

    await page.goto("/");

    const getStarted = page.getByRole("link", { name: /开始验证你的产品/i });
    await getStarted.click();

    // Should redirect to the ecom-launch agent chat
    await page.waitForURL("**/workspace/agents/ecom-launch/chats/new");
    await expect(page).toHaveURL(
      /\/workspace\/agents\/ecom-launch\/chats\/new/,
    );
  });

  test("bilingual demo link opens the Chinese credential-free sample", async ({
    page,
  }) => {
    await page.goto("/");

    await page.getByRole("link", { name: /查看中英文 demo/i }).click();

    await expect(page).toHaveURL(/\/demo\?lang=zh$/);
    await expect(
      page.getByRole("heading", {
        name: /一份商品 brief，生成一套可决策的上新包/i,
      }),
    ).toBeVisible();
  });
});
