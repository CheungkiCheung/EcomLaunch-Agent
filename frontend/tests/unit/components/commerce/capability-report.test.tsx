import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceCapabilityReportView } from "@/components/commerce/capability-report";

describe("CommerceCapabilityReportView", () => {
  test("renders the capability-before-Case hierarchy without runtime copy", () => {
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceCapabilityReportView, {
          viewModel: {
            status: "ready",
            title: "这批数据能分析什么",
            subtitle: "根据已确认字段、关联关系和样本量，明确可分析范围。",
            metadataLabel: "订单履约数据 · 2,268 行 · 6 个文件",
            dataset: null,
            paths: [
              {
                name: "fulfillment_diagnosis",
                label: "履约诊断",
                description: "识别履约关键环节的问题",
                status: "available",
                statusLabel: "可直接分析",
                statusDescription: "证据完整，可以进入案例队列",
                reasonLabels: [],
                availableFields: ["订单", "发货时间", "签收时间"],
                missingFields: [],
                canCreateCase: true,
              },
            ],
            observedLabels: ["订单", "履约", "商品"],
            notObservedLabels: ["曝光", "点击", "库存", "利润"],
            reviewItems: [],
          },
          error: null,
          notice: null,
          onRetry: () => undefined,
          onCreateCase: () => undefined,
        }),
      ),
    );

    for (const label of [
      "能力结论",
      "可直接分析",
      "履约诊断",
      "可用分析路径",
      "数据边界",
      "已观察",
      "未观察",
      "需要补充或确认",
      "未观察字段不会被推断为零",
    ]) {
      expect(text).toContain(label);
    }
    expect(text).not.toContain("Agent");
    expect(text).not.toContain("Token");
    expect(text).not.toContain("Retry");
  });
});

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
