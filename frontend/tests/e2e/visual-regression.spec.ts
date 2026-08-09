import {
  expect,
  test,
  type Locator,
  type Page,
  type TestInfo,
} from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

test.use({ locale: "en-US" });

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({
    colorScheme: "light",
    reducedMotion: "reduce",
  });
});

async function settleVisuals(page: Page) {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        caret-color: transparent !important;
        transition-duration: 0s !important;
      }
    `,
  });
  await page.evaluate(() => document.fonts.ready);
}

async function captureVisual(
  page: Page,
  testInfo: TestInfo,
  name: string,
  options: { fullPage?: boolean; target?: Locator } = {},
) {
  if (process.env.CI) {
    const path = testInfo.outputPath(name);
    if (options.target) {
      await options.target.screenshot({
        animations: "disabled",
        path,
      });
    } else {
      await page.screenshot({
        animations: "disabled",
        fullPage: options.fullPage,
        path,
      });
    }
    await testInfo.attach(name, { contentType: "image/png", path });
    return;
  }

  if (options.target) {
    await expect(options.target).toHaveScreenshot(name, {
      animations: "disabled",
      maxDiffPixelRatio: 0.02,
    });
    return;
  }

  await expect(page).toHaveScreenshot(name, {
    animations: "disabled",
    fullPage: options.fullPage,
    maxDiffPixelRatio: 0.02,
  });
}

test.describe("OpenSKU visual regression", () => {
  test("landing hero remains balanced at desktop size", async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "从产品想法到" }),
    ).toBeVisible();
    await settleVisuals(page);

    await captureVisual(page, testInfo, "landing-desktop.png");
  });

  test("Chinese verification loop keeps the action-observation hierarchy", async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/demo?scenario=launch&lang=zh");
    const loop = page.getByTestId("agent-environment-loop");
    await expect(loop).toBeVisible();
    await expect(loop.locator("[data-loop-round]")).toHaveCount(2);
    await settleVisuals(page);

    await captureVisual(page, testInfo, "launch-loop-zh.png", {
      target: loop,
    });
  });

  test("War Room keeps the room and team rail aligned on desktop", async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    mockLangGraphAPI(page);
    await page.context().addCookies([
      {
        name: "locale",
        value: "en-US",
        url: String(testInfo.project.use.baseURL),
      },
    ]);
    await page.goto("/workspace/war-room");
    await expect(page.getByTestId("war-room-scene")).toBeVisible();
    await expect(page.getByTestId("war-room-canvas")).toHaveAttribute(
      "data-ready",
      "true",
    );
    await settleVisuals(page);

    await captureVisual(page, testInfo, "war-room-desktop.png");
  });

  test("War Room stacks cleanly at the interview-demo compact size", async ({
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
    const scene = page.getByTestId("war-room-scene");
    const sidebar = page.getByTestId("war-room-agent-sidebar");
    await expect(scene).toBeVisible();
    await expect(page.getByTestId("war-room-canvas")).toHaveAttribute(
      "data-ready",
      "true",
    );
    await expect(sidebar).toBeVisible();
    const [sceneBox, sidebarBox] = await Promise.all([
      scene.boundingBox(),
      sidebar.boundingBox(),
    ]);
    expect(sceneBox).not.toBeNull();
    expect(sidebarBox).not.toBeNull();
    expect(sidebarBox!.y).toBeGreaterThanOrEqual(
      sceneBox!.y + sceneBox!.height,
    );
    await settleVisuals(page);

    await captureVisual(page, testInfo, "war-room-compact.png");
  });

  test("Flash Launch Pack delivery keeps files and completion state visible", async ({
    page,
  }, testInfo) => {
    const threadId = "00000000-0000-0000-0000-000000003124";
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
          title: "通勤咖啡杯 7 天轻量验证",
          agent_name: "ecom-launch",
          messages: [
            {
              type: "human",
              id: "visual-human-render-pack",
              content: "请输出通勤咖啡杯 Launch Validation Pack",
            },
            {
              type: "ai",
              id: "visual-ai-render-pack",
              content: "",
              tool_calls: [
                {
                  id: "visual-call-render-pack",
                  name: "render_launch_pack",
                  args: { spec: { category: "通勤咖啡杯" } },
                },
              ],
            },
            {
              type: "tool",
              id: "visual-tool-render-pack",
              name: "render_launch_pack",
              tool_call_id: "visual-call-render-pack",
              content: "Successfully presented files",
              additional_kwargs: { artifacts: packFiles },
            },
            {
              type: "ai",
              id: "visual-ai-render-pack-final",
              content:
                "Launch Validation Pack 已交付。7 个文件可在下方卡片或右上角“文件”中查看。",
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
    await expect(page.getByTestId("artifact-delivery")).toBeVisible();
    await expect(
      page.getByText("Launch Validation Pack 已生成", { exact: true }),
    ).toBeVisible();
    await settleVisuals(page);

    await captureVisual(page, testInfo, "flash-launch-pack-delivery-zh.png");
  });

  test("Growth Analyst welcome makes the demo dataset obvious", async ({
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
    await page.goto("/workspace/agents/data-inspector/chats/new");

    const demoCard = page.getByTestId("growth-demo-data");
    await expect(demoCard).toBeVisible();
    await expect(
      demoCard.getByText("3 个 CSV · 200 个用户 · 转化实验"),
    ).toBeVisible();
    for (const label of ["A/B 实验", "渠道 ROI", "用户留存", "商品经营"]) {
      await expect(demoCard.getByRole("tab", { name: label })).toBeVisible();
    }
    await expect(
      demoCard.getByText(
        "control 100 人 / 10 次转化 · variant 100 人 / 20 次转化",
      ),
    ).toBeVisible();
    await expect(
      demoCard.getByRole("button", { name: "载入所选数据" }),
    ).toBeVisible();
    await settleVisuals(page);

    await captureVisual(page, testInfo, "growth-analyst-demo-welcome-zh.png");
  });

  test("Growth Analyst keeps the scenario switcher visible after loading files", async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    mockLangGraphAPI(page);
    await page.context().addCookies([
      {
        name: "locale",
        value: "zh-CN",
        url: String(testInfo.project.use.baseURL),
      },
    ]);
    await page.goto("/workspace/agents/data-inspector/chats/new");

    await page.locator('input[type="file"]').first().setInputFiles({
      name: "manual.csv",
      mimeType: "text/csv",
      buffer: Buffer.from("metric,value\nmanual,1\n"),
    });
    const demoCard = page.getByTestId("growth-demo-data");
    await demoCard
      .getByRole("button", { name: "载入所选数据" })
      .click();

    await expect(
      demoCard.getByRole("tab", { name: "渠道 ROI" }),
    ).toBeInViewport();
    await expect(
      demoCard.getByRole("button", { name: "所选数据已载入" }),
    ).toBeInViewport();
    await expect(page.getByTestId("prompt-input-attachments")).toContainText(
      "manual.csv",
    );
    await settleVisuals(page);

    await captureVisual(page, testInfo, "growth-analyst-demo-loaded-zh.png");
  });
});
