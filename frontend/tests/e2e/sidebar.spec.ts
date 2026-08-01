import { expect, test } from "@playwright/test";

import { MOCK_THREAD_ID, mockLangGraphAPI } from "./utils/mock-api";

test.describe("Sidebar navigation", () => {
  test("sidebar contains Chats and Agents nav links", async ({ page }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/chats/new");

    // Sidebar uses data-sidebar="menu-button" with asChild rendering on <Link>
    const sidebar = page.locator("[data-sidebar='sidebar']");
    await expect(sidebar.locator("a[href='/workspace/chats']")).toBeVisible({
      timeout: 15_000,
    });
    await expect(sidebar.getByRole("link", { name: "验证对话" })).toBeVisible();
    await expect(
      sidebar
        .locator("a[href='/workspace/agents/store-operator/chats/new']")
        .first(),
    ).toBeVisible();
    await expect(
      sidebar.locator("a[href='/workspace/agents/store-operator/war-room']"),
    ).toBeVisible();
    await expect(
      sidebar.locator("a[href='/workspace/agents/ecom-launch/war-room']"),
    ).toBeVisible();
    await expect(sidebar.locator("a[href='/workspace/agents']")).toBeVisible();
  });

  test("商铺运营作战室只同步真实 Task 状态", async ({ page }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: MOCK_THREAD_ID,
          title: "近期经营分析",
          agent_name: "store-operator",
          messages: [
            {
              type: "ai",
              id: "store-task-call",
              content: "",
              tool_calls: [
                {
                  id: "store-task-analyst",
                  name: "task",
                  args: {
                    subagent_type: "analyst",
                    description: "比较最近十四天与此前十四天",
                    prompt: "使用数据工具复算两个窗口。",
                  },
                },
              ],
            },
          ],
        },
      ],
    });

    await page.goto(
      `/workspace/agents/store-operator/war-room?threadId=${MOCK_THREAD_ID}`,
    );

    await expect(
      page.getByRole("heading", { name: "商铺运营作战室" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("[data-store-war-room-stage]")).toBeVisible();
    await expect(page.locator("[data-store-agent='analyst']")).toHaveAttribute(
      "data-store-agent-active",
      "true",
    );
    await expect(page.locator("[data-store-agent='analyst']")).toHaveAttribute(
      "data-store-agent-motion",
      /returning_home|working/,
    );
    await expect(page.locator("[data-store-agent='explore']")).toHaveAttribute(
      "data-store-agent-active",
      "false",
    );
  });

  test("商铺运营作战室在移动端和减少动态效果模式下可用", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/store-operator/war-room");

    const stage = page.locator("[data-store-war-room-stage]");
    await expect(stage).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByRole("button", { name: "切换侧边栏" }),
    ).toBeVisible();
    await expect(page.locator("[data-store-agent-label='lead']")).toBeVisible();
    await expect(
      page.locator("[data-store-agent-label='explore']"),
    ).toBeHidden();
    const initialExploreStyle = await page
      .locator("[data-store-agent='explore']")
      .getAttribute("style");
    await page.waitForTimeout(4500);
    await expect(page.locator("[data-store-agent='explore']")).toHaveAttribute(
      "style",
      initialExploreStyle ?? "",
    );

    const stageBox = await stage.boundingBox();
    const asideBox = await page.locator("aside").boundingBox();
    expect(stageBox).not.toBeNull();
    expect(asideBox).not.toBeNull();
    expect(stageBox!.width).toBeGreaterThan(300);
    expect(asideBox!.y).toBeGreaterThan(stageBox!.y + stageBox!.height - 1);

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);
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
    await expect(page.getByLabel("Animated EcomLaunch war room")).toBeVisible();
    await expect(page.locator("[data-war-room-canvas='true']")).toBeVisible();
    await page.waitForTimeout(900);
    await expect(
      page.locator("[data-war-room-agent='launch-director']"),
    ).toHaveAttribute("data-motion-state", "seated");
    await expect(
      page.locator("[data-war-room-prop='director-command-console']"),
    ).toBeVisible();
    await expect(page.locator("[data-war-room-prop$='-station']")).toHaveCount(
      5,
    );
    await expect(
      page.locator(
        "[data-war-room-character='market-voc-researcher'][data-war-room-standalone-character='true']",
      ),
    ).toBeVisible();
    await expect(
      page.locator(
        "[data-war-room-sprite-frame='walk-left'], [data-war-room-sprite-frame='walk-right'], [data-war-room-sprite-frame='walk-up'], [data-war-room-sprite-frame='walk-down']",
      ),
    ).not.toHaveCount(0);
    await expect(
      page.locator(
        "[data-war-room-path-length='3'], [data-war-room-path-length='4']",
      ),
    ).not.toHaveCount(0);
    await expect(page.locator("[data-war-room-artifact-queue]")).toBeVisible();
    await expect(page.locator("[data-war-room-artifact-drop]")).toHaveCount(0);
    await expect(page.locator("[data-war-room-artifact]")).toHaveCount(0);
    await expect(page.locator("[data-motion-state='roaming']")).not.toHaveCount(
      0,
    );
  });

  test("War Room syncs artifacts from an EcomLaunch thread", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: MOCK_THREAD_ID,
          title: "Real launch thread",
          agent_name: "ecom-launch",
          artifacts: [
            "/outputs/competitor-table.csv",
            "/outputs/listing-pack.md",
          ],
          messages: [
            {
              type: "ai",
              id: "task-call-market",
              content: "",
              tool_calls: [
                {
                  id: "task-market",
                  name: "task",
                  args: {
                    subagent_type: "market-voc-researcher",
                    description: "Cluster competitor demand signals.",
                    prompt: "Find competitor demand signals.",
                  },
                },
              ],
            },
            {
              type: "ai",
              id: "task-call-offer",
              content: "",
              tool_calls: [
                {
                  id: "task-offer",
                  name: "task",
                  args: {
                    subagent_type: "offer-architect",
                    description: "Shape the first offer wedge.",
                    prompt: "Turn market findings into positioning.",
                  },
                },
              ],
            },
            {
              type: "tool",
              id: "task-result-market",
              tool_call_id: "task-market",
              content: "Task Succeeded. Result: Competitor table ready.",
              additional_kwargs: { subagent_status: "completed" },
            },
          ],
        },
      ],
    });

    await page.goto(
      `/workspace/agents/ecom-launch/war-room?threadId=${MOCK_THREAD_ID}`,
    );

    await expect(page.getByText("Synced with Real launch thread.")).toBeVisible(
      { timeout: 15_000 },
    );
    await expect(page.locator("[data-war-room-artifact-drop]")).not.toHaveCount(
      0,
    );
    await expect(
      page.locator("[data-war-room-artifact='competitor-table.csv']"),
    ).toBeVisible();
    await expect(
      page.locator("[data-war-room-artifact='listing-pack.md']"),
    ).toBeVisible();
    await expect(
      page.locator("[data-war-room-vfx='artifact-pulse']"),
    ).toBeVisible();
    await expect(
      page.locator(
        "[data-war-room-vfx='station-active'][data-war-room-vfx-agent='offer-architect']",
      ),
    ).toBeVisible();
    await expect(
      page.locator(
        "[data-war-room-carried-package][data-war-room-carried-agent='market-voc-researcher']",
      ),
    ).toBeVisible();
  });

  test("War Room keeps the game canvas usable on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: MOCK_THREAD_ID,
          title: "Mobile launch thread",
          agent_name: "ecom-launch",
          artifacts: ["/outputs/competitor-table.csv"],
        },
      ],
    });

    await page.goto(
      `/workspace/agents/ecom-launch/war-room?threadId=${MOCK_THREAD_ID}`,
    );
    await expect(page.locator("[data-war-room-canvas='true']")).toBeVisible({
      timeout: 15_000,
    });

    const stageBox = await page
      .getByLabel("Animated EcomLaunch war room")
      .boundingBox();
    const asideBox = await page.locator("aside").boundingBox();

    expect(stageBox).not.toBeNull();
    expect(asideBox).not.toBeNull();
    expect(stageBox!.width).toBeGreaterThan(300);
    expect(asideBox!.y).toBeGreaterThan(stageBox!.y + stageBox!.height - 1);
  });
});
