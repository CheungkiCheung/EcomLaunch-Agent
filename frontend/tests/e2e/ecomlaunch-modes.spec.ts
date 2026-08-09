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
  test("War Room shows empty state without run data", async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);

    await page.context().addCookies([
      {
        name: "locale",
        value: "zh-CN",
        url: String(testInfo.project.use.baseURL),
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

  test("War Room replays the latest real Launch run", async ({ page }) => {
    const threadId = "00000000-0000-0000-0000-000000003125";
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: threadId,
          title: "通勤咖啡杯 Launch Validation Pack",
          agent_name: "ecom-launch",
          messages: [
            {
              type: "human",
              id: "replay-human",
              content: "判断 99-199 元通勤咖啡杯是否值得做",
            },
            {
              type: "ai",
              id: "replay-task-call",
              content: "",
              tool_calls: [
                {
                  id: "replay-task-1",
                  name: "task",
                  args: {
                    subagent_type: "market-voc-researcher",
                    description: "采集公开市场与用户声音",
                  },
                },
              ],
            },
            {
              type: "tool",
              id: "replay-task-result",
              tool_call_id: "replay-task-1",
              content: "Task Succeeded. Result: 价格带信号已整理",
              additional_kwargs: { subagent_status: "completed" },
            },
            {
              type: "ai",
              id: "replay-render-call",
              content: "",
              tool_calls: [
                {
                  id: "replay-render-1",
                  name: "render_launch_pack",
                  args: { spec: { category: "通勤咖啡杯" } },
                },
              ],
            },
            {
              type: "tool",
              id: "replay-render-result",
              tool_call_id: "replay-render-1",
              content: "Successfully presented files",
            },
            {
              type: "ai",
              id: "replay-final",
              content: "建议进入 7 天轻量验证。",
            },
          ],
        },
      ],
    });
    await page.context().addCookies([
      {
        name: "locale",
        value: "zh-CN",
        url: "http://localhost:3000",
      },
    ]);
    await page.goto("/workspace/war-room");

    const replay = page.getByTestId("war-room-replay");
    await expect(replay).toBeVisible({ timeout: 15_000 });
    await expect(replay.getByText("运行回放", { exact: true })).toBeVisible();
    await expect(
      replay.getByRole("button", { name: "播放回放" }),
    ).toBeVisible();
    await replay.getByRole("button", { name: "播放回放" }).click();
    await replay.getByRole("button", { name: "下一个事件" }).click();
    await expect(page.getByTestId("war-room-replay-event-title")).toHaveText(
      "分派给市场研究员",
    );
    await replay.getByRole("button", { name: "返回实时" }).click();
    await expect(
      replay.getByText("实时", { exact: true }).first(),
    ).toBeVisible();
  });

  test("War Room switches to and replays a real Growth Analyst run", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: "00000000-0000-0000-0000-000000003127",
          title: "通勤咖啡杯 Launch Validation Pack",
          agent_name: "ecom-launch",
          messages: [
            {
              type: "human",
              id: "growth-switch-launch-human",
              content: "输出上新验证包",
            },
            {
              type: "ai",
              id: "growth-switch-launch-ai",
              content: "已完成公开信号研究",
            },
          ],
        },
        {
          thread_id: "00000000-0000-0000-0000-000000003128",
          title: "增长实验分析",
          agent_name: "data-inspector",
          messages: [
            {
              type: "human",
              id: "growth-replay-human",
              content: "分析三份增长数据并判断是否继续投放",
            },
            {
              type: "ai",
              id: "growth-replay-inspect-call",
              content: "",
              tool_calls: [
                {
                  id: "growth-replay-inspect-1",
                  name: "inspect_data",
                  args: {
                    filenames: ["users.csv", "events.csv", "orders.csv"],
                  },
                },
              ],
            },
            {
              type: "tool",
              id: "growth-replay-inspect-result",
              tool_call_id: "growth-replay-inspect-1",
              content: "3 tables inspected",
            },
            {
              type: "ai",
              id: "growth-replay-query-call",
              content: "",
              tool_calls: [
                {
                  id: "growth-replay-query-1",
                  name: "query_data",
                  args: { sql: "SELECT variant, COUNT(*) FROM experiments" },
                },
              ],
            },
            {
              type: "tool",
              id: "growth-replay-query-result",
              tool_call_id: "growth-replay-query-1",
              content: "control=100, variant=100",
            },
            {
              type: "ai",
              id: "growth-replay-experiment-call",
              content: "",
              tool_calls: [
                {
                  id: "growth-replay-experiment-1",
                  name: "analyze_ab_test",
                  args: { control_conversions: 10, variant_conversions: 20 },
                },
              ],
            },
            {
              type: "tool",
              id: "growth-replay-experiment-result",
              tool_call_id: "growth-replay-experiment-1",
              content: "p=0.0477; uplift=+10.00 pp; no SRM",
            },
            {
              type: "ai",
              id: "growth-replay-final",
              content: "SHIP WITH MONITORING",
            },
          ],
        },
      ],
    });
    await page.context().addCookies([
      {
        name: "locale",
        value: "zh-CN",
        url: "http://localhost:3000",
      },
    ]);
    await page.goto("/workspace/war-room");

    const replay = page.getByTestId("war-room-replay");
    await expect(replay).toBeVisible({ timeout: 15_000 });
    const sources = replay.getByTestId("war-room-replay-sources");
    await expect(sources).toBeVisible();
    await expect(
      sources.getByRole("button", { name: "上新团队", exact: true }),
    ).toBeVisible();
    await expect(
      sources.getByRole("button", { name: "增长分析师", exact: true }),
    ).toBeVisible();

    await sources
      .getByRole("button", { name: "增长分析师", exact: true })
      .click();
    await expect(
      replay.getByText("增长实验分析", { exact: true }),
    ).toBeVisible();

    await replay.getByRole("button", { name: "播放回放" }).click();
    await replay.getByRole("button", { name: "暂停回放" }).click();
    await expect(page.getByTestId("war-room-replay-event-title")).toHaveText(
      "收到任务需求",
    );

    await replay.getByRole("button", { name: "下一个事件" }).click();
    await expect(page.getByTestId("war-room-replay-event-title")).toHaveText(
      "检查上传数据",
    );

    await page.locator("summary", { hasText: "运行详情" }).click();
    await expect(
      page.getByText("增长分析流水线", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("数据查询", { exact: true })).toBeVisible();
    await expect(page.getByText("实验分析", { exact: true })).toHaveCount(2);
    await expect(page.getByText("任务队列", { exact: true })).toHaveCount(0);

    await replay.getByRole("button", { name: "返回实时" }).click();
    await expect(
      replay.getByRole("button", { name: "返回实时" }),
    ).toBeDisabled();
  });

  test("War Room switches languages and keeps a compact layout usable", async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1100, height: 800 });
    mockLangGraphAPI(page);

    await page.context().addCookies([
      {
        name: "locale",
        value: "en-US",
        url: String(testInfo.project.use.baseURL),
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
  test("EcomLaunch input exposes the attachment picker", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/ecom-launch/chats/new");

    const textarea = page.getByPlaceholder(
      /今天我能为你做些什么|how can i assist/i,
    );
    await expect(textarea).toBeVisible({ timeout: 15_000 });

    await expect(
      page.getByRole("button", { name: /Add attachments|添加附件/ }),
    ).toBeVisible();
    await expect(page.getByLabel("Upload files")).toHaveCount(1);
  });
});
