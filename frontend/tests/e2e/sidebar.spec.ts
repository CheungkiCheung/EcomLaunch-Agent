import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

test.describe("Sidebar navigation", () => {
  test("sidebar contains both primary agent links", async ({ page }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    // Sidebar uses data-sidebar="menu-button" with asChild rendering on <Link>
    const sidebar = page.locator("[data-sidebar='sidebar']");
    await expect(sidebar.locator("a[href='/workspace/chats']")).toBeVisible({
      timeout: 15_000,
    });
    await expect(sidebar.locator("a[href='/workspace/agents']")).toBeVisible();
    await expect(
      sidebar.locator("a[href='/workspace/agents/ecom-launch/chats/new']"),
    ).toBeVisible();
    await expect(
      sidebar.locator("a[href='/workspace/agents/data-inspector/chats/new']"),
    ).toBeVisible();
    await expect(
      sidebar.locator("a[href='/workspace/war-room']"),
    ).toBeVisible();
  });

  test("War Room opens as a standalone workspace above agent chats", async ({
    page,
  }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    const sidebar = page.locator("[data-sidebar='sidebar']");
    const warRoomLink = sidebar.locator("a[href='/workspace/war-room']");
    await expect(warRoomLink).toBeVisible({ timeout: 15_000 });
    await warRoomLink.click();

    await expect(page).toHaveURL(/\/workspace\/war-room/);
    await expect(
      page.getByRole("heading", { name: "智能商业作战室" }),
    ).toBeVisible();
    const warRoomCanvas = page.locator("canvas");
    await expect(warRoomCanvas).toHaveCount(1, { timeout: 15_000 });
    await expect(warRoomCanvas).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Growth Analyst 待命" }),
    ).toBeVisible();
  });

  test("Growth Analyst link opens its own chat", async ({ page }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    const dataInspectorLink = page.locator(
      "[data-sidebar='sidebar'] a[href='/workspace/agents/data-inspector/chats/new']",
    );
    await expect(dataInspectorLink).toBeVisible({ timeout: 15_000 });
    await dataInspectorLink.click();

    await expect(page).toHaveURL(
      /\/workspace\/agents\/data-inspector\/chats\/new/,
    );
    await expect(page.getByText("Data overview")).toBeVisible();
  });

  test("recent chats are scoped to the active primary agent", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: "data-thread",
          title: "Data analysis thread",
          agent_name: "data-inspector",
        },
        {
          thread_id: "launch-thread",
          title: "Launch validation thread",
          agent_name: "ecom-launch",
        },
      ],
    });

    await page.goto("/workspace/agents/data-inspector/chats/new");

    const sidebar = page.locator("[data-sidebar='sidebar']");
    await expect(sidebar.getByText("Data analysis thread")).toBeVisible({
      timeout: 15_000,
    });
    await expect(sidebar.getByText("Launch validation thread")).toHaveCount(0);
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
});
