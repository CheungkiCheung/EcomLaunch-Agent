import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

test.describe("Sidebar navigation", () => {
  test("sidebar contains Chats and Agents nav links", async ({ page }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    // Sidebar uses data-sidebar="menu-button" with asChild rendering on <Link>
    const sidebar = page.locator("[data-sidebar='sidebar']");
    await expect(sidebar.locator("a[href='/workspace/chats']")).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      sidebar.getByRole("link", { name: "Chat", exact: true }),
    ).toBeVisible();
    await expect(
      sidebar.locator("a[href='/workspace/agents/ecom-launch/war-room']"),
    ).toBeVisible();
    await expect(sidebar.locator("a[href='/workspace/agents']")).toBeVisible();
  });

  test("Agents link navigates to agents page", async ({ page }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    const sidebar = page.locator("[data-sidebar='sidebar']");
    const agentsLink = sidebar.locator("a[href='/workspace/agents']");
    await expect(agentsLink).toBeVisible({ timeout: 15_000 });
    await agentsLink.click();

    await page.waitForURL("**/workspace/agents");
    await expect(page).toHaveURL(/\/workspace\/agents/);
  });

  test("War Room link opens the full EcomLaunch game workspace", async ({
    page,
  }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    const sidebar = page.locator("[data-sidebar='sidebar']");
    const warRoomLink = sidebar.locator(
      "a[href='/workspace/agents/ecom-launch/war-room']",
    );
    await expect(warRoomLink).toBeVisible({ timeout: 15_000 });
    await warRoomLink.click();

    await page.waitForURL("**/workspace/agents/ecom-launch/war-room");
    await expect(
      page.getByRole("heading", { name: "Launch War Room" }),
    ).toBeVisible();
    await expect(page.getByLabel("EcomLaunch full war room")).toBeVisible();
  });
});
