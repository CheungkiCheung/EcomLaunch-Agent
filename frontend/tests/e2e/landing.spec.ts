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
    await expect(page).toHaveURL(/\/workspace\/agents\/ecom-launch\/chats\/new/);
  });
});
