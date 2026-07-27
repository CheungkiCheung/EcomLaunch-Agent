import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceEvidenceExplorer } from "@/components/commerce/evidence-explorer";

describe("CommerceEvidenceExplorer", () => {
  test("renders support contradiction references and boundaries without runtime copy", () => {
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceEvidenceExplorer, {
          viewModel: {
            title: "证据浏览",
            subtitle:
              "逐条检查支持、矛盾和未知证据，以及它们引用的事实与指标。",
            filters: [
              { value: "all", label: "全部", count: 2 },
              { value: "supports", label: "支持", count: 1 },
              { value: "contradicts", label: "矛盾", count: 1 },
              { value: "unknown", label: "未知", count: 0 },
            ],
            items: [
              {
                id: "evd_support",
                shortId: "evd_…pport",
                summary: "延迟履约率从 3.5% 变为 35.1%",
                relation: "supports",
                relationLabel: "支持",
                typeLabel: "指标证据",
                semanticStatusLabel: "已推导",
                confidenceLabel: "98%",
                referenceCountLabel: "引用 2 个对象",
                references: [
                  {
                    id: "m1",
                    kind: "metric",
                    label: "基线延迟履约率",
                    valueLabel: "3.5%",
                    metadataLabel: "5月1日—6月1日",
                  },
                ],
                hypotheses: [
                  {
                    id: "h1",
                    label: "履约问题真实存在",
                    statusLabel: "调查中",
                    relationLabel: "支持当前判断",
                  },
                ],
                boundary: "该证据支持当前判断，但不能单独证明因果关系。",
              },
              {
                id: "evd_contradict",
                shortId: "evd_…adict",
                summary: "当前平均处理时长为 8.2 小时",
                relation: "contradicts",
                relationLabel: "矛盾",
                typeLabel: "指标证据",
                semanticStatusLabel: "已观察",
                confidenceLabel: "93%",
                referenceCountLabel: "引用 1 个对象",
                references: [],
                hypotheses: [],
                boundary: "该证据反驳部分判断，应与支持证据共同审查。",
              },
            ],
          },
        }),
      ),
    );

    for (const label of [
      "证据浏览",
      "支持",
      "矛盾",
      "延迟履约率从 3.5% 变为 35.1%",
      "证据详情",
      "引用对象",
      "支持的判断",
      "证据边界",
      "不能单独证明因果关系",
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
