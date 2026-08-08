import { expect, test, type Page } from "@playwright/test";

function trackApplicationApiRequests(page: Page) {
  const requests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (
      url.pathname.startsWith("/api/") ||
      url.pathname.startsWith("/mock/api/")
    ) {
      requests.push(url.pathname);
    }
  });
  return requests;
}

test.describe("Credential-free English interview demo", () => {
  test("shows the real Launch Team topology, deterministic preflight, and outputs", async ({
    page,
  }) => {
    const applicationApiRequests = trackApplicationApiRequests(page);

    await page.goto("/demo?scenario=launch");

    await expect(page.getByTestId("scenario-launch")).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(page.getByTestId("recorded-demo-notice")).toContainText(
      "no live agents are running",
    );
    await expect(page.getByTestId("demo-war-room")).toBeVisible();
    await expect(
      page.getByTestId("demo-agent-status").locator("[data-agent-id]"),
    ).toHaveCount(5);
    await expect(page.getByTestId("demo-agent-status")).toContainText(
      "Launch Director",
    );
    await expect(page.getByTestId("demo-agent-status")).toContainText(
      "Market Researcher",
    );
    await expect(
      page.locator('[data-agent-id="evidence-checker"]'),
    ).toHaveCount(0);
    await expect(page.getByTestId("deterministic-pipeline")).toContainText(
      "Preflight",
    );
    const agentLoop = page.getByTestId("agent-environment-loop");
    await expect(agentLoop).toBeVisible();
    await expect(agentLoop.locator("[data-loop-round]")).toHaveCount(2);
    await expect(agentLoop).toContainText("Environment observation");
    await expect(agentLoop).toContainText(
      "Minimal repair selected from Observation",
    );
    await expect(agentLoop).toContainText("2 / 5 iterations used");
    await expect(agentLoop).toContainText("Success criteria met");
    await expect(page.getByTestId("loop-agent-decision")).toContainText(
      "evidence-ledger.json",
    );
    await expect(page.getByTestId("loop-stop-condition")).toContainText(
      "Revision scope 2/7 files",
    );
    await expect(
      page.getByTestId("demo-deliverables").getByRole("link"),
    ).toHaveCount(4);

    const walkthrough = page.getByTestId("guided-walkthrough");
    await walkthrough.getByRole("button", { name: "Start tour" }).click();
    await expect(walkthrough).toHaveAttribute("data-active-step", "0");
    await expect(walkthrough).toContainText("Brief:");

    expect(applicationApiRequests).toEqual([]);
  });

  test("switches to a deterministic Growth Analyst experiment", async ({
    page,
  }) => {
    const applicationApiRequests = trackApplicationApiRequests(page);

    await page.goto("/demo?scenario=growth");

    await expect(page.getByTestId("scenario-growth")).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(
      page.getByRole("heading", {
        name: "Turn three business files into an experiment decision.",
      }),
    ).toBeVisible();
    await expect(
      page.getByTestId("demo-agent-status").locator("[data-agent-id]"),
    ).toHaveCount(2);
    await expect(page.getByTestId("demo-agent-status")).toContainText(
      "Growth Analyst",
    );
    await expect(page.getByTestId("deterministic-pipeline")).toContainText(
      "Read-only DuckDB query",
    );
    await expect(page.getByTestId("demo-verification")).toContainText(
      "p = 0.0346",
    );
    await expect(page.getByTestId("demo-verification")).toContainText(
      "+0.18 to +4.84 pp",
    );
    await expect(
      page.getByTestId("demo-deliverables").getByRole("link"),
    ).toHaveCount(4);

    expect(applicationApiRequests).toEqual([]);
  });

  test("keeps the selected language across both Chinese demo scenarios", async ({
    page,
    request,
  }) => {
    const applicationApiRequests = trackApplicationApiRequests(page);

    await page.goto("/demo?scenario=launch&lang=zh");

    await expect(page.getByTestId("lang-zh")).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(page.getByTestId("lang-en")).toHaveAttribute(
      "href",
      "/demo?scenario=launch&lang=en",
    );
    await expect(
      page.getByRole("heading", {
        name: "一份商品 Brief，生成一套可决策的上新包。",
      }),
    ).toBeVisible();
    await expect(page.getByTestId("guided-walkthrough")).toContainText(
      "60 秒面试引导演示",
    );
    await expect(
      page.getByTestId("guided-walkthrough").getByRole("button", {
        name: "开始演示",
      }),
    ).toBeVisible();
    await expect(page.getByTestId("scenario-growth")).toHaveAttribute(
      "href",
      "/demo?scenario=growth&lang=zh",
    );
    await expect(page.getByTestId("scenario-growth")).toContainText("增长实验");
    await expect(
      page
        .getByTestId("demo-deliverables")
        .locator('a[href="/demo/opensku-coffee-mug/launch-decision.zh-CN.md"]'),
    ).toHaveCount(1);
    await expect(page.getByTestId("agent-environment-loop")).toContainText(
      "下一步由环境反馈决定",
    );
    await expect(page.getByTestId("loop-stop-condition")).toContainText(
      "成功条件满足",
    );

    await page.getByTestId("scenario-growth").click();

    await expect(page).toHaveURL(/scenario=growth&lang=zh/);
    await expect(
      page.getByRole("heading", {
        name: "三份业务文件，形成一项实验决策。",
      }),
    ).toBeVisible();
    await expect(page.getByTestId("demo-agent-status")).toContainText(
      "增长分析师",
    );
    await expect(page.getByTestId("demo-verification")).toContainText(
      "上线并持续监控",
    );

    const chineseDecision = await request.get(
      "/demo/opensku-growth-experiment/growth-decision.zh-CN.md",
    );
    expect(chineseDecision.ok()).toBeTruthy();
    expect(await chineseDecision.text()).toContain("上线并持续监控");

    expect(applicationApiRequests).toEqual([]);
  });

  test("exposes launch and growth decisions as real files", async ({
    request,
  }) => {
    const launchResponse = await request.get(
      "/demo/opensku-coffee-mug/launch-decision.md",
    );
    const growthResponse = await request.get(
      "/demo/opensku-growth-experiment/growth-decision.md",
    );

    expect(launchResponse.ok()).toBeTruthy();
    expect(await launchResponse.text()).toContain("VALIDATE BEFORE COMMITTING");

    expect(growthResponse.ok()).toBeTruthy();
    const growthContent = await growthResponse.text();
    expect(growthContent).toContain("SHIP WITH MONITORING");
    expect(growthContent).toContain("p = 0.0346");
  });
});
