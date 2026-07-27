import { describe, expect, test } from "vitest";

import { buildCommerceCapabilityReportViewModel } from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const DATASET_ID = "dset_0123456789abcdef0123456789abcdef";

describe("buildCommerceCapabilityReportViewModel", () => {
  test("keeps capability empty until a verified Dataset exists", () => {
    const view = buildCommerceCapabilityReportViewModel({
      workspaceId: WORKSPACE_ID,
      datasets: [],
      selectedDataset: null,
    });

    expect(view.status).toBe("empty");
    expect(view.paths).toEqual([]);
    expect(view.title).toBe("这批数据能分析什么");
  });

  test("projects available partial and unavailable paths from backend reason codes", () => {
    const view = buildCommerceCapabilityReportViewModel(capabilitySnapshot());

    expect(view.status).toBe("ready");
    expect(view.paths.map((path) => [path.label, path.statusLabel])).toEqual([
      ["履约诊断", "可直接分析"],
      ["评价体验", "部分可分析"],
      ["卖家对标", "当前不可分析"],
    ]);
    expect(view.paths[0]?.canCreateCase).toBe(true);
    expect(view.paths[2]?.canCreateCase).toBe(false);
    expect(view.paths[2]?.reasonLabels).toContain("实体数量不足");
    expect(view.reviewItems[0]).toMatchObject({
      columnName: "order_approved_at",
      semanticLabel: "订单审核时间",
    });
    expect(view.notObservedLabels).toContain("利润");
  });
});

function capabilitySnapshot() {
  const checks = {
    file_count: 1,
    table_count: 1,
    row_count: 1,
    confirmed_mapping_count: 1,
    unresolved_mapping_count: 1,
    available_capability_count: 1,
    partial_capability_count: 1,
    unavailable_capability_count: 1,
  };
  return {
    workspaceId: WORKSPACE_ID,
    datasets: [],
    selectedDataset: {
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
      mappings: {
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
            confidence: 0.75,
            source: "deterministic_rule",
            status: "needs_confirmation",
            reason: "ambiguous",
          },
        ],
        unresolved_columns: ["orders.order_approved_at"],
      },
      capabilities: {
        schema_version: "1.0",
        dataset_id: DATASET_ID,
        workspace_id: WORKSPACE_ID,
        capabilities: [
          capability("fulfillment_diagnosis", "available", ["available"]),
          capability("review_experience", "partial", [
            "missing_optional_semantics",
          ]),
          capability("seller_peer_comparison", "unavailable", [
            "insufficient_entity_diversity",
          ]),
        ],
      },
      confirmations: [],
      checks,
      integrity_status: "verified" as const,
    },
  };
}

function capability(name: string, status: string, reasonCodes: string[]) {
  return {
    name,
    path_agent: `${name}Agent`,
    status,
    reason_codes: reasonCodes,
    available_fields: ["order.id"],
    missing_required_fields: status === "unavailable" ? ["seller.id"] : [],
    missing_optional_fields: status === "partial" ? ["review.comment"] : [],
    unmet_dependencies: [],
  };
}
