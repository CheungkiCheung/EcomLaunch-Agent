import { expect, test, type Page } from "@playwright/test";

import { handleRunStream, mockLangGraphAPI } from "./utils/mock-api";

const LAUNCH_THREAD_ID = "00000000-0000-0000-0000-000000004201";
const GROWTH_THREAD_ID = "00000000-0000-0000-0000-000000004202";
const ARTIFACT_PREFIX = "/mnt/user-data/outputs/";

const launchSpec = {
  category: "通勤咖啡杯",
  target_price: "99-199 元",
  decision: "test_after_fixing_assumptions",
  decision_rationale:
    "清洁痛点已有公开信号，但目标价格接受度仍待真实用户验证。",
  audience: "每天通勤且自带咖啡的城市用户",
  validation_goal: "验证清洁痛点优先级与 99-199 元价格接受度",
  hypotheses: ["目标用户愿意为更易清洁的方案支付 99-199 元"],
  evidence: [
    {
      claim: "公开评论反复提到杯盖清洁困难",
      evidence_label: "observed_public",
      source_urls: ["https://example.com/reviews/cleaning"],
    },
    {
      claim: "目标价格仍是假设",
      evidence_label: "assumption",
      source_urls: [],
    },
  ],
  experiments: [
    {
      day: "1",
      action: "价格接受度测试",
      evidence_to_collect: "价格选择、拒绝理由与购买时机",
      success_criterion: "预算理由与目标价格存在交集",
      stop_condition: "目标价格持续被明确拒绝",
    },
  ],
};

const launchMessages = [
  {
    type: "human",
    id: "launch-human",
    content: "判断 99-199 元通勤咖啡杯是否值得做",
  },
  {
    type: "ai",
    id: "launch-render",
    content: "",
    tool_calls: [
      {
        id: "launch-render-call",
        name: "render_launch_pack",
        args: { spec: launchSpec },
      },
    ],
  },
  {
    type: "tool",
    id: "launch-render-result",
    name: "render_launch_pack",
    tool_call_id: "launch-render-call",
    content: "Successfully presented files",
    additional_kwargs: {
      artifacts: [
        `${ARTIFACT_PREFIX}launch-war-room.html`,
        `${ARTIFACT_PREFIX}evidence-ledger.json`,
        `${ARTIFACT_PREFIX}competitor-table.csv`,
        `${ARTIFACT_PREFIX}positioning-brief.md`,
        `${ARTIFACT_PREFIX}listing-pack.md`,
        `${ARTIFACT_PREFIX}content-pack.md`,
        `${ARTIFACT_PREFIX}launch-calendar.csv`,
      ],
    },
  },
  {
    type: "ai",
    id: "launch-final",
    content: "建议先验证价格假设，再决定是否进入样品阶段。",
  },
];

async function useChinese(page: Page, baseURL: string) {
  await page
    .context()
    .addCookies([{ name: "locale", value: "zh-CN", url: baseURL }]);
}

function mockLaunchArtifacts(page: Page) {
  void page.route("**/api/threads/*/artifacts/**", (route) => {
    const url = route.request().url();
    if (url.endsWith("evidence-ledger.json")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          metadata: { decision: launchSpec.decision },
          entries: launchSpec.evidence,
        }),
      });
    }
    if (url.endsWith("launch-calendar.csv")) {
      return route.fulfill({
        status: 200,
        contentType: "text/csv",
        body: [
          "day,action,evidence_to_collect,success_criterion,stop_condition",
          "1,价格接受度测试,价格选择与理由,预算与目标价格有交集,目标价格持续被拒绝",
        ].join("\n"),
      });
    }
    return route.fulfill({ status: 404, body: "Not found" });
  });
}

test.describe("OpenSKU decision workspace", () => {
  test("shows the real decision contract and sends a structured validation result", async ({
    page,
    baseURL,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: LAUNCH_THREAD_ID,
          title: "通勤咖啡杯验证",
          agent_name: "ecom-launch",
          messages: launchMessages,
        },
      ],
    });
    mockLaunchArtifacts(page);
    let submittedBody = "";
    await page.route("**/threads/*/runs/stream", async (route) => {
      submittedBody = route.request().postData() ?? "";
      return handleRunStream(route);
    });
    await useChinese(page, baseURL!);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/workspace/agents/ecom-launch/chats/${LAUNCH_THREAD_ID}`);

    await page.getByRole("button", { name: "决策", exact: true }).click();
    const workspace = page.getByTestId("launch-decision-workspace");
    await expect(workspace).toBeVisible();
    await expect(workspace.getByText("通勤咖啡杯 验证决策")).toBeVisible();
    await expect(
      workspace.getByText("补齐关键假设后再验证", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      workspace.getByText("部分支持", { exact: true }),
    ).toBeVisible();
    await expect(workspace.getByText("目标价格持续被拒绝")).toBeVisible();

    await workspace.getByRole("tab", { name: "实验", exact: true }).click();
    await expect(
      workspace.getByText("价格接受度测试", { exact: true }).first(),
    ).toBeVisible();
    await workspace
      .getByRole("button", { name: "记录验证结果" })
      .first()
      .click();
    await page
      .getByRole("textbox", { name: "实验", exact: true })
      .fill("价格接受度测试");
    await page.getByLabel("样本口径").fill("12 名有通勤场景的目标用户");
    await page
      .getByLabel("观察结果")
      .fill("8 人认为 159 元以上需要更明确的清洁收益证明");
    await page.getByRole("button", { name: "提交并复核" }).click();

    await expect
      .poll(() => submittedBody)
      .toContain("OPENSKU_VALIDATION_RESULT_V1");
    expect(submittedBody).toContain("12 名有通勤场景的目标用户");
    expect(submittedBody).toContain("inconclusive");
  });

  test("performs an explicit Launch Team to Growth Analyst handoff", async ({
    page,
    baseURL,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: LAUNCH_THREAD_ID,
          title: "通勤咖啡杯验证",
          agent_name: "ecom-launch",
          messages: launchMessages,
        },
      ],
    });
    mockLaunchArtifacts(page);
    await useChinese(page, baseURL!);
    await page.goto(`/workspace/agents/ecom-launch/chats/${LAUNCH_THREAD_ID}`);
    await page.getByRole("button", { name: "决策", exact: true }).click();
    await page.getByRole("button", { name: "前往 Growth Analyst" }).click();

    await expect(page).toHaveURL(
      /\/workspace\/agents\/data-inspector\/chats\/new/,
    );
    const composer = page.locator("textarea").first();
    await expect(composer).toContainText("OPENSKU_GROWTH_HANDOFF_V1");
    await expect(composer).toContainText("通勤咖啡杯");
    await expect(composer).toContainText("请先让我上传 CSV/XLSX");
    await page.getByRole("button", { name: "Submit" }).click();
    await expect(page).toHaveURL(
      new RegExp("/workspace/agents/data-inspector/chats/[^?]+$"),
    );
    await expect(
      page.getByRole("button", { name: "用于更新 Launch 决策" }),
    ).toBeVisible();
  });

  test("returns Growth Analyst findings to the source Launch decision", async ({
    page,
    baseURL,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: GROWTH_THREAD_ID,
          title: "价格实验分析",
          agent_name: "data-inspector",
          messages: [
            {
              type: "human",
              id: "growth-human",
              content: "分析上传的价格测试",
            },
            {
              type: "ai",
              id: "growth-final",
              content:
                "12 个有效样本中，159 元以上选择减少；样本量小且来自单一渠道，不能外推整体市场。",
            },
          ],
        },
        {
          thread_id: LAUNCH_THREAD_ID,
          title: "通勤咖啡杯验证",
          agent_name: "ecom-launch",
          messages: launchMessages,
        },
      ],
    });
    mockLaunchArtifacts(page);
    await useChinese(page, baseURL!);
    await page.goto(
      `/workspace/agents/data-inspector/chats/${GROWTH_THREAD_ID}?sourceThread=${LAUNCH_THREAD_ID}`,
    );

    await page.getByRole("button", { name: "用于更新 Launch 决策" }).click();
    await expect(page).toHaveURL(
      new RegExp(`/workspace/agents/ecom-launch/chats/${LAUNCH_THREAD_ID}`),
    );
    const composer = page.locator("textarea").first();
    await expect(composer).toContainText("OPENSKU_GROWTH_RETURN_V1");
    await expect(composer).toContainText("样本量小且来自单一渠道");
    await expect(composer).toContainText("作为新证据审查");
  });
});
