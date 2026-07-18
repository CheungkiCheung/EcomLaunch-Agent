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
            "/outputs/launch-state.json",
            "/outputs/promotion-replan.md",
            "/outputs/knowledge-deltas.json",
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
            {
              type: "ai",
              id: "final-summary",
              content:
                "当前阶段: scale_iterate\n推荐决策: Hold\n数据边界: GMV/CTR/CVR/ROI 不可用，除非用户上传私域指标。",
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
    await expect(page.locator("[data-war-room-stage]")).toContainText(
      "scale_iterate",
    );
    await expect(page.locator("[data-war-room-decision]")).toContainText(
      "Hold",
    );
    await expect(page.locator("[data-war-room-private-metrics]")).toContainText(
      "GMV/CTR/CVR/ROI",
    );
    await expect(
      page.locator("[data-war-room-loop-artifact='launch-state.json']"),
    ).toBeVisible();
    await expect(
      page.locator("[data-war-room-loop-artifact='promotion-replan.md']"),
    ).toBeVisible();
    await expect(
      page.locator("[data-war-room-loop-artifact='knowledge-deltas.json']"),
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
