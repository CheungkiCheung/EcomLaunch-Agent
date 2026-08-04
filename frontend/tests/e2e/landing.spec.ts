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
      page.getByRole("link", { name: /view english demo/i }),
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
    await expect(page).toHaveURL(
      /\/workspace\/agents\/ecom-launch\/chats\/new/,
    );
  });

  test("English demo link opens the credential-free sample", async ({
    page,
  }) => {
    await page.goto("/");

    await page.getByRole("link", { name: /view english demo/i }).click();

    await expect(page).toHaveURL(/\/demo$/);
    await expect(
      page.getByRole("heading", {
        name: /see an ecommerce launch team turn one brief into a decision pack/i,
      }),
    ).toBeVisible();
  });
});
