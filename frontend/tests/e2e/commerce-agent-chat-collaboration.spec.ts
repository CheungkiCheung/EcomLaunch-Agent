import { expect, test, type Page } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

const THREAD_ID = "00000000-0000-0000-0000-000000000301";
const RUN_ID = "00000000-0000-0000-0000-000000000302";
const CREATED_AT = "2026-07-26T12:00:00Z";

test.describe("Commerce Agent Chat-first collaboration UI", () => {
  test.beforeEach(async ({ page }) => {
    await page.context().addCookies([
      {
        name: "locale",
        value: "zh-CN",
        url: "http://localhost:3000",
      },
    ]);
    mockLangGraphAPI(page, {
      agents: [
        {
          name: "commerce-agent",
          description: "中文电商经营诊断与行动 Agent",
          system_prompt: "使用真实任务与证据回答。",
        },
      ],
      threads: [
        {
          thread_id: THREAD_ID,
          title: "履约异常诊断",
          agent_name: "commerce-agent",
        },
      ],
    });
  });

  test("uses DeerFlow Chat as the single Chinese product entry", async ({
    page,
  }) => {
    await page.goto("/workspace/agents/commerce-agent/chats/new");

    const sidebar = page.locator("[data-sidebar='sidebar']");
    const commerceEntry = sidebar.locator(
      "a[href='/workspace/agents/commerce-agent/chats/new']",
    );
    await expect(commerceEntry).toHaveCount(1);
    await expect(commerceEntry).toContainText("电商经营诊断");
    await expect(
      sidebar.locator("a[href='/workspace/agents/ecom-launch/war-room']"),
    ).toHaveCount(0);

    await expect(
      page.getByRole("heading", { name: "电商经营诊断", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("上传真实经营数据", { exact: false }),
    ).toBeVisible();
    await expect(page.getByText("确定性指标", { exact: true })).toBeVisible();
    await expect(page.getByText("动态子任务", { exact: true })).toBeVisible();
    await expect(page.getByText("证据与反证", { exact: true })).toBeVisible();
    await expect(page.getByText("独立核验", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "协作空间" })).toHaveCount(0);
    await expect(page.getByText("Launch Crew")).toHaveCount(0);
    await expect(page.getByText("War Room")).toHaveCount(0);
  });

  test("opens the native file chooser from the visible attachment button", async ({
    page,
  }) => {
    await page.goto("/workspace/agents/commerce-agent/chats/new");

    const attachmentButton = page.locator("button:has(svg.lucide-paperclip)");
    await expect(attachmentButton).toHaveCount(1);
    await expect(attachmentButton).toBeVisible();
    await expect(page.getByLabel("Upload files")).toHaveCount(1);

    const fileChooserPromise = page.waitForEvent("filechooser");
    await attachmentButton.click();
    const fileChooser = await fileChooserPromise;

    expect(fileChooser.isMultiple()).toBe(true);
    await fileChooser.setFiles({
      name: "orders.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("order_id\no1\n"),
    });
    await expect(page.getByText("orders.csv", { exact: true })).toBeVisible();
  });

  test("keeps the collaboration space empty and actor-free without a real run", async ({
    page,
  }) => {
    await page.goto("/workspace/agents/commerce-agent/war-room");

    await expect(
      page.getByRole("heading", { name: "当前没有真实协作任务" }),
    ).toBeVisible();
    await expect(page.locator("[data-commerce-actor]")).toHaveCount(0);
    await expect(page.locator("[data-commerce-room-sprite]")).toHaveCount(1);
    await expect(page.locator("[data-commerce-actor-sprite]")).toHaveCount(0);
    await expect(page.locator("[data-commerce-station-sprite]")).toHaveCount(0);
    await expect(page.getByText("主智能体", { exact: false })).toBeVisible();
    await expect(
      page.getByText("人物与动作来自真实任务/事件", { exact: false }),
    ).toBeVisible();
    await expect(page.getByText("Parent")).toHaveCount(0);
    await expect(page.getByText("Task/Event")).toHaveCount(0);
    await expect(page.getByText("War Room")).toHaveCount(0);
    await expect(page.getByRole("link", { name: "返回对话" })).toHaveAttribute(
      "href",
      "/workspace/agents/commerce-agent/chats/new",
    );
  });

  test("projects exactly one actor per durable task and preserves terminal states", async ({
    page,
  }) => {
    await mockDurableTaskAPI(page);
    await page.goto(
      `/workspace/agents/commerce-agent/war-room?threadId=${THREAD_ID}&runId=${RUN_ID}`,
    );

    await expect(page.locator("[data-commerce-actor]")).toHaveCount(4);
    await expect(page.locator("[data-commerce-actor-sprite]")).toHaveCount(4);
    await expect(page.locator("[data-commerce-station-sprite]")).toHaveCount(4);
    const generatedAssetState = await page.evaluate(() =>
      [
        ...document.querySelectorAll<HTMLImageElement>(
          "[data-commerce-room-sprite], [data-commerce-actor-sprite], [data-commerce-station-sprite]",
        ),
      ].map((image) => ({
        complete: image.complete,
        naturalWidth: image.naturalWidth,
        src: image.currentSrc || image.src,
      })),
    );
    expect(generatedAssetState).toHaveLength(9);
    expect(
      generatedAssetState.every(
        (asset) => asset.complete && asset.naturalWidth > 0,
      ),
    ).toBe(true);
    await expect(
      page.locator("[data-commerce-task-id='task-analyst']"),
    ).toHaveAttribute("data-commerce-task-status", "working");
    await expect(
      page.locator("[data-commerce-task-id='task-failed']"),
    ).toHaveAttribute("data-commerce-task-status", "failed");
    await expect(
      page.locator("[data-commerce-task-id='task-cancelled']"),
    ).toHaveAttribute("data-commerce-task-status", "cancelled");
    await expect(
      page.locator("[data-commerce-task-id='task-timeout']"),
    ).toHaveAttribute("data-commerce-task-status", "timed_out");

    await expect(page.getByText("任务未完成，可查看原因")).toBeVisible();
    await expect(page.getByText("任务已取消")).toBeVisible();
    await expect(page.getByText("任务已超时")).toBeVisible();

    const analyst = page.locator("[data-commerce-task-id='task-analyst']");
    await expect(analyst).toHaveCount(1);
    await analyst.click();
    const drawer = page.locator("[data-commerce-actor-drawer]");
    await expect(drawer).toBeVisible();
    await expect(drawer).toContainText("当前任务详情");
    await expect(drawer).toContainText("task-analyst");
    await expect(drawer).toContainText("正在使用：窗口对比");

    await expect(page.locator("[data-war-room-agent]")).toHaveCount(0);
    await expect(page.getByText("Launch Crew")).toHaveCount(0);
    await expect(page.getByRole("link", { name: "返回对话" })).toHaveAttribute(
      "href",
      `/workspace/agents/commerce-agent/chats/${THREAD_ID}`,
    );
  });

  test("stays usable without horizontal overflow on a narrow viewport", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/workspace/agents/commerce-agent/war-room");

    await expect(
      page.getByRole("heading", { name: "经营诊断协作空间" }),
    ).toBeVisible();
    await expect(page.getByText("无任务", { exact: true })).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
  });

  test("keeps four real task actors usable on a narrow viewport", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockDurableTaskAPI(page);
    await page.goto(
      `/workspace/agents/commerce-agent/war-room?threadId=${THREAD_ID}&runId=${RUN_ID}`,
    );

    await expect(page.locator("[data-commerce-actor]")).toHaveCount(4);
    const layout = await page.evaluate(() => {
      const scene = document.querySelector<HTMLElement>(
        "[data-commerce-collaboration-scene]",
      );
      const actors = [
        ...document.querySelectorAll<HTMLElement>("[data-commerce-actor]"),
      ];
      if (!scene) return null;
      const sceneRect = scene.getBoundingClientRect();
      return {
        viewport: document.documentElement.clientWidth,
        content: document.documentElement.scrollWidth,
        actors: actors.map((actor) => {
          const rect = actor.getBoundingClientRect();
          return {
            height: rect.height,
            insideHorizontalBounds:
              rect.left >= sceneRect.left - 1 &&
              rect.right <= sceneRect.right + 1,
            width: rect.width,
          };
        }),
      };
    });

    expect(layout).not.toBeNull();
    expect(layout!.content).toBeLessThanOrEqual(layout!.viewport);
    expect(
      layout!.actors.every(
        (actor) =>
          actor.insideHorizontalBounds &&
          actor.width >= 90 &&
          actor.height >= 90,
      ),
    ).toBe(true);
  });
});

async function mockDurableTaskAPI(page: Page) {
  const tasks = [
    task("task-analyst", "analyst", "定位履约异常阶段", "running"),
    task("task-failed", "explore", "检查缺失字段", "failed"),
    task("task-cancelled", "operator", "准备行动草案", "cancelled"),
    task("task-timeout", "verifier", "独立核验结论", "timed_out"),
  ];
  await page.route(`**/api/runs/${RUN_ID}/subagent-tasks`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: tasks }),
    }),
  );
  await page.route(/\/api\/subagent-tasks\/[^/]+\/events\?/, (route) => {
    const taskId = new URL(route.request().url()).pathname.split("/").at(-2)!;
    const events =
      taskId === "task-analyst"
        ? [
            event(taskId, 1, "task.running"),
            event(taskId, 2, "task.tool_result", {
              tool_name: "commerce_compare_windows",
            }),
          ]
        : [event(taskId, 1, `task.${statusEventSuffix(taskId)}`)];
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        data: events,
        next_after_seq: events.at(-1)?.seq ?? 0,
        has_more: false,
      }),
    });
  });
}

function task(
  taskId: string,
  subagentType: string,
  description: string,
  status: "running" | "failed" | "cancelled" | "timed_out",
) {
  return {
    task_id: taskId,
    thread_id: THREAD_ID,
    run_id: RUN_ID,
    user_id: null,
    parent_task_id: null,
    subagent_type: subagentType,
    description,
    context_packet: {
      schema_version: "1.0",
      goal: description,
      source_refs: ["dataset:olist"],
      evidence_refs: [],
      constraints: {},
      available_skills: ["fulfillment-investigation"],
      available_tools: ["commerce_compare_windows"],
      budget: { max_tool_rounds: 2 },
      expected_output_schema: {},
      metadata: {},
    },
    tool_policy: {},
    depends_on: [],
    metadata: {},
    status,
    result: null,
    error: status === "failed" ? { message: "字段不足" } : null,
    checkpoint: null,
    telemetry: {},
    wait_reason: null,
    version: 1,
    event_seq: 2,
    attempt: 1,
    max_attempts: 1,
    priority: 0,
    lease_owner: null,
    lease_token: 0,
    lease_expires_at: null,
    created_at: CREATED_AT,
    updated_at: CREATED_AT,
    started_at: CREATED_AT,
    completed_at: status === "running" ? null : CREATED_AT,
  };
}

function event(
  taskId: string,
  seq: number,
  eventType: string,
  payload: Record<string, unknown> = {},
) {
  return {
    task_id: taskId,
    thread_id: THREAD_ID,
    run_id: RUN_ID,
    seq,
    event_type: eventType,
    payload,
    idempotency_key: `${taskId}:${seq}`,
    created_at: CREATED_AT,
  };
}

function statusEventSuffix(taskId: string) {
  if (taskId === "task-failed") return "failed";
  if (taskId === "task-cancelled") return "cancelled";
  return "timed_out";
}
