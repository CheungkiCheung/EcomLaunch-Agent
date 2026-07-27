import { describe, expect, test } from "vitest";

import {
  buildCommerceCaseCreateOptions,
  buildCommerceCaseQueueViewModel,
  validateCommerceExplicitCaseDraft,
} from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";

describe("buildCommerceCaseQueueViewModel", () => {
  test("groups actionable tracking and closed Cases without inventing activity", () => {
    const view = buildCommerceCaseQueueViewModel(
      [
        commerceCase("case_low", "low", "investigating", null, "01:00:00Z"),
        commerceCase(
          "case_high",
          "high",
          "awaiting_data",
          "评分下降已观察，缺少评价文本。",
          "02:00:00Z",
        ),
        commerceCase(
          "case_tracking",
          "medium",
          "monitoring",
          "等待新一批履约数据后重新计算。",
          "03:00:00Z",
        ),
        commerceCase(
          "case_closed",
          "medium",
          "resolved",
          "案例已完成。",
          "04:00:00Z",
        ),
      ],
      { filter: "all", query: "" },
    );

    expect(view.status).toBe("ready");
    expect(view.attentionItems.map((item) => item.id)).toEqual([
      "case_high",
      "case_low",
    ]);
    expect(view.trackingItems.map((item) => item.id)).toEqual([
      "case_tracking",
    ]);
    expect(view.closedItems.map((item) => item.id)).toEqual(["case_closed"]);
    expect(view.attentionItems[0]).toMatchObject({
      statusLabel: "等待数据",
      severityLabel: "高风险",
      actionLabel: "补充数据",
    });
    expect(view.attentionItems[1]?.summary).toBe(
      "当前案例尚未形成可展示摘要。",
    );
  });

  test("filters by lifecycle state and Chinese keyword", () => {
    const cases = [
      commerceCase(
        "case_fulfillment",
        "high",
        "investigating",
        "履约延迟需要继续调查。",
        "02:00:00Z",
        "Deterministic anomaly for seller fulfillment-4869",
      ),
      commerceCase(
        "case_review",
        "medium",
        "awaiting_data",
        "评分下降已观察。",
        "03:00:00Z",
        "User-requested investigation for seller review-0b90",
      ),
    ];

    const waiting = buildCommerceCaseQueueViewModel(cases, {
      filter: "awaiting_data",
      query: "",
    });
    expect(waiting.attentionItems.map((item) => item.title)).toEqual([
      "评价体验异常",
    ]);

    const fulfillment = buildCommerceCaseQueueViewModel(cases, {
      filter: "all",
      query: "履约",
    });
    expect(fulfillment.attentionItems.map((item) => item.title)).toEqual([
      "履约延迟异常",
    ]);
  });

  test("derives seller suggestions and path availability from the selected Dataset", () => {
    const options = buildCommerceCaseCreateOptions(
      datasetSnapshot(),
      "review_experience",
    );

    expect(options?.datasetId).toBe("dset_0123456789abcdef0123456789abcdef");
    expect(options?.sellerSuggestions).toEqual(["seller-4869"]);
    expect(options?.pathOptions).toEqual([
      expect.objectContaining({
        value: "fulfillment",
        statusLabel: "可直接分析",
        disabled: false,
        selected: false,
      }),
      expect.objectContaining({
        value: "review_experience",
        statusLabel: "部分可分析",
        disabled: false,
        selected: true,
      }),
      expect.objectContaining({
        value: "seller_peer",
        statusLabel: "当前不可分析",
        disabled: true,
        selected: false,
      }),
    ]);
  });

  test("rejects overlapping windows and incomplete seller-peer policy", () => {
    expect(
      validateCommerceExplicitCaseDraft({
        sellerId: "seller-4869",
        baselineStart: "2026-05-01T00:00",
        baselineEnd: "2026-06-15T00:00",
        currentStart: "2026-06-01T00:00",
        currentEnd: "2026-07-01T00:00",
        requestedPaths: ["fulfillment"],
        peerProductCategory: "",
        peerMinOrders: 20,
        matchSellerState: true,
      }),
    ).toBe("基线窗口必须在当前窗口开始前结束");

    expect(
      validateCommerceExplicitCaseDraft({
        sellerId: "seller-4869",
        baselineStart: "2026-05-01T00:00",
        baselineEnd: "2026-06-01T00:00",
        currentStart: "2026-06-01T00:00",
        currentEnd: "2026-07-01T00:00",
        requestedPaths: ["seller_peer"],
        peerProductCategory: "",
        peerMinOrders: 20,
        matchSellerState: true,
      }),
    ).toBe("卖家对标需要填写商品类目口径");
  });
});

function commerceCase(
  id: string,
  severity: string,
  status: string,
  summary: string | null,
  time: string,
  title = "用户发起的经营诊断",
) {
  return {
    id,
    workspace_id: WORKSPACE_ID,
    title,
    severity,
    status,
    summary,
    evidence_ids: [],
    hypothesis_ids: [],
    action_ids: [],
    opened_at: `2026-07-20T${time}`,
    updated_at: `2026-07-20T${time}`,
    version: 1,
  };
}

function datasetSnapshot() {
  const workspaceId = WORKSPACE_ID;
  const datasetId = "dset_0123456789abcdef0123456789abcdef";
  const checks = {
    file_count: 1,
    table_count: 1,
    row_count: 1,
    confirmed_mapping_count: 1,
    unresolved_mapping_count: 0,
    available_capability_count: 1,
    partial_capability_count: 1,
    unavailable_capability_count: 1,
  };
  return {
    workspaceId,
    datasets: [],
    selectedDataset: {
      manifest: {
        schema_version: "1.0",
        dataset_id: datasetId,
        workspace_id: workspaceId,
        created_at: "2026-07-20T02:32:41Z",
        storage_relative_path: `${workspaceId}/${datasetId}`,
        files: [
          {
            id: "src_0123456789abcdef0123456789abcdef",
            original_name: "orders.csv",
            stored_relative_path: "raw/orders.csv",
            format: "csv",
            size_bytes: 20,
            sha256: "a".repeat(64),
            encoding: "utf-8",
            read_only: true,
            parent_source_id: null,
            archive_member: null,
          },
        ],
        tables: [
          {
            table_name: "order_items",
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
        dataset_id: datasetId,
        workspace_id: workspaceId,
        tables: [
          {
            table_name: "order_items",
            row_count: 1,
            column_count: 1,
            columns: [
              {
                name: "seller_id",
                inferred_type: "string",
                row_count: 1,
                non_null_count: 1,
                missing_count: 0,
                missing_rate: 0,
                unique_count: 1,
                unique_rate: 1,
                example_values: ["seller-4869", "seller-4869"],
                numeric_min: null,
                numeric_max: null,
                leading_zero_count: 0,
                leading_zero_rate: 0,
                is_primary_key_candidate: false,
                is_time_candidate: false,
              },
            ],
            duplicate_row_count: 0,
            duplicate_row_rate: 0,
            primary_key_candidates: [],
            time_candidates: [],
          },
        ],
        join_risks: [],
      },
      mappings: {
        schema_version: "1.0",
        dataset_id: datasetId,
        workspace_id: workspaceId,
        mappings: [
          {
            table_name: "order_items",
            column_name: "seller_id",
            semantic_field: "seller.id",
            confidence: 1,
            source: "deterministic_rule",
            status: "confirmed",
            reason: "deterministic",
          },
        ],
        unresolved_columns: [],
      },
      capabilities: {
        schema_version: "1.0",
        dataset_id: datasetId,
        workspace_id: workspaceId,
        capabilities: [
          capability("fulfillment_diagnosis", "available"),
          capability("review_experience", "partial"),
          capability("seller_peer_comparison", "unavailable"),
        ],
      },
      confirmations: [],
      checks,
      integrity_status: "verified" as const,
    },
  };
}

function capability(name: string, status: string) {
  return {
    name,
    path_agent: `${name}Agent`,
    status,
    reason_codes: [],
    available_fields: [],
    missing_required_fields: [],
    missing_optional_fields: [],
    unmet_dependencies: [],
  };
}
