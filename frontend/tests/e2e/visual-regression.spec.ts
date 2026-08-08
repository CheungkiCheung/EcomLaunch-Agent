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
});
