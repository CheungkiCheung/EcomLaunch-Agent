import { resolve } from "node:path";

import { expect, test, type Page } from "@playwright/test";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CASE_FULFILLMENT = "case_0123456789abcdef0123456789abcdef";
const CASE_REVIEW = "case_1123456789abcdef0123456789abcdef";
const CASE_EXPLICIT = "case_2123456789abcdef0123456789abcdef";
const ACTION_ID = "act_0123456789abcdef0123456789abcdef";
const RUN_ID = "run_0123456789abcdef0123456789abcdef";
const SKILL_CANDIDATE_ID = "skillcand_0123456789abcdef0123456789abcdef";
const EVIDENCE_PRIMARY = "evd_0123456789abcdef0123456789abcdef";
const EVIDENCE_CONTRADICT = "evd_1123456789abcdef0123456789abcdef";
const EVIDENCE_CONTEXT = "evd_2123456789abcdef0123456789abcdef";
const HANDLING_BASELINE = "mobs_2123456789abcdef0123456789abcde1";
const HANDLING_CURRENT = "mobs_2123456789abcdef0123456789abcde2";

test.describe("Commerce Master Shell mechanical UI", () => {
  test.beforeEach(async ({ page }, testInfo) => {
    await mockCommerceReadAPI(page, {
      initialDataset: testInfo.title.includes("Capability Report"),
    });
  });

  test("renders Chinese Case state and keeps unconnected input honest", async ({
    page,
  }) => {
    await page.goto("/commerce");

    await expect(
      page.getByRole("heading", { name: "履约延迟异常", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("4.8%", { exact: true })).toBeVisible();
    await expect(page.getByText("36.4%", { exact: true })).toBeVisible();
    await expect(
      page.getByText("+31.6 个百分点", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("深度求索 V4", { exact: true }),
    ).not.toBeVisible();
    await captureVisual(page, "case-detail-react-desktop-v1.png");

    await page
      .getByLabel("继续询问当前案例")
      .fill("请解释当前证据为什么支持这个结论");
    await page.getByRole("button", { name: "发送案例问题" }).click();
    await expect(
      page.getByText("当前内容没有发送，也没有启动新的调查。", {
        exact: false,
      }),
    ).toBeVisible();

    await page.getByRole("button", { name: "查看证据", exact: true }).click();
    await expect(
      page.getByRole("complementary", { name: "证据详情" }),
    ).toBeVisible();
    await expect(page.getByText("订单履约数据", { exact: true })).toBeVisible();
    await expect(
      page.getByText("延迟订单数 / 已履约订单数", { exact: true }),
    ).toBeVisible();
    await captureVisual(page, "case-detail-react-evidence-inspector-v1.png");
    await page.getByRole("button", { name: "关闭检查面板" }).click();

    await page.getByRole("button", { name: "运行", exact: true }).click();
    await expect(page.getByText(/深度求索 V4/)).toBeVisible();
    await expect(page.getByLabel("继续询问当前案例")).not.toBeVisible();
  });

  test("switches Cases through the left navigation", async ({ page }) => {
    await page.goto("/commerce");

    await page.getByRole("button", { name: /评价体验异常/ }).click();

    await expect(
      page.getByRole("heading", { name: "评价体验异常", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "调查记录", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "评价体验已完成", exact: true }),
    ).toBeVisible();
  });

  test("shows the Case composer only on the overview tab", async ({ page }) => {
    await page.goto("/commerce");

    await expect(page.getByLabel("继续询问当前案例")).toBeVisible();

    for (const tab of ["调查记录", "证据", "运行"]) {
      await page.getByRole("button", { name: tab, exact: true }).click();
      await expect(page.getByLabel("继续询问当前案例")).not.toBeVisible();
    }

    await page.getByRole("button", { name: "概览", exact: true }).click();
    await expect(page.getByLabel("继续询问当前案例")).toBeVisible();
  });

  test("uses off-canvas navigation and inspector on a narrow screen", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/commerce");
    await captureVisual(page, "case-detail-react-mobile-v1.png");

    await page.getByRole("button", { name: "打开导航" }).click();
    await expect(page.getByLabel("电商经营诊断导航")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /履约延迟异常/ }),
    ).toBeVisible();
    await page.getByRole("button", { name: "关闭导航" }).click();

    await page.getByRole("button", { name: "打开检查面板" }).click();
    await expect(
      page.getByRole("complementary", { name: "证据详情" }),
    ).toBeVisible();
    await expect(page.getByText("数据血缘", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "关闭检查面板" }).click();
    await expect(
      page.getByText("深度求索 V4", { exact: true }),
    ).not.toBeVisible();

    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
  });

  test("keeps the complete mobile drawer after collapsing the desktop rail", async ({
    page,
  }) => {
    await page.goto("/commerce");
    await page.getByRole("button", { name: "折叠导航", exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "打开导航", exact: true }).click();

    await expect(
      page.getByRole("button", { name: "更多", exact: true }),
    ).toBeVisible();
    await expect(
      page
        .getByLabel("电商经营诊断导航")
        .getByText("当前案例", { exact: true }),
    ).toBeVisible();
  });

  test("opens Data Inbox, uploads a batch, and records a semantic confirmation", async ({
    page,
  }) => {
    await page.goto("/commerce");

    await page.getByRole("button", { name: "数据接入", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "数据接入", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("button", { name: "案例队列", exact: true }),
    ).not.toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("heading", { name: "接入经营数据", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("还没有导入记录", { exact: true }),
    ).toBeVisible();
    await captureVisual(page, "data-inbox-react-empty-v1.png");

    await page.locator('input[type="file"]').setInputFiles({
      name: "orders.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "order_id,order_approved_at\no1,2026-07-20T00:00:00\n",
      ),
    });

    await expect(
      page.getByRole("heading", { name: "订单履约数据", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("需要你确认", { exact: true })).toBeVisible();
    await captureVisual(page, "data-inbox-react-review-v1.png");
    await page
      .getByRole("button", { name: "确认字段含义", exact: true })
      .click();
    await expect(
      page.getByText("字段含义已记录", { exact: false }),
    ).toBeVisible();
    await expect(page.getByText("字段语义", { exact: true })).toBeVisible();
    await expect(page.getByLabel("继续询问当前案例")).not.toBeVisible();

    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
  });

  test("uses Case Queue as a distinct work page with search and mobile cards", async ({
    page,
  }) => {
    await page.goto("/commerce");
    await page.getByRole("button", { name: "案例队列", exact: true }).click();

    await expect(
      page.getByRole("heading", { name: "需要处理的经营问题", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "案例队列", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("button", { name: /履约延迟异常/ }),
    ).not.toHaveAttribute("aria-current", "page");
    await expect(page.getByLabel("继续询问当前案例")).not.toBeVisible();

    await page.getByPlaceholder("搜索案例").fill("评价");
    await expect(
      page.locator("main").getByRole("heading", {
        name: "评价体验异常",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.locator("main").getByRole("heading", {
        name: "履约延迟异常",
        exact: true,
      }),
    ).not.toBeVisible();
    await page.getByPlaceholder("搜索案例").fill("");
    await captureVisual(page, "case-queue-react-desktop-v1.png");

    const reviewRow = page
      .getByRole("article")
      .filter({ hasText: "评价体验异常" });
    await reviewRow.getByRole("button", { name: /补充数据/ }).click();
    await expect(
      page.getByRole("heading", { name: "评价体验异常", exact: true }),
    ).toBeVisible();

    await page.getByRole("button", { name: "案例队列", exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await captureVisual(page, "case-queue-react-mobile-v1.png");
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
  });

  test("explores support contradiction and unknown evidence without hiding boundaries", async ({
    page,
  }) => {
    await page.goto("/commerce");
    await page.getByRole("button", { name: "证据", exact: true }).click();

    await expect(
      page.getByRole("heading", { name: "证据浏览", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /全部\s*3/ }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByText("证据详情", { exact: true }).last(),
    ).toBeVisible();
    await expect(
      page
        .getByText("该证据支持当前判断，但不能单独证明因果关系。", {
          exact: true,
        })
        .last(),
    ).toBeVisible();
    await captureVisual(page, "evidence-explorer-react-desktop-v1.png");

    await page
      .getByLabel("证据关系筛选")
      .getByRole("button", { name: /矛盾\s*1/ })
      .click();
    await expect(
      page.getByRole("heading", {
        name: "平均处理时长从 8.1 小时 变为 8.2 小时",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page
        .getByText("该证据反驳部分判断，应与支持证据共同审查。", {
          exact: true,
        })
        .last(),
    ).toBeVisible();

    await page
      .getByLabel("证据关系筛选")
      .getByRole("button", { name: /全部\s*3/ })
      .click();
    await page.setViewportSize({ width: 390, height: 844 });
    await captureVisual(page, "evidence-explorer-react-mobile-v1.png");
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
  });

  test("opens Capability Report and creates an explicitly scoped Case", async ({
    page,
  }) => {
    await page.goto("/commerce");
    await page.getByRole("button", { name: "更多", exact: true }).click();
    await page.getByRole("button", { name: "数据能力", exact: true }).click();

    await expect(
      page.getByRole("button", { name: "数据能力", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("button", { name: "案例队列", exact: true }),
    ).not.toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("button", { name: /履约延迟异常/ }),
    ).not.toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("heading", { name: "这批数据能分析什么", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("可直接分析", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByText("部分可分析", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByText("当前不可分析", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "刷新数据能力" }),
    ).not.toBeVisible();
    await expect(page.getByRole("button", { name: "刷新工作区" })).toHaveCount(
      1,
    );

    const refreshedDataset = page.waitForRequest((request) => {
      const url = new URL(request.url());
      return (
        request.method() === "GET" && url.pathname === "/api/commerce/datasets"
      );
    });
    await page.getByRole("button", { name: "刷新工作区" }).click();
    await refreshedDataset;
    await captureVisual(page, "capability-report-react-desktop-v1.png");
    await page
      .getByRole("button", { name: "创建案例", exact: true })
      .first()
      .click();
    await expect(
      page.getByRole("complementary", { name: "创建案例" }),
    ).toBeVisible();
    await expect(page.getByLabel(/履约诊断/)).toBeChecked();
    await captureVisual(page, "case-queue-react-create-v1.png");
    await page.getByLabel("经营主体（卖家编号）").fill("seller-4869");
    await page.getByLabel("基线开始").fill("2026-05-01T00:00");
    await page.getByLabel("基线结束").fill("2026-06-01T00:00");
    await page.getByLabel("当前开始").fill("2026-06-01T00:00");
    await page.getByLabel("当前结束").fill("2026-07-01T00:00");
    await page.getByRole("button", { name: "创建并打开案例" }).click();
    await expect(
      page.getByRole("heading", {
        name: "用户发起的履约诊断",
        exact: true,
      }),
    ).toBeVisible();
    await expect(page.getByLabel("继续询问当前案例")).toBeVisible();
  });

  test("reviews executes and rolls back an evidence-backed Action", async ({
    page,
  }) => {
    await page.goto("/commerce");
    await page.getByRole("button", { name: "行动中心", exact: true }).click();

    await expect(
      page.getByRole("heading", { name: "审查与执行行动", exact: true }),
    ).toBeVisible();
    await expect(page.getByLabel("继续询问当前案例")).not.toBeVisible();
    await expect(
      page
        .getByRole("heading", {
          name: "创建延迟履约率跟踪",
          exact: true,
        })
        .last(),
    ).toBeVisible();
    await expect(
      page.getByText("小于或等于 4.8%", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("允许执行", { exact: true })).toBeVisible();
    await captureVisual(page, "action-center-react-desktop-v1.png");

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByLabel("切换行动")).toBeVisible();
    await captureVisual(page, "action-center-react-mobile-v1.png");
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);

    await page.setViewportSize({ width: 1280, height: 720 });
    await page.getByRole("button", { name: "执行行动", exact: true }).click();
    await expect(
      page.getByText("行动已执行，并已创建可审计运行与执行产物。", {
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByText("跟踪中", { exact: true }).last(),
    ).toBeVisible();
    await page.getByRole("button", { name: "回滚行动", exact: true }).click();
    await expect(
      page.getByText("回滚已完成，执行产物已重新验证。", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("已回滚", { exact: true }).last(),
    ).toBeVisible();
  });

  test("inspects persisted fan-out telemetry and checkpoints without fake activity", async ({
    page,
  }) => {
    await page.goto("/commerce");
    await page.getByRole("button", { name: "更多", exact: true }).click();
    await page.getByRole("button", { name: "运行记录", exact: true }).click();

    await expect(
      page.getByRole("button", { name: "运行记录", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("heading", { name: "检查一次智能体运行", exact: true }),
    ).toBeVisible();
    await expect(page.getByLabel("继续询问当前案例")).not.toBeVisible();
    await expect(page.getByText("履约路径", { exact: true })).toBeVisible();
    await expect(page.getByText("卖家对标", { exact: true })).toBeVisible();
    await expect(page.getByText("评价体验", { exact: true })).toBeVisible();
    await expect(
      page.getByText("由全部路径终态与主智能体启动事件确认", {
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByText("deepseek-v4-flash", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("5 个唯一 ID", { exact: true })).toBeVisible();
    await expect(page.getByText("18,420", { exact: true })).toBeVisible();
    await expect(
      page.getByText("新鲜上下文验证", { exact: true }).last(),
    ).toBeVisible();
    await expect(
      page.getByText("上下文 SHA-256", { exact: true }),
    ).toBeVisible();
    await page.setViewportSize({ width: 1536, height: 1024 });
    await captureVisual(page, "agent-run-react-desktop-v1.png");

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByLabel("切换运行")).toBeVisible();
    await page.getByTestId("commerce-agent-run").evaluate((element) => {
      element.scrollIntoView({ block: "start" });
    });
    await captureVisual(page, "agent-run-react-mobile-v1.png");
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);

    await page.getByRole("button", { name: "查看事件流", exact: true }).click();
    await expect(
      page.getByText("独立验证已完成", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("12 条事件", { exact: false })).toBeVisible();
  });

  test("reviews promotes and rolls back an evidence-bound Skill Candidate", async ({
    page,
  }) => {
    await page.goto("/commerce");
    await page.getByRole("button", { name: "更多", exact: true }).click();
    await page.getByRole("button", { name: "技能与评测", exact: true }).click();

    await expect(
      page.getByRole("button", { name: "技能与评测", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("heading", { name: "治理技能演进", exact: true }),
    ).toBeVisible();
    await expect(page.getByLabel("继续询问当前案例")).not.toBeVisible();
    await expect(page.getByText("未建立指针", { exact: true })).toBeVisible();
    await expect(
      page.getByText("待人工审查", { exact: true }).last(),
    ).toBeVisible();
    await expect(page.getByText("8 / 8", { exact: true }).last()).toBeVisible();
    await expect(page.getByText("6 / 8", { exact: true })).toBeVisible();
    await expect(
      page.getByText("质量提升，令牌 -12.1%，延迟 -26.0%", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("请求遥测未由当前接口开放", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("运行中智能体不能修改生效技能", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "查看实验依据", exact: true })
      .click();
    await expect(
      page.getByText("32 个唯一请求编号", { exact: true }),
    ).toBeVisible();

    await page.setViewportSize({ width: 1536, height: 1024 });
    await page.getByTestId("commerce-skills-evals").evaluate((element) => {
      element.scrollIntoView({ block: "start" });
    });
    await captureVisual(page, "skills-evals-react-desktop-v1.png");

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByLabel("切换候选版本")).toBeVisible();
    await page.getByTestId("commerce-skills-evals").evaluate((element) => {
      element.scrollIntoView({ block: "start" });
    });
    await captureVisual(page, "skills-evals-react-mobile-v1.png");
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);

    await page.setViewportSize({ width: 1280, height: 720 });
    await page
      .getByRole("button", { name: "人工批准并激活", exact: true })
      .click();
    await expect(
      page.getByText("候选版本 1.3.0 已由人工审查者激活。", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("已生效", { exact: true }).last(),
    ).toBeVisible();

    await page
      .getByPlaceholder("说明为什么需要回退当前生效版本")
      .fill("新留出集出现回归");
    await page
      .getByRole("button", { name: "回滚生效版本", exact: true })
      .click();
    await expect(
      page.getByText("生效指针已回退至 1.2.0", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByText("已回滚", { exact: true }).last(),
    ).toBeVisible();
  });
});

async function mockCommerceReadAPI(
  page: Page,
  options: { initialDataset?: boolean } = {},
) {
  let hasDataset = options.initialDataset ?? false;
  let mappingConfirmed = false;
  let explicitCase: ReturnType<typeof commerceCase> | null = null;
  let actionStatus = "policy_checked";
  let actionArtifact: ReturnType<typeof commerceActionArtifact> | null = null;
  let skillStatus: "shadow" | "active" | "rolled_back" = "shadow";
  let skillReviewer: string | null = null;
  let skillRollbackReason: string | null = null;
  let activeSkillPointer: ReturnType<typeof commerceActiveSkillPointer> | null =
    null;
  await page.route("**/api/commerce/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    expect(request.headers()["x-commerce-workspace-id"]).toBe(WORKSPACE_ID);

    if (
      url.pathname === "/api/commerce/datasets" &&
      request.method() === "GET"
    ) {
      return json(route, {
        items: hasDataset ? [commerceDatasetListItem()] : [],
        limit: 100,
        offset: 0,
      });
    }
    if (
      url.pathname === "/api/commerce/datasets/intake" &&
      request.method() === "POST"
    ) {
      hasDataset = true;
      return json(route, commerceDatasetIntake(), 201);
    }
    if (
      url.pathname === `/api/commerce/datasets/${DATASET_ID}/mapping-resume` &&
      request.method() === "POST"
    ) {
      mappingConfirmed = true;
      return json(route, {
        confirmations: [
          {
            workspace_id: WORKSPACE_ID,
            table_name: "orders",
            column_name: "order_approved_at",
            semantic_field: "order.approved_at",
            confirmed_by: "commerce-operator",
            confirmed_at: "2026-07-20T02:35:00Z",
          },
        ],
        mappings: commerceDatasetMappings(false),
        capabilities: commerceDatasetCapabilities(),
        created: true,
        replayed: false,
      });
    }
    if (
      url.pathname === `/api/commerce/datasets/${DATASET_ID}` &&
      request.method() === "GET"
    ) {
      return json(route, commerceDatasetDetail(!mappingConfirmed));
    }
    if (
      url.pathname === `/api/commerce/datasets/${DATASET_ID}/cases` &&
      request.method() === "POST"
    ) {
      const body = request.postDataJSON();
      expect(body).toMatchObject({
        seller_id: "seller-4869",
        requested_paths: ["fulfillment"],
        peer_policy: null,
      });
      explicitCase = {
        ...commerceCase(CASE_EXPLICIT, "medium"),
        title: "User-requested investigation for seller seller-4869",
        status: "new",
        summary:
          "用户明确发起履约诊断；当前只创建案例，不把确定性指标写成异常或因果结论。",
        evidence_ids: [],
      };
      return json(
        route,
        {
          case: explicitCase,
          trigger: {
            trigger_type: "explicit_user_request",
            requested_paths: ["fulfillment"],
            peer_policy: null,
          },
          baseline_window: body.baseline_window,
          current_window: body.current_window,
        },
        201,
      );
    }

    if (url.pathname === "/api/commerce/cases") {
      return json(route, {
        items: [
          ...(explicitCase ? [explicitCase] : []),
          commerceCase(CASE_FULFILLMENT, "high"),
          commerceCase(CASE_REVIEW, "medium"),
        ],
        limit: 100,
        offset: 0,
      });
    }

    const caseActionMatch = /^\/api\/commerce\/cases\/([^/]+)\/actions$/u.exec(
      url.pathname,
    );
    if (caseActionMatch && request.method() === "GET") {
      return json(route, {
        items:
          caseActionMatch[1] === CASE_FULFILLMENT
            ? [commerceActionRecord(actionStatus)]
            : [],
      });
    }
    if (
      url.pathname === `/api/commerce/actions/${ACTION_ID}` &&
      request.method() === "GET"
    ) {
      return json(route, {
        record: commerceActionRecord(actionStatus),
        approval: null,
        artifact: actionArtifact,
        follow_ups: [],
      });
    }
    if (
      url.pathname === `/api/commerce/actions/${ACTION_ID}/executions` &&
      request.method() === "POST"
    ) {
      expect(request.headers()["x-commerce-actor-id"]).toBe(
        "commerce-operator",
      );
      const body = request.postDataJSON();
      expect(body.idempotency_key).toContain(ACTION_ID);
      if (body.operation === "execute") {
        actionStatus = "monitoring";
        actionArtifact = commerceActionArtifact("active");
      } else {
        actionStatus = "rolled_back";
        actionArtifact = commerceActionArtifact("disabled");
      }
      return json(
        route,
        {
          run: commerceActionRun(body.operation),
          record: commerceActionRecord(actionStatus),
          artifact: actionArtifact,
          created: true,
          replayed: false,
          error_message: null,
        },
        201,
      );
    }

    if (
      url.pathname === "/api/commerce/skill-candidates" &&
      request.method() === "GET"
    ) {
      return json(route, {
        items: [
          commerceSkillCandidate(
            skillStatus,
            skillReviewer,
            skillRollbackReason,
          ),
        ],
      });
    }
    if (
      url.pathname ===
        `/api/commerce/skill-candidates/${SKILL_CANDIDATE_ID}/evidence` &&
      request.method() === "GET"
    ) {
      return json(route, {
        candidate: commerceSkillCandidate(
          skillStatus,
          skillReviewer,
          skillRollbackReason,
        ),
        experiment_role: "offline_evaluation",
        definition: commerceSkillExperimentDefinition(),
        report: commerceSkillExperimentReport(),
        active_pointer: activeSkillPointer,
      });
    }
    if (
      url.pathname ===
        `/api/commerce/skill-candidates/${SKILL_CANDIDATE_ID}/promote` &&
      request.method() === "POST"
    ) {
      expect(request.headers()["x-commerce-actor-id"]).toBe(
        "commerce-operator",
      );
      skillStatus = "active";
      skillReviewer = "commerce-operator";
      activeSkillPointer = commerceActiveSkillPointer("active");
      return json(route, {
        candidate: commerceSkillCandidate(skillStatus, skillReviewer, null),
        active_pointer: activeSkillPointer,
        replayed: false,
      });
    }
    if (
      url.pathname ===
        "/api/commerce/skills/commerce-diagnostic-synthesis/rollback" &&
      request.method() === "POST"
    ) {
      expect(request.headers()["x-commerce-actor-id"]).toBe(
        "commerce-operator",
      );
      const body = request.postDataJSON();
      expect(body.reason).toBe("新留出集出现回归");
      skillStatus = "rolled_back";
      skillReviewer = "commerce-operator";
      skillRollbackReason = body.reason;
      activeSkillPointer = commerceActiveSkillPointer("rolled_back");
      return json(route, {
        candidate: commerceSkillCandidate(
          skillStatus,
          skillReviewer,
          skillRollbackReason,
        ),
        active_pointer: activeSkillPointer,
        replayed: false,
      });
    }

    if (
      url.pathname === `/api/commerce/runs/${RUN_ID}` &&
      request.method() === "GET"
    ) {
      return json(route, {
        run: commerceRun(CASE_FULFILLMENT, "fulfillment"),
        latest_checkpoint: commerceRunCheckpoint(),
      });
    }
    if (
      url.pathname === `/api/commerce/runs/${RUN_ID}/events` &&
      request.method() === "GET"
    ) {
      return json(route, { items: commerceAgentRunEvents() });
    }
    if (
      url.pathname === `/api/commerce/runs/${RUN_ID}/checkpoints` &&
      request.method() === "GET"
    ) {
      return json(route, { items: [commerceRunCheckpoint()] });
    }

    const caseId = url.pathname.split("/")[4];
    if (!caseId) return route.abort();

    if (url.pathname.endsWith("/events")) {
      return json(route, {
        items:
          caseId === CASE_REVIEW
            ? commerceEvents(caseId, "review_experience")
            : commerceEvents(caseId, "fulfillment"),
      });
    }
    if (url.pathname.endsWith("/runs")) {
      return json(route, {
        items: [
          commerceRun(
            caseId,
            caseId === CASE_REVIEW ? "review_experience" : "fulfillment",
          ),
        ],
        limit: 100,
        offset: 0,
      });
    }
    if (url.pathname === `/api/commerce/cases/${caseId}`) {
      return json(
        route,
        commerceDetail(
          caseId,
          explicitCase?.id === caseId ? explicitCase : undefined,
        ),
      );
    }
    return route.abort();
  });
}

const DATASET_ID = "dset_0123456789abcdef0123456789abcdef";

function commerceDatasetListItem() {
  return {
    dataset_id: DATASET_ID,
    workspace_id: WORKSPACE_ID,
    created_at: "2026-07-20T02:32:41Z",
    files: [
      {
        original_name: "orders.csv",
        format: "csv",
        size_bytes: 51,
        sha256: "a".repeat(64),
        archive_member: null,
      },
    ],
    checks: {
      file_count: 1,
      table_count: 1,
      row_count: 1,
      confirmed_mapping_count: 1,
      unresolved_mapping_count: 1,
      available_capability_count: 0,
      partial_capability_count: 0,
      unavailable_capability_count: 3,
    },
    integrity_status: "verified",
  };
}

function commerceDatasetIntake() {
  const detail = commerceDatasetDetail(true);
  return {
    manifest: detail.manifest,
    profile: detail.profile,
    mappings: detail.mappings,
    capabilities: detail.capabilities,
  };
}

function commerceDatasetDetail(pending: boolean) {
  return {
    manifest: {
      schema_version: "1.0",
      dataset_id: DATASET_ID,
      workspace_id: WORKSPACE_ID,
      created_at: "2026-07-20T02:32:41Z",
      storage_relative_path: `${WORKSPACE_ID}/${DATASET_ID}`,
      files: [
        {
          id: "src_0123456789abcdef0123456789abcdef",
          original_name: "orders.csv",
          stored_relative_path: "raw/orders.csv",
          format: "csv",
          size_bytes: 51,
          sha256: "a".repeat(64),
          encoding: "utf-8",
          read_only: true,
          parent_source_id: null,
          archive_member: null,
        },
      ],
      tables: [
        {
          table_name: "orders",
          source_file_id: "src_0123456789abcdef0123456789abcdef",
          format: "csv",
          sheet_name: null,
          json_key: null,
          archive_member: null,
        },
      ],
      warnings: [],
    },
    profile: {
      schema_version: "1.0",
      dataset_id: DATASET_ID,
      workspace_id: WORKSPACE_ID,
      tables: [
        {
          table_name: "orders",
          row_count: 1,
          column_count: 2,
          columns: [],
          duplicate_row_count: 0,
          duplicate_row_rate: 0,
          primary_key_candidates: [],
          time_candidates: [],
        },
      ],
      join_risks: [],
    },
    mappings: commerceDatasetMappings(pending),
    capabilities: commerceDatasetCapabilities(),
    confirmations: pending
      ? []
      : [
          {
            workspace_id: WORKSPACE_ID,
            table_name: "orders",
            column_name: "order_approved_at",
            semantic_field: "order.approved_at",
            confirmed_by: "commerce-operator",
            confirmed_at: "2026-07-20T02:35:00Z",
          },
        ],
    checks: {
      file_count: 1,
      table_count: 1,
      row_count: 1,
      confirmed_mapping_count: pending ? 1 : 2,
      unresolved_mapping_count: pending ? 1 : 0,
      available_capability_count: 0,
      partial_capability_count: 0,
      unavailable_capability_count: 3,
    },
    integrity_status: "verified",
  };
}

function commerceDatasetMappings(pending: boolean) {
  return {
    schema_version: "1.0",
    dataset_id: DATASET_ID,
    workspace_id: WORKSPACE_ID,
    mappings: [
      {
        table_name: "orders",
        column_name: "order_id",
        semantic_field: "order.id",
        confidence: 1,
        source: "deterministic_rule",
        status: "confirmed",
        reason: "deterministic",
      },
      {
        table_name: "orders",
        column_name: "order_approved_at",
        semantic_field: "order.approved_at",
        confidence: pending ? 0.75 : 1,
        source: pending ? "deterministic_rule" : "user_confirmed",
        status: pending ? "needs_confirmation" : "confirmed",
        reason: pending
          ? "ambiguous"
          : "Explicit workspace semantic confirmation",
      },
    ],
    unresolved_columns: pending ? ["orders.order_approved_at"] : [],
  };
}

function commerceDatasetCapabilities() {
  return {
    schema_version: "1.0",
    dataset_id: DATASET_ID,
    workspace_id: WORKSPACE_ID,
    capabilities: [
      {
        name: "fulfillment_diagnosis",
        path_agent: "FulfillmentPathAgent",
        status: "available",
        reason_codes: ["available"],
        available_fields: [
          "order.id",
          "order.approved_at",
          "order.delivered_at",
        ],
        missing_required_fields: [],
        missing_optional_fields: [],
        unmet_dependencies: [],
      },
      {
        name: "review_experience",
        path_agent: "ReviewExperiencePathAgent",
        status: "partial",
        reason_codes: ["missing_optional_semantics"],
        available_fields: ["review.score"],
        missing_required_fields: [],
        missing_optional_fields: ["review.comment"],
        unmet_dependencies: [],
      },
      {
        name: "seller_peer_comparison",
        path_agent: "SellerPeerPathAgent",
        status: "unavailable",
        reason_codes: ["insufficient_entity_diversity"],
        available_fields: ["seller.id"],
        missing_required_fields: [],
        missing_optional_fields: [],
        unmet_dependencies: [],
      },
    ],
  };
}

function commerceCase(id: string, severity: string) {
  const isReview = id === CASE_REVIEW;
  return {
    id,
    workspace_id: WORKSPACE_ID,
    title:
      id === CASE_REVIEW
        ? "User-requested investigation for seller review-0b90"
        : "Deterministic anomaly for seller fulfillment-4869",
    severity,
    status: isReview ? "awaiting_data" : "investigating",
    summary: isReview
      ? "评分下降已观察，缺少评价文本，当前结论范围受限。"
      : "延迟履约率显著上升，当前案例正在调查。",
    evidence_ids: isReview
      ? [EVIDENCE_PRIMARY]
      : [EVIDENCE_PRIMARY, EVIDENCE_CONTRADICT, EVIDENCE_CONTEXT],
    hypothesis_ids: ["hyp_0123456789abcdef0123456789abcdef"],
    action_ids:
      id === CASE_REVIEW ? [] : ["act_0123456789abcdef0123456789abcdef"],
    opened_at: "2026-07-20T02:32:41Z",
    updated_at:
      id === CASE_REVIEW ? "2026-07-20T02:33:00Z" : "2026-07-20T02:34:00Z",
    version: 2,
  };
}

function commerceDetail(
  caseId: string,
  caseOverride?: ReturnType<typeof commerceCase>,
) {
  const isReview = caseId === CASE_REVIEW;
  const isExplicit = Boolean(caseOverride);
  const baselineMetricId = isReview
    ? "mobs_1123456789abcdef0123456789abcde1"
    : "mobs_0123456789abcdef0123456789abcde1";
  const currentMetricId = isReview
    ? "mobs_1123456789abcdef0123456789abcde2"
    : "mobs_0123456789abcdef0123456789abcde2";
  return {
    case: caseOverride ?? commerceCase(caseId, isReview ? "medium" : "high"),
    lineage: {
      schema_version: "1.0.0",
      workspace_id: WORKSPACE_ID,
      case_id: caseId,
      dataset_id: "dset_0123456789abcdef0123456789abcdef",
      seller_entity_id: "ent_0123456789abcdef0123456789abcdef",
      seller_external_key: isReview ? "seller-0b90" : "seller-4869",
      baseline_start: "2026-05-01T00:00:00Z",
      baseline_end: "2026-05-07T23:59:59Z",
      current_start: "2026-05-08T00:00:00Z",
      current_end: "2026-05-14T23:59:59Z",
      anomaly_ids: ["anom_0123456789abcdef0123456789abcdef"],
      metric_observation_ids: [baselineMetricId, currentMetricId],
      analysis_artifact_relative_path: "analysis/case.json",
      analysis_artifact_sha256: "a".repeat(64),
      created_at: "2026-07-20T02:32:41Z",
    },
    evidence: isExplicit
      ? []
      : [
          {
            id: EVIDENCE_PRIMARY,
            workspace_id: WORKSPACE_ID,
            case_id: caseId,
            summary: isReview
              ? "Customers reported product experience concerns."
              : "Late delivery rate increased by 31.6 percentage points.",
            relation: "supports",
            semantic_status: "observed",
            confidence: 0.96,
            fact_ids: isReview ? ["fact_0123456789abcdef0123456789abcdef"] : [],
            metric_observation_ids: [baselineMetricId, currentMetricId],
          },
          ...(!isReview
            ? [
                {
                  id: EVIDENCE_CONTRADICT,
                  workspace_id: WORKSPACE_ID,
                  case_id: caseId,
                  summary: "Handling time did not worsen with delivery delay.",
                  relation: "contradicts",
                  semantic_status: "derived",
                  confidence: 0.93,
                  fact_ids: [],
                  metric_observation_ids: [HANDLING_BASELINE, HANDLING_CURRENT],
                },
                {
                  id: EVIDENCE_CONTEXT,
                  workspace_id: WORKSPACE_ID,
                  case_id: caseId,
                  summary: "Advertising spend and profit are not available.",
                  relation: "context",
                  semantic_status: "unknown",
                  confidence: 0.5,
                  fact_ids: ["fact_0123456789abcdef0123456789abcdef"],
                  metric_observation_ids: [],
                },
              ]
            : []),
        ],
    hypotheses:
      isReview || isExplicit
        ? []
        : [
            {
              id: "hyp_0123456789abcdef0123456789abcdef",
              workspace_id: WORKSPACE_ID,
              case_id: caseId,
              statement: "承运运输阶段可能与履约延迟有关。",
              status: "investigating",
              confidence: 0.74,
              supporting_evidence_ids: [EVIDENCE_PRIMARY],
              contradicting_evidence_ids: [EVIDENCE_CONTRADICT],
              version: 1,
            },
          ],
    analysis: isExplicit
      ? {
          ...commerceAnalysis(false, baselineMetricId, currentMetricId),
          anomalies: [],
        }
      : commerceAnalysis(isReview, baselineMetricId, currentMetricId),
    actions:
      isReview || isExplicit
        ? []
        : [
            {
              id: "act_0123456789abcdef0123456789abcdef",
              title: "Review carrier service levels and late orders",
              description: "Create a bounded internal review task.",
              kind: "create_internal_task",
              status: "policy_checked",
              risk_level: "low",
              policy_level: "auto_allowed",
              approval_required: false,
              approval_status: "not_required",
              evidence_ids: ["evd_0123456789abcdef0123456789abcdef"],
              created_at: "2026-07-20T02:33:20Z",
              updated_at: "2026-07-20T02:33:20Z",
              version: 1,
            },
          ],
  };
}

function commerceAnalysis(
  isReview: boolean,
  baselineMetricId: string,
  currentMetricId: string,
) {
  const metricName = isReview ? "average_review_score" : "late_delivery_rate";
  const unit = isReview ? "score" : "ratio";
  const baselineValue = isReview ? "4.6" : "0.048";
  const currentValue = isReview ? "3.8" : "0.364";
  const absoluteChange = isReview ? "-0.8" : "0.316";
  return {
    status: "available",
    unavailable_reason: null,
    baseline_metrics: [
      metric(
        baselineMetricId,
        metricName,
        baselineValue,
        unit,
        "2026-05-01T00:00:00Z",
        "2026-05-08T00:00:00Z",
      ),
      ...(!isReview
        ? [
            metric(
              HANDLING_BASELINE,
              "handling_time_hours",
              "8.1",
              "hours",
              "2026-05-01T00:00:00Z",
              "2026-05-08T00:00:00Z",
            ),
          ]
        : []),
    ],
    current_metrics: [
      metric(
        currentMetricId,
        metricName,
        currentValue,
        unit,
        "2026-05-08T00:00:00Z",
        "2026-05-15T00:00:00Z",
      ),
      ...(!isReview
        ? [
            metric(
              HANDLING_CURRENT,
              "handling_time_hours",
              "8.2",
              "hours",
              "2026-05-08T00:00:00Z",
              "2026-05-15T00:00:00Z",
            ),
          ]
        : []),
    ],
    anomalies: [
      {
        id: "anom_0123456789abcdef0123456789abcdef",
        metric_name: metricName,
        baseline_observation_id: baselineMetricId,
        current_observation_id: currentMetricId,
        baseline_value: baselineValue,
        current_value: currentValue,
        absolute_change: absoluteChange,
        relative_change: isReview ? "-0.1739" : "6.5833",
        direction: isReview ? "decrease" : "increase",
        severity: isReview ? "medium" : "high",
        confidence: 0.96,
        baseline_sample_size: 125,
        current_sample_size: 132,
        sample_adequate: true,
        reason: "Deterministic threshold crossed.",
      },
    ],
  };
}

function metric(
  id: string,
  metricName: string,
  value: string,
  unit: string,
  start: string,
  end: string,
) {
  return {
    id,
    metric_name: metricName,
    semantic_status: "derived",
    value,
    unit,
    formula_version: `${metricName}@1.0.0`,
    window_start: start,
    window_end: end,
    sample_size: 100,
    numerator: null,
    denominator: null,
    source_fact_count: 100,
    unknown_reason: null,
  };
}

function commerceEvents(caseId: string, pathType: string) {
  return [
    event(caseId, 1, "case.created", {}),
    event(caseId, 2, "run.created", {
      status: "queued",
      requested_paths: [pathType],
    }),
    event(caseId, 3, "path.started", { path_type: pathType }),
    event(caseId, 4, "path.completed", { path_type: pathType }),
    event(caseId, 5, "lead.started", {}),
    event(caseId, 6, "lead.completed", {}),
    event(caseId, 7, "verification.completed", {
      actual_model_identity: "deepseek-v4-flash",
      retry_count: 0,
    }),
    event(caseId, 8, "run.lease_released", {}),
  ];
}

function commerceAgentRunEvents() {
  return [
    event(CASE_FULFILLMENT, 1, "run.created", {}),
    event(CASE_FULFILLMENT, 2, "path.started", {
      path_type: "fulfillment",
    }),
    event(CASE_FULFILLMENT, 3, "path.started", {
      path_type: "seller_peer",
    }),
    event(CASE_FULFILLMENT, 4, "path.started", {
      path_type: "review_experience",
    }),
    event(
      CASE_FULFILLMENT,
      5,
      "path.completed",
      modelTelemetry("req-path-a", 4200, 3100, {
        path_type: "fulfillment",
        evidence_ids: [EVIDENCE_PRIMARY, EVIDENCE_CONTRADICT],
        provider_request_ids: ["req-path-a"],
      }),
    ),
    event(
      CASE_FULFILLMENT,
      6,
      "path.completed",
      modelTelemetry("req-path-b", 3600, 2600, {
        path_type: "seller_peer",
        evidence_ids: [EVIDENCE_CONTEXT],
        provider_request_ids: ["req-path-b"],
      }),
    ),
    event(
      CASE_FULFILLMENT,
      7,
      "path.completed",
      modelTelemetry("req-path-c", 3200, 2200, {
        path_type: "review_experience",
        evidence_ids: ["evd_3123456789abcdef0123456789abcdef"],
        provider_request_ids: ["req-path-c"],
      }),
    ),
    event(CASE_FULFILLMENT, 8, "lead.started", {}),
    event(
      CASE_FULFILLMENT,
      9,
      "lead.completed",
      modelTelemetry("req-lead", 4400, 3000, {
        provider_request_ids: ["req-lead"],
        model_call_count: 1,
        claim_count: 1,
      }),
    ),
    event(CASE_FULFILLMENT, 10, "verification.started", {}),
    event(
      CASE_FULFILLMENT,
      11,
      "verification.completed",
      modelTelemetry("req-verify", 3020, 1700, { accepted: true }),
    ),
    event(CASE_FULFILLMENT, 12, "run.lease_released", {}),
  ];
}

function modelTelemetry(
  requestId: string,
  totalTokens: number,
  latencyMs: number,
  extra: Record<string, unknown>,
) {
  return {
    provider_request_id: requestId,
    actual_model_identity: "deepseek-v4-flash",
    total_tokens: totalTokens,
    latency_ms: latencyMs,
    retry_count: 0,
    stop_reason: "stop",
    ...extra,
  };
}

function event(
  caseId: string,
  sequence: number,
  eventType: string,
  payload: Record<string, unknown>,
) {
  const suffix = String(sequence).padStart(32, "0");
  return {
    id: `evt_${suffix}`,
    workspace_id: WORKSPACE_ID,
    case_id: caseId,
    run_id: runIdForCase(caseId),
    event_type: eventType,
    schema_version: "1.0.0",
    case_sequence: sequence,
    run_sequence: sequence,
    occurred_at: `2026-07-20T02:33:${String(sequence).padStart(2, "0")}Z`,
    recorded_at: `2026-07-20T02:33:${String(sequence).padStart(2, "0")}Z`,
    trace_id: "trace_0123456789abcdef0123456789abcdef",
    correlation_id: "corr_0123456789abcdef0123456789abcdef",
    causation_event_id: null,
    actor: "system",
    payload,
  };
}

function commerceRun(caseId: string, pathType: string) {
  return {
    id: runIdForCase(caseId),
    workspace_id: WORKSPACE_ID,
    case_id: caseId,
    run_type: "case_investigation",
    status: "completed",
    phase: "terminal",
    goal:
      caseId === CASE_FULFILLMENT
        ? "Explain the fulfillment delay with traceable evidence"
        : "Investigate the review experience anomaly.",
    parent_run_id: null,
    subject_action_id: null,
    action_operation: null,
    requested_paths:
      caseId === CASE_FULFILLMENT
        ? ["fulfillment", "seller_peer", "review_experience"]
        : [pathType],
    wait_reason: null,
    stop_reason: "goal_achieved",
    created_at: "2026-07-20T02:32:45Z",
    started_at: "2026-07-20T02:33:10Z",
    ended_at: "2026-07-20T02:33:22.600Z",
    updated_at: "2026-07-20T02:33:22.600Z",
    version: 3,
  };
}

function runIdForCase(caseId: string) {
  if (caseId === CASE_REVIEW) {
    return "run_1123456789abcdef0123456789abcdef";
  }
  if (caseId === CASE_EXPLICIT) {
    return "run_2123456789abcdef0123456789abcdef";
  }
  return RUN_ID;
}

function commerceRunCheckpoint() {
  return {
    id: "chk_0123456789abcdef0123456789abcdef",
    sequence: 7,
    checkpoint: {
      schema_version: "commerce.goal-loop-checkpoint@1.0.0",
      workspace_id: WORKSPACE_ID,
      run_id: RUN_ID,
      case_id: CASE_FULFILLMENT,
      goal: "Explain the fulfillment delay with traceable evidence",
      loop_iteration: 1,
      budget_snapshot: {
        limit: {
          max_iterations: 8,
          max_tool_calls: 20,
          max_path_agents: 3,
          max_tokens: 32000,
          max_wall_time_seconds: 300,
          max_model_escalations: 1,
          max_verification_repairs: 2,
          max_repeated_actions: 2,
          max_consecutive_no_new_evidence: 2,
        },
        usage: {
          iterations: 1,
          tool_calls: 6,
          path_agents: 3,
          tokens: 18420,
          wall_time_seconds: 12.6,
          model_escalations: 0,
          verification_repairs: 0,
          repeated_actions: 0,
          consecutive_no_new_evidence: 0,
        },
      },
      evidence_ids: [
        EVIDENCE_PRIMARY,
        EVIDENCE_CONTRADICT,
        EVIDENCE_CONTEXT,
        "evd_3123456789abcdef0123456789abcdef",
      ],
      hypothesis_ids: ["hyp_0123456789abcdef0123456789abcdef"],
      active_path_task_ids: [],
      model_assignments: [],
      skill_versions: [
        { skill_id: "commerce.lead-synthesis", version: "1.0.0" },
      ],
      context_sha256: "a".repeat(64),
      tool_state: [],
      wait_reason: null,
      resume_token_sha256: null,
    },
    created_at: "2026-07-20T02:33:22.600Z",
  };
}

function commerceSkillCandidate(
  status: "shadow" | "active" | "rolled_back",
  reviewerId: string | null,
  rollbackReason: string | null,
) {
  return {
    schema_version: "commerce.skill-candidate@1.0.0",
    id: SKILL_CANDIDATE_ID,
    skill_name: "commerce-diagnostic-synthesis",
    base_version: "1.2.0",
    candidate_version: "1.3.0",
    content:
      "Never invent numeric action thresholds; use configured server policy only.",
    content_sha256:
      "f46d8884d6ffba670f9c3d9299d702f9c9fdd477e759dbcaaabcc4450dc6b228",
    source_failure_codes: ["unsupported-action-threshold"],
    security_scan: {
      passed: true,
      findings: [],
      scanner_version: "commerce-skill-security@1.0.0",
    },
    proposed_by: "skill-evolution-runner",
    status,
    source_experiment_id: "exp_1123456789abcdef0123456789abcdef",
    source_experiment_decision: "promote_candidate",
    experiment_id: "exp_0123456789abcdef0123456789abcdef",
    experiment_decision: "promote_candidate",
    regression_passed: true,
    holdout_passed: true,
    shadow_passed: true,
    shadow_live_run_ids: [
      "run_9123456789abcdef0123456789abcdef",
      "run_a123456789abcdef0123456789abcdef",
    ],
    reviewer_id: reviewerId,
    rollback_reason: rollbackReason,
    created_at: "2026-07-19T10:00:00Z",
    updated_at:
      status === "shadow" ? "2026-07-19T10:30:00Z" : "2026-07-19T10:40:00Z",
    version: status === "shadow" ? 3 : status === "active" ? 4 : 5,
  };
}

function commerceSkillExperimentDefinition() {
  return {
    schema_version: "commerce.experiment@1.0.0",
    id: "exp_0123456789abcdef0123456789abcdef",
    title: "Four-Gold threshold hardening",
    hypothesis: "Candidate improves safety and Pareto efficiency.",
    control: {
      name: "control",
      prompt_version: "prompt@1.0.0",
      context_version: "gold-case@1.0.0",
      router_version: "router@1.0.0",
      skill_version: "commerce-diagnostic-synthesis@1.2.0",
      skill_content_sha256: "a".repeat(64),
    },
    candidate: {
      name: "candidate",
      prompt_version: "prompt@1.0.0",
      context_version: "gold-case@1.0.0",
      router_version: "router@1.0.0",
      skill_version: "commerce-diagnostic-synthesis@1.3.0-candidate",
      skill_content_sha256:
        "f46d8884d6ffba670f9c3d9299d702f9c9fdd477e759dbcaaabcc4450dc6b228",
    },
    case_keys: [
      "GC-FULFILLMENT-001",
      "GC-REVIEW-002",
      "GC-CAPABILITY-003",
      "GC-PEER-004",
    ],
    repetitions: 2,
    controlled_variables: ["model=deepseek-v4"],
    reproduction_command: "python -m app.commerce.evaluation.run_experiment",
    created_at: "2026-07-19T10:05:00Z",
  };
}

function commerceSkillExperimentReport() {
  return {
    schema_version: "commerce.experiment-report@1.0.0",
    experiment_id: "exp_0123456789abcdef0123456789abcdef",
    control: {
      variant_name: "control",
      run_count: 8,
      passed_count: 6,
      hard_gate_failures: 2,
      pass_rate: 0.75,
      mean_total_tokens: 2334.625,
      mean_latency_ms: 5691.85,
    },
    candidate: {
      variant_name: "candidate",
      run_count: 8,
      passed_count: 8,
      hard_gate_failures: 0,
      pass_rate: 1,
      mean_total_tokens: 2051.875,
      mean_latency_ms: 4212.11,
    },
    decision: "promote_candidate",
    reasons: [
      "Candidate passes all hard gates and improves the Pareto frontier",
    ],
    provider_request_ids: Array.from(
      { length: 32 },
      (_, index) => `req-experiment-${index}`,
    ),
    created_at: "2026-07-19T10:20:00Z",
  };
}

function commerceActiveSkillPointer(status: "active" | "rolled_back") {
  return {
    schema_version: "commerce.active-skill-pointer@1.0.0",
    skill_name: "commerce-diagnostic-synthesis",
    version: status === "active" ? "1.3.0" : "1.2.0",
    candidate_id: status === "active" ? SKILL_CANDIDATE_ID : null,
    previous_version: "1.2.0",
    reviewer_id: "commerce-operator",
    rolled_back_candidate_id:
      status === "rolled_back" ? SKILL_CANDIDATE_ID : null,
    rollback_reviewer_id: status === "rolled_back" ? "commerce-operator" : null,
    rollback_reason: status === "rolled_back" ? "新留出集出现回归" : null,
  };
}

function commerceActionRecord(status: string) {
  const rollbackPlan = {
    strategy: "停用本次指标跟踪",
    trigger: "发现配置错误或监控对象不一致时",
    verification: "确认跟踪任务已停用且不再产生新检查记录",
  };
  const action = {
    id: ACTION_ID,
    workspace_id: WORKSPACE_ID,
    case_id: CASE_FULFILLMENT,
    title: "Monitor late-delivery recovery",
    description: "Create a reversible internal metric monitor.",
    status,
    evidence_ids: [EVIDENCE_PRIMARY, EVIDENCE_CONTRADICT],
    risk_level: "medium",
    approval: {
      required: false,
      status: "not_required",
      approval_id: null,
      reason: "Internal reversible Action is below the approval threshold",
    },
    rollback_plan: rollbackPlan,
  };
  return {
    action,
    decision: {
      schema_version: "commerce.action-policy-decision@1.0.0",
      validated: {
        schema_version: "commerce.validated-action@1.0.0",
        draft: {
          schema_version: "commerce.action-draft@1.0.0",
          id: ACTION_ID,
          workspace_id: WORKSPACE_ID,
          case_id: CASE_FULFILLMENT,
          title: action.title,
          description: action.description,
          evidence_ids: action.evidence_ids,
          hypothesis_ids: ["hyp_0123456789abcdef0123456789abcdef"],
          expected_signal_metric_ids: ["mobs_0123456789abcdef0123456789abcde2"],
          parameters: {
            kind: "create_metric_monitor",
            metric_name: "late_delivery_rate",
            metric_observation_ids: ["mobs_0123456789abcdef0123456789abcde2"],
            comparison: "less_than_or_equal",
            threshold: "0.048",
            cadence_hours: 24,
            follow_up_after_days: 7,
          },
          rollback_plan: rollbackPlan,
        },
        validation_sha256: "a".repeat(64),
      },
      level: "L2",
      disposition: "auto_execute",
      reason_codes: ["reversible_internal_operation"],
      required_approvals: 0,
      execution_tool: "internal_metric_monitor.create",
      action,
    },
    created_at: "2026-07-20T02:33:20Z",
    updated_at: "2026-07-20T02:42:20Z",
    version: status === "policy_checked" ? 1 : 2,
  };
}

function commerceActionArtifact(status: "active" | "disabled" = "active") {
  return {
    schema_version: "commerce.action-execution-artifact@1.0.0",
    workspace_id: WORKSPACE_ID,
    case_id: CASE_FULFILLMENT,
    action_id: ACTION_ID,
    execution_tool: "internal_metric_monitor.create",
    payload: {
      kind: "metric_monitor",
      metric_name: "late_delivery_rate",
      metric_observation_ids: ["mobs_0123456789abcdef0123456789abcde2"],
      comparison: "less_than_or_equal",
      threshold: "0.048",
      cadence_hours: 24,
      follow_up_after_days: 7,
      next_evaluation_at: "2026-07-27T02:42:43Z",
    },
    status,
    execution_input_sha256: "b".repeat(64),
    verification_sha256: "c".repeat(64),
    created_at: "2026-07-20T02:42:43Z",
    updated_at: "2026-07-20T02:42:43Z",
    version: status === "active" ? 1 : 2,
  };
}

function commerceActionRun(operation: "execute" | "rollback") {
  return {
    id: "run_2123456789abcdef0123456789abcdef",
    workspace_id: WORKSPACE_ID,
    case_id: CASE_FULFILLMENT,
    run_type: "action_execution",
    status: "completed",
    phase: "executing",
    goal: operation === "execute" ? "Execute Action" : "Rollback Action",
    parent_run_id: null,
    subject_action_id: ACTION_ID,
    action_operation: operation,
    requested_paths: [],
    wait_reason: null,
    stop_reason:
      operation === "execute"
        ? "action_execution_verified"
        : "action_rollback_verified",
    created_at: "2026-07-20T02:42:41Z",
    started_at: "2026-07-20T02:42:42Z",
    ended_at: "2026-07-20T02:42:43Z",
    updated_at: "2026-07-20T02:42:43Z",
    version: 3,
  };
}

function json(
  route: Parameters<Parameters<Page["route"]>[1]>[0],
  body: unknown,
  status = 200,
) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function captureVisual(page: Page, filename: string) {
  if (process.env.COMMERCE_CAPTURE_VISUALS !== "1") return;
  await page.screenshot({
    path: resolve(
      process.cwd(),
      "../docs/design/commerce/implementation",
      filename,
    ),
    fullPage: false,
  });
}
