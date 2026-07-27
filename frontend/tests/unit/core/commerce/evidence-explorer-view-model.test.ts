import { describe, expect, test } from "vitest";

import {
  buildCommerceEvidenceExplorerViewModel,
  filterCommerceEvidenceExplorerItems,
  type CommerceCaseDetail,
} from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CASE_ID = "case_0123456789abcdef0123456789abcdef";
const BASELINE_ID = "mobs_0123456789abcdef0123456789abcde1";
const CURRENT_ID = "mobs_0123456789abcdef0123456789abcde2";
const HANDLING_ID = "mobs_0123456789abcdef0123456789abcde3";

describe("buildCommerceEvidenceExplorerViewModel", () => {
  test("keeps supports contradictions and context evidence equally inspectable", () => {
    const view = buildCommerceEvidenceExplorerViewModel(caseDetail());

    expect(view.filters.map((item) => [item.label, item.count])).toEqual([
      ["全部", 3],
      ["支持", 1],
      ["矛盾", 1],
      ["未知", 1],
    ]);
    expect(view.items.map((item) => item.relationLabel)).toEqual([
      "支持",
      "矛盾",
      "未知",
    ]);
    expect(view.items[0]).toMatchObject({
      summary: "延迟履约率从 3.5% 变为 35.1%",
      typeLabel: "指标证据",
      semanticStatusLabel: "已推导",
      confidenceLabel: "98%",
      boundary: "该证据支持当前判断，但不能单独证明因果关系。",
    });
    expect(view.items[0]?.references).toEqual([
      expect.objectContaining({
        kind: "metric",
        label: "基线延迟履约率",
        valueLabel: "3.5%",
      }),
      expect.objectContaining({
        kind: "metric",
        label: "当前延迟履约率",
        valueLabel: "35.1%",
      }),
    ]);
    expect(view.items[0]?.hypotheses[0]?.relationLabel).toBe("支持当前判断");
    expect(view.items[1]?.hypotheses[0]?.relationLabel).toBe("反驳当前判断");
    expect(view.items[2]?.references[0]).toMatchObject({
      kind: "fact",
      valueLabel: "原始事实详情尚未开放",
    });
    expect(JSON.stringify(view)).not.toContain("Late delivery");
  });

  test("filters by relation and a localized metric keyword", () => {
    const view = buildCommerceEvidenceExplorerViewModel(caseDetail());

    expect(
      filterCommerceEvidenceExplorerItems(view.items, {
        filter: "contradicts",
        query: "",
      }).map((item) => item.relationLabel),
    ).toEqual(["矛盾"]);
    expect(
      filterCommerceEvidenceExplorerItems(view.items, {
        filter: "all",
        query: "履约率",
      }).map((item) => item.id),
    ).toEqual(["evd_support"]);
  });
});

function caseDetail(): CommerceCaseDetail {
  return {
    case: {
      id: CASE_ID,
      workspace_id: WORKSPACE_ID,
      title: "Deterministic anomaly for seller seller-4869",
      severity: "high",
      status: "investigating",
      summary: null,
      evidence_ids: ["evd_support", "evd_contradict", "evd_context"],
      hypothesis_ids: ["hyp_1"],
      action_ids: [],
      opened_at: "2026-07-20T02:32:41Z",
      updated_at: "2026-07-20T02:33:27Z",
      version: 2,
    },
    lineage: null,
    evidence: [
      {
        id: "evd_support",
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        summary: "Late delivery rate increased.",
        relation: "supports",
        semantic_status: "derived",
        confidence: 0.98,
        fact_ids: [],
        metric_observation_ids: [BASELINE_ID, CURRENT_ID],
      },
      {
        id: "evd_contradict",
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        summary: "Handling time did not worsen.",
        relation: "contradicts",
        semantic_status: "observed",
        confidence: 0.93,
        fact_ids: [],
        metric_observation_ids: [HANDLING_ID],
      },
      {
        id: "evd_context",
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        summary: "Advertising spend is not available.",
        relation: "context",
        semantic_status: "unknown",
        confidence: 0.5,
        fact_ids: ["fact_0123456789abcdef0123456789abcdef"],
        metric_observation_ids: [],
      },
    ],
    hypotheses: [
      {
        id: "hyp_1",
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        statement: "承运运输阶段可能与履约延迟有关。",
        status: "investigating",
        confidence: 0.74,
        supporting_evidence_ids: ["evd_support"],
        contradicting_evidence_ids: ["evd_contradict"],
        version: 1,
      },
    ],
    analysis: {
      status: "available",
      unavailable_reason: null,
      baseline_metrics: [
        metric(BASELINE_ID, "late_delivery_rate", "0.035", "ratio"),
      ],
      current_metrics: [
        metric(CURRENT_ID, "late_delivery_rate", "0.351", "ratio"),
        metric(HANDLING_ID, "handling_time_hours", "8.2", "hours"),
      ],
      anomalies: [],
    },
    actions: [],
  };
}

function metric(id: string, name: string, value: string, unit: string) {
  return {
    id,
    metric_name: name,
    semantic_status: "derived",
    value,
    unit,
    formula_version: `${name}@1.0.0`,
    window_start: "2026-05-01T00:00:00",
    window_end: "2026-06-01T00:00:00",
    sample_size: 100,
    numerator: null,
    denominator: null,
    source_fact_count: 100,
    unknown_reason: null,
  };
}
