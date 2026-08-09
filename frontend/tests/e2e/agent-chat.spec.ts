import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

const MOCK_AGENTS = [
  {
    name: "test-agent",
    description: "A test agent for E2E tests",
    system_prompt: "You are a test agent.",
  },
];

test.describe("Agent chat", () => {
  test("agent gallery page loads and shows agents", async ({ page }) => {
    mockLangGraphAPI(page, { agents: MOCK_AGENTS });

    await page.goto("/workspace/agents");

    // The agent card should appear with the agent name
    await expect(page.getByText("test-agent")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("agent chat page loads with input box", async ({ page }) => {
    mockLangGraphAPI(page, { agents: MOCK_AGENTS });

    await page.goto("/workspace/agents/test-agent/chats/new");

    // The prompt input textarea should be visible
    const textarea = page.getByPlaceholder(/how can i assist you/i);
    await expect(textarea).toBeVisible({ timeout: 15_000 });
  });

  test("agent chat page shows agent badge", async ({ page }) => {
    mockLangGraphAPI(page, { agents: MOCK_AGENTS });

    await page.goto("/workspace/agents/test-agent/chats/new");

    // The agent badge should display in the header (scoped to header to avoid
    // matching the welcome area which also shows the agent name)
    await expect(
      page.locator("header span", { hasText: "test-agent" }),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("Growth Analyst has a dedicated identity and quick actions", async ({
    page,
  }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/data-inspector/chats/new");

    await expect(
      page.locator("header span", { hasText: "Growth Analyst" }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Data overview")).toBeVisible();
    await expect(page.getByText("Find anomalies")).toBeVisible();
    await expect(page.getByText("Improvement areas")).toBeVisible();
  });

  test("Growth Analyst can switch interview demo scenarios without removing manual files", async ({
    page,
  }) => {
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/data-inspector/chats/new");

    const demoCard = page.getByTestId("growth-demo-data");
    await expect(demoCard).toBeVisible({ timeout: 15_000 });
    await expect(
      demoCard.getByText("3 CSVs · 200 users · conversion experiment"),
    ).toBeVisible();
    for (const label of [
      "A/B test",
      "Channel ROI",
      "Retention",
      "Merchandising",
    ]) {
      await expect(demoCard.getByRole("tab", { name: label })).toBeVisible();
    }

    await page.locator('input[type="file"]').first().setInputFiles({
      name: "manual-interview-note.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("note,value\nsource,manual\n"),
    });

    await demoCard
      .getByRole("button", { name: "Load selected data" })
      .click();

    const attachments = page.getByTestId("prompt-input-attachments");
    await expect(attachments).toBeVisible();
    await expect(
      attachments.getByText("manual-interview-note.csv", { exact: true }),
    ).toBeVisible();
    for (const name of ["customers.csv", "assignments.csv", "outcomes.csv"]) {
      await expect(attachments.getByText(name, { exact: true })).toBeVisible();
    }
    await expect(
      demoCard.getByRole("button", { name: "Selected data loaded" }),
    ).toBeVisible();
    await expect(page.getByPlaceholder(/how can i assist you/i)).toHaveValue(
      /join customers, assignments, and outcomes/i,
    );

    await demoCard.getByRole("tab", { name: "Channel ROI" }).click();
    await expect(
      demoCard.getByText("3 CSVs · 30 days · 4 channels · 12 campaigns"),
    ).toBeVisible();
    await demoCard
      .getByRole("button", { name: "Load selected data" })
      .click();

    for (const name of ["ad_spend.csv", "sessions.csv", "orders.csv"]) {
      await expect(attachments.getByText(name, { exact: true })).toBeVisible();
    }
    for (const name of ["customers.csv", "assignments.csv", "outcomes.csv"]) {
      await expect(attachments.getByText(name, { exact: true })).toHaveCount(0);
    }
    await expect(
      attachments.getByText("manual-interview-note.csv", { exact: true }),
    ).toBeVisible();
    await expect(page.getByPlaceholder(/how can i assist you/i)).toHaveValue(
      /join ad_spend, sessions, and orders/i,
    );

    await demoCard.getByRole("tab", { name: "Retention" }).click();
    await expect(
      demoCard.getByText("3 CSVs · 12 weekly cohorts · 240 users"),
    ).toBeVisible();
    await expect(
      demoCard.getByTestId("growth-demo-files").getByText("events.csv"),
    ).toBeVisible();

    await demoCard.getByRole("tab", { name: "Merchandising" }).click();
    await expect(
      demoCard.getByText("3 CSVs · 8 SKUs · 240 orders"),
    ).toBeVisible();
    await expect(
      demoCard.getByTestId("growth-demo-files").getByText("products.csv"),
    ).toBeVisible();
    await demoCard
      .getByRole("button", { name: "Load selected data" })
      .click();
    for (const name of ["products.csv", "orders.csv", "order_items.csv"]) {
      await expect(attachments.getByText(name, { exact: true })).toHaveCount(1);
    }
    for (const name of ["ad_spend.csv", "sessions.csv"]) {
      await expect(attachments.getByText(name, { exact: true })).toHaveCount(0);
    }
    await expect(
      attachments.getByText("manual-interview-note.csv", { exact: true }),
    ).toBeVisible();
    await expect(page.getByPlaceholder(/how can i assist you/i)).toHaveValue(
      /join products, orders, and order_items/i,
    );
  });

  test("OpenSKU keeps its launch team available in the default Flash mode", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);

    await page.goto("/workspace/agents/ecom-launch/chats/new");

    await expect(
      page.getByRole("button", { name: "Flash", exact: true }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: "Launch Team", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Flash keeps specialist capability available without extra planning overhead. Active roles appear here only when real work is assigned.",
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      page.getByText("Evidence Checker", { exact: true }),
    ).toHaveCount(0);
    await expect(page.getByText("证据检查员", { exact: true })).toHaveCount(0);
    await expect(page.getByText("开启 Ultra 后", { exact: false })).toHaveCount(
      0,
    );
    await expect(page.getByText("校准", { exact: true })).toHaveCount(0);
  });

  test("shows an atomic Flash Launch Pack in chat and syncs delivery state", async ({
    page,
  }, testInfo) => {
    const threadId = "00000000-0000-0000-0000-000000003123";
    const packFiles = [
      "/mnt/user-data/outputs/launch-war-room.html",
      "/mnt/user-data/outputs/evidence-ledger.json",
      "/mnt/user-data/outputs/competitor-table.csv",
      "/mnt/user-data/outputs/positioning-brief.md",
      "/mnt/user-data/outputs/listing-pack.md",
      "/mnt/user-data/outputs/content-pack.md",
      "/mnt/user-data/outputs/launch-calendar.csv",
    ];
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: threadId,
          title: "Flash Launch Pack delivery",
          agent_name: "ecom-launch",
          messages: [
            {
              type: "human",
              id: "msg-human-render-pack",
              content: "输出通勤咖啡杯 Launch Validation Pack",
            },
            {
              type: "ai",
              id: "msg-ai-render-pack",
              content: "",
              tool_calls: [
                {
                  id: "call-render-pack",
                  name: "render_launch_pack",
                  args: { spec: { category: "通勤咖啡杯" } },
                },
              ],
            },
            {
              type: "tool",
              id: "msg-tool-render-pack",
              name: "render_launch_pack",
              tool_call_id: "call-render-pack",
              content: "Successfully presented files",
              additional_kwargs: { artifacts: packFiles },
            },
            {
              type: "ai",
              id: "msg-ai-render-pack-final",
              content:
                "Launch Validation Pack 已交付，文件可在下方卡片和右上角文件入口查看。",
            },
          ],
        },
      ],
    });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.context().addCookies([
      {
        name: "locale",
        value: "zh-CN",
        url: String(testInfo.project.use.baseURL),
      },
    ]);

    await page.goto(`/workspace/agents/ecom-launch/chats/${threadId}`);

    await expect(page.getByTestId("artifact-delivery")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("artifact-delivery")).toContainText(
      "Launch Validation Pack",
    );
    const deliveryCard = page.getByTestId("artifact-delivery");
    for (const filepath of packFiles) {
      await expect(
        deliveryCard.getByText(filepath.split("/").at(-1)!, { exact: true }),
      ).toBeVisible();
    }
    await expect(
      page.getByText("7/7 个核心文件已落地", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("交付进度", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByText("Launch Validation Pack 已生成", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "市场研究员", exact: true }),
    ).toHaveCount(0);
    await expect(page.getByTestId("artifact-trigger")).toContainText("文件");
    await expect(page.getByTestId("artifact-trigger")).toContainText("7");
  });
});
