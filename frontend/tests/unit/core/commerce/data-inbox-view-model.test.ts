import { describe, expect, test } from "vitest";

import { buildCommerceDataInboxViewModel } from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const DATASET_ID = "dset_0123456789abcdef0123456789abcdef";

describe("buildCommerceDataInboxViewModel", () => {
  test("keeps the empty state honest and does not invent a historical batch", () => {
    const view = buildCommerceDataInboxViewModel({
      workspaceId: WORKSPACE_ID,
      datasets: [],
      selectedDataset: null,
    });

    expect(view.status).toBe("empty");
    expect(view.title).toBe("接入经营数据");
    expect(view.recentDatasets).toEqual([]);
    expect(view.notObservedLabels).toEqual([
      "曝光",
      "点击",
      "加购",
      "广告消耗",
      "库存",
      "利润",
    ]);
  });

  test("projects deterministic checks and one bounded semantic confirmation", () => {
    const view = buildCommerceDataInboxViewModel({
      workspaceId: WORKSPACE_ID,
      datasets: [
        {
          dataset_id: DATASET_ID,
          workspace_id: WORKSPACE_ID,
          created_at: "2026-07-20T02:32:41Z",
          files: [
            {
              original_name: "orders.csv",
              format: "csv",
              size_bytes: 20,
              sha256: "a".repeat(64),
              archive_member: null,
            },
          ],
          checks: {
            file_count: 1,
            table_count: 1,
            row_count: 2,
            confirmed_mapping_count: 1,
            unresolved_mapping_count: 1,
            available_capability_count: 0,
            partial_capability_count: 0,
            unavailable_capability_count: 3,
          },
          integrity_status: "verified",
        },
      ],
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
              row_count: 2,
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
          capabilities: [],
        },
        confirmations: [],
        checks: {
          file_count: 1,
          table_count: 1,
          row_count: 2,
          confirmed_mapping_count: 1,
          unresolved_mapping_count: 1,
          available_capability_count: 0,
          partial_capability_count: 0,
          unavailable_capability_count: 3,
        },
        integrity_status: "verified",
      },
    });

    expect(view.status).toBe("review");
    expect(view.title).toBe("订单履约数据");
    expect(view.metadataLabel).toContain("2 行");
    expect(view.pendingConfirmation).toMatchObject({
      tableName: "orders",
      columnName: "order_approved_at",
      semanticLabel: "订单审核时间",
    });
    expect(view.checks.find((item) => item.label === "字段语义")?.detail).toBe(
      "1 项需确认",
    );
    expect(view.recognizedLabels).toEqual(["订单"]);
  });
});
