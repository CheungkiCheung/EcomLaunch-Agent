import type { Message } from "@langchain/langgraph-sdk";
import { describe, expect, test } from "vitest";

import {
  buildDecisionWorkspaceModel,
  buildGrowthAnalystHandoff,
  extractLaunchSpecs,
  formatValidationResultMessage,
  parseEvidenceLedger,
  parseLaunchCalendar,
} from "@/core/launch-validation/decision";

function renderMessages(spec: Record<string, unknown>): Message[] {
  const toolCallId = crypto.randomUUID();
  return [
    {
      type: "ai",
      id: crypto.randomUUID(),
      content: "",
      tool_calls: [
        {
          id: toolCallId,
          name: "render_launch_pack",
          args: { spec },
        },
      ],
    },
    {
      type: "tool",
      id: crypto.randomUUID(),
      name: "render_launch_pack",
      tool_call_id: toolCallId,
      content: "Successfully presented files",
    },
  ];
}

describe("launch decision contract", () => {
  test("extracts only valid Launch Pack specs and keeps first/current decisions", () => {
    const messages: Message[] = [
      ...renderMessages({ category: "通勤咖啡杯", decision: "test_now" }),
      {
        type: "ai",
        id: "unrelated",
        content: "",
        tool_calls: [{ id: "x", name: "web_search", args: {} }],
      },
      ...renderMessages({
        category: "通勤咖啡杯",
        decision: "test_after_fixing_assumptions",
        decision_rationale: "价格接受度仍有分歧",
      }),
    ];

    const specs = extractLaunchSpecs(messages);
    expect(specs).toHaveLength(2);
    expect(specs[0]?.decision).toBe("test_now");
    expect(specs[1]?.decision).toBe("test_after_fixing_assumptions");

    const model = buildDecisionWorkspaceModel({ messages });
    expect(model.decisionChanged).toBe(true);
    expect(model.currentSpec?.decisionRationale).toBe("价格接受度仍有分歧");
  });

  test("ignores an unfinished or failed Launch Pack render", () => {
    const toolCallId = "failed-render";
    const messages: Message[] = [
      {
        type: "ai",
        id: "failed-ai",
        content: "",
        tool_calls: [
          {
            id: toolCallId,
            name: "render_launch_pack",
            args: { spec: { category: "通勤咖啡杯", decision: "test_now" } },
          },
        ],
      },
      {
        type: "tool",
        id: "failed-tool",
        name: "render_launch_pack",
        tool_call_id: toolCallId,
        content: "Error: deterministic preflight failed",
      },
    ];

    expect(extractLaunchSpecs(messages)).toEqual([]);
    expect(
      extractLaunchSpecs([
        {
          type: "ai",
          id: "pending-ai",
          content: "",
          tool_calls: [
            {
              id: "pending-render",
              name: "render_launch_pack",
              args: { spec: { category: "通勤咖啡杯" } },
            },
          ],
        },
      ]),
    ).toEqual([]);
  });

  test("parses renderer ledger and quoted calendar fields", () => {
    const evidence = parseEvidenceLedger(
      JSON.stringify({
        metadata: { decision: "test_now" },
        entries: [
          {
            id: "E1",
            claim: "目标人群反复提到清洁痛点",
            evidence_label: "observed_public",
            source_urls: ["https://example.com/review"],
          },
        ],
      }),
    );
    expect(evidence[0]).toMatchObject({
      id: "E1",
      evidenceLabel: "observed_public",
    });

    const experiments = parseLaunchCalendar(
      'day,action,evidence_to_collect,success_criterion,stop_condition\r\n1,"访谈 5 人, 记录原话",原话,重复问题,只有泛泛偏好\r\n',
    );
    expect(experiments).toHaveLength(1);
    expect(experiments[0]?.action).toBe("访谈 5 人, 记录原话");
  });

  test("degrades damaged artifact content to empty data", () => {
    expect(parseEvidenceLedger("{broken")).toEqual([]);
    expect(parseLaunchCalendar("not,a,launch,calendar")).toEqual([]);
  });

  test("marks a newly recorded result as awaiting reassessment", () => {
    const resultMessage = formatValidationResultMessage(
      {
        experiment: "价格接受度测试",
        date: "2026-08-10",
        sampleDefinition: "12 名目标用户",
        observation: "目标价格区间存在明显分歧",
        outcome: "partial",
      },
      "zh",
    );
    const messages: Message[] = [
      ...renderMessages({ category: "通勤咖啡杯", decision: "test_now" }),
      { type: "human", id: "result", content: resultMessage },
    ];
    const model = buildDecisionWorkspaceModel({ messages });

    expect(model.validationResults).toHaveLength(1);
    expect(model.pendingReassessment).toBe(true);
    expect(model.currentSpec?.decision).toBe("test_now");
  });

  test("builds an explicit Growth Analyst handoff without inventing results", () => {
    const model = buildDecisionWorkspaceModel({
      messages: [
        ...renderMessages({
          category: "通勤咖啡杯",
          decision: "test_now",
          validation_goal: "验证价格接受度",
          hypotheses: ["用户接受 99-199 元"],
        }),
      ],
    });
    const handoff = buildGrowthAnalystHandoff(model, "zh");

    expect(handoff).toContain("OPENSKU_GROWTH_HANDOFF_V1");
    expect(handoff).toContain("请先让我上传 CSV/XLSX");
    expect(handoff).toContain('"recordedResults": []');
  });
});
