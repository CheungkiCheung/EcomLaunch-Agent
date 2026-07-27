import { afterEach, describe, expect, test, vi } from "vitest";

import {
  createCommerceExplicitCase,
  loadCommerceDataInboxSnapshot,
  loadCommerceWorkspaceSnapshot,
  resumeCommerceDatasetMapping,
  uploadCommerceDataset,
  type CommerceApiError,
} from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CASE_ID = "case_0123456789abcdef0123456789abcdef";
const DATASET_ID = "dset_0123456789abcdef0123456789abcdef";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("loadCommerceWorkspaceSnapshot", () => {
  test("fails closed when the workspace id is missing", async () => {
    await expect(
      loadCommerceWorkspaceSnapshot({ workspaceId: "" }),
    ).rejects.toMatchObject({ code: "workspace_missing" });
  });

  test("sends the workspace header and loads the selected Case projections", async () => {
    const requests: Array<{ url: string; init: RequestInit | undefined }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        requests.push({ url, init });

        if (url.endsWith("/api/commerce/cases?limit=100&offset=0")) {
          return jsonResponse({
            items: [caseResponse()],
            limit: 100,
            offset: 0,
          });
        }
        if (url.endsWith(`/api/commerce/cases/${CASE_ID}`)) {
          return jsonResponse({
            case: caseResponse(),
            lineage: null,
            evidence: [],
            hypotheses: [],
            analysis: {
              status: "unavailable",
              unavailable_reason: "lineage_not_found",
              baseline_metrics: [],
              current_metrics: [],
              anomalies: [],
            },
            actions: [],
          });
        }
        if (url.endsWith(`/api/commerce/cases/${CASE_ID}/events`)) {
          return jsonResponse({ items: [] });
        }
        if (
          url.endsWith(`/api/commerce/cases/${CASE_ID}/runs?limit=100&offset=0`)
        ) {
          return jsonResponse({ items: [], limit: 100, offset: 0 });
        }
        return new Response("not found", { status: 404 });
      }),
    );

    const snapshot = await loadCommerceWorkspaceSnapshot({
      workspaceId: WORKSPACE_ID,
      selectedCaseId: CASE_ID,
    });

    expect(snapshot.selectedCase?.case.id).toBe(CASE_ID);
    expect(snapshot.selectedCase?.analysis.status).toBe("unavailable");
    expect(snapshot.selectedCase?.actions).toEqual([]);
    expect(requests).toHaveLength(4);
    for (const request of requests) {
      expect(
        new Headers(request.init?.headers).get("X-Commerce-Workspace-Id"),
      ).toBe(WORKSPACE_ID);
      expect(request.init?.credentials).toBe("include");
      expect(request.init?.cache).toBe("no-store");
    }
  });

  test("rejects malformed backend contracts instead of guessing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ items: [{ id: "broken" }] })),
    );

    await expect(
      loadCommerceWorkspaceSnapshot({ workspaceId: WORKSPACE_ID }),
    ).rejects.toEqual(
      expect.objectContaining<Partial<CommerceApiError>>({
        code: "invalid_response",
      }),
    );
  });
});

describe("Commerce Data Inbox API", () => {
  test("loads a workspace-scoped dataset list and resumable detail", async () => {
    const requests: Array<{ url: string; init: RequestInit | undefined }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        requests.push({ url, init });
        if (url.endsWith("/api/commerce/datasets?limit=100&offset=0")) {
          return jsonResponse({
            items: [
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
                checks: datasetChecks(),
                integrity_status: "verified",
              },
            ],
            limit: 100,
            offset: 0,
          });
        }
        if (url.endsWith(`/api/commerce/datasets/${DATASET_ID}`)) {
          return jsonResponse(datasetDetailResponse());
        }
        return new Response("not found", { status: 404 });
      }),
    );

    const snapshot = await loadCommerceDataInboxSnapshot({
      workspaceId: WORKSPACE_ID,
    });

    expect(snapshot.selectedDataset?.manifest.dataset_id).toBe(DATASET_ID);
    expect(snapshot.datasets[0]?.checks.table_count).toBe(1);
    expect(requests).toHaveLength(2);
    for (const request of requests) {
      expect(
        new Headers(request.init?.headers).get("X-Commerce-Workspace-Id"),
      ).toBe(WORKSPACE_ID);
    }
  });

  test("uploads multipart data and keeps the workspace contract", async () => {
    let request: { url: string; init: RequestInit | undefined } | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        request = {
          url:
            typeof input === "string"
              ? input
              : input instanceof URL
                ? input.toString()
                : input.url,
          init,
        };
        return jsonResponse(datasetIntakeResponse());
      }),
    );

    const result = await uploadCommerceDataset({
      workspaceId: WORKSPACE_ID,
      files: [new File(["order_id\no1\n"], "orders.csv", { type: "text/csv" })],
    });

    expect(result.manifest.dataset_id).toBe(DATASET_ID);
    expect(request?.url).toContain("/api/commerce/datasets/intake");
    expect(request?.init?.method).toBe("POST");
    expect(request?.init?.body).toBeInstanceOf(FormData);
    expect(
      new Headers(request?.init?.headers).get("X-Commerce-Workspace-Id"),
    ).toBe(WORKSPACE_ID);
  });

  test("resumes a semantic confirmation with an auditable actor header", async () => {
    let request: { init: RequestInit | undefined } | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        request = { init };
        return jsonResponse({
          confirmations: [],
          mappings: datasetDetailResponse().mappings,
          capabilities: datasetDetailResponse().capabilities,
          created: true,
          replayed: false,
        });
      }),
    );

    const result = await resumeCommerceDatasetMapping({
      workspaceId: WORKSPACE_ID,
      datasetId: DATASET_ID,
      actorId: "operator-a",
      tableName: "orders",
      columnName: "order_approved_at",
      semanticField: "order.approved_at",
      idempotencyKey: "mapping-resume-001",
    });

    expect(result.created).toBe(true);
    const headers = new Headers(request?.init?.headers);
    expect(headers.get("X-Commerce-Workspace-Id")).toBe(WORKSPACE_ID);
    expect(headers.get("X-Commerce-Actor-Id")).toBe("operator-a");
    expect(headers.get("Content-Type")).toBe("application/json");
    const body = request?.init?.body;
    expect(typeof body).toBe("string");
    expect(JSON.parse(body as string)).toMatchObject({
      idempotency_key: "mapping-resume-001",
    });
  });
});

describe("Commerce Explicit Case API", () => {
  test("creates a content-addressed Case with the selected dataset and paths", async () => {
    let request: { url: string; init: RequestInit | undefined } | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        request = {
          url:
            typeof input === "string"
              ? input
              : input instanceof URL
                ? input.toString()
                : input.url,
          init,
        };
        return jsonResponse({
          case: caseResponse(),
          trigger: {
            trigger_type: "explicit_user_request",
            requested_paths: ["fulfillment"],
            peer_policy: null,
          },
          baseline_window: {
            start: "2026-05-01T00:00:00",
            end: "2026-06-01T00:00:00",
          },
          current_window: {
            start: "2026-06-01T00:00:00",
            end: "2026-07-01T00:00:00",
          },
        });
      }),
    );

    const result = await createCommerceExplicitCase({
      workspaceId: WORKSPACE_ID,
      datasetId: DATASET_ID,
      sellerId: "seller-4869",
      baselineWindow: {
        start: "2026-05-01T00:00:00",
        end: "2026-06-01T00:00:00",
      },
      currentWindow: {
        start: "2026-06-01T00:00:00",
        end: "2026-07-01T00:00:00",
      },
      requestedPaths: ["fulfillment"],
      peerPolicy: null,
    });

    expect(result.case.id).toBe(CASE_ID);
    expect(request?.url).toContain(
      `/api/commerce/datasets/${DATASET_ID}/cases`,
    );
    expect(request?.init?.method).toBe("POST");
    expect(
      new Headers(request?.init?.headers).get("X-Commerce-Workspace-Id"),
    ).toBe(WORKSPACE_ID);
    expect(JSON.parse(request?.init?.body as string)).toMatchObject({
      seller_id: "seller-4869",
      requested_paths: ["fulfillment"],
      peer_policy: null,
    });
  });
});

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function caseResponse() {
  return {
    id: CASE_ID,
    workspace_id: WORKSPACE_ID,
    title: "Deterministic anomaly for seller seller-4869",
    severity: "high",
    status: "investigating",
    summary: null,
    evidence_ids: [],
    hypothesis_ids: [],
    action_ids: [],
    opened_at: "2026-07-20T02:32:41Z",
    updated_at: "2026-07-20T02:33:27Z",
    version: 1,
  };
}

function datasetChecks() {
  return {
    file_count: 1,
    table_count: 1,
    row_count: 1,
    confirmed_mapping_count: 1,
    unresolved_mapping_count: 0,
    available_capability_count: 0,
    partial_capability_count: 0,
    unavailable_capability_count: 3,
  };
}

function datasetManifest() {
  return {
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
  };
}

function datasetProfile() {
  return {
    schema_version: "1.0",
    dataset_id: DATASET_ID,
    workspace_id: WORKSPACE_ID,
    tables: [
      {
        table_name: "orders",
        row_count: 1,
        column_count: 1,
        columns: [
          {
            name: "order_approved_at",
            inferred_type: "datetime",
            row_count: 1,
            non_null_count: 1,
            missing_count: 0,
            missing_rate: 0,
            unique_count: 1,
            unique_rate: 1,
            example_values: ["2026-07-20T00:00:00"],
            numeric_min: null,
            numeric_max: null,
            leading_zero_count: 0,
            leading_zero_rate: 0,
            is_primary_key_candidate: false,
            is_time_candidate: true,
          },
        ],
        duplicate_row_count: 0,
        duplicate_row_rate: 0,
        primary_key_candidates: [],
        time_candidates: ["order_approved_at"],
      },
    ],
    join_risks: [],
  };
}

function datasetMappings() {
  return {
    schema_version: "1.0",
    dataset_id: DATASET_ID,
    workspace_id: WORKSPACE_ID,
    mappings: [
      {
        table_name: "orders",
        column_name: "order_approved_at",
        semantic_field: "order.approved_at",
        confidence: 1,
        source: "deterministic_rule",
        status: "confirmed",
        reason: "Matched deterministic orders field rule",
      },
    ],
    unresolved_columns: [],
  };
}

function datasetCapabilities() {
  return {
    schema_version: "1.0",
    dataset_id: DATASET_ID,
    workspace_id: WORKSPACE_ID,
    capabilities: [
      {
        name: "fulfillment_diagnosis",
        path_agent: "FulfillmentPathAgent",
        status: "unavailable",
        reason_codes: ["missing_required_semantics"],
        available_fields: [],
        missing_required_fields: ["order.id"],
        missing_optional_fields: [],
        unmet_dependencies: [],
      },
    ],
  };
}

function datasetDetailResponse() {
  return {
    manifest: datasetManifest(),
    profile: datasetProfile(),
    mappings: datasetMappings(),
    capabilities: datasetCapabilities(),
    confirmations: [],
    checks: datasetChecks(),
    integrity_status: "verified" as const,
  };
}

function datasetIntakeResponse() {
  const detail = datasetDetailResponse();
  return {
    manifest: detail.manifest,
    profile: detail.profile,
    mappings: detail.mappings,
    capabilities: detail.capabilities,
  };
}
