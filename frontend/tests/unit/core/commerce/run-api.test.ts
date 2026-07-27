import { afterEach, describe, expect, test, vi } from "vitest";

import {
  loadCommerceAgentRunSnapshot,
  type CommerceApiError,
} from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CASE_ID = "case_0123456789abcdef0123456789abcdef";
const RUN_ID = "run_0123456789abcdef0123456789abcdef";

afterEach(() => vi.unstubAllGlobals());

describe("Commerce Agent Run API", () => {
  test("loads cross-Case Runs and selected detail events checkpoints", async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input);
        requests.push({ url, init });
        if (
          url.endsWith(`/api/commerce/cases/${CASE_ID}/runs?limit=100&offset=0`)
        ) {
          return jsonResponse({ items: [run()], limit: 100, offset: 0 });
        }
        if (url.endsWith(`/api/commerce/runs/${RUN_ID}`)) {
          return jsonResponse({ run: run(), latest_checkpoint: checkpoint() });
        }
        if (url.endsWith(`/api/commerce/runs/${RUN_ID}/events`)) {
          return jsonResponse({ items: [] });
        }
        if (url.endsWith(`/api/commerce/runs/${RUN_ID}/checkpoints`)) {
          return jsonResponse({ items: [checkpoint()] });
        }
        return new Response("not found", { status: 404 });
      }),
    );

    const snapshot = await loadCommerceAgentRunSnapshot({
      workspaceId: WORKSPACE_ID,
      caseIds: [CASE_ID],
      selectedRunId: RUN_ID,
    });

    expect(snapshot.runs).toHaveLength(1);
    expect(snapshot.selectedDetail?.run.id).toBe(RUN_ID);
    expect(snapshot.checkpoints[0]?.sequence).toBe(7);
    expect(requests).toHaveLength(4);
    for (const request of requests) {
      expect(
        new Headers(request.init?.headers).get("X-Commerce-Workspace-Id"),
      ).toBe(WORKSPACE_ID);
    }
  });

  test("fails closed when checkpoint shape is incomplete", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = requestUrl(input);
        if (url.includes("/cases/")) {
          return jsonResponse({ items: [run()], limit: 100, offset: 0 });
        }
        if (url.endsWith(`/runs/${RUN_ID}`)) {
          return jsonResponse({ run: run(), latest_checkpoint: null });
        }
        if (url.endsWith(`/runs/${RUN_ID}/events`)) {
          return jsonResponse({ items: [] });
        }
        return jsonResponse({ items: [{ id: "broken" }] });
      }),
    );

    await expect(
      loadCommerceAgentRunSnapshot({
        workspaceId: WORKSPACE_ID,
        caseIds: [CASE_ID],
      }),
    ).rejects.toEqual(
      expect.objectContaining<Partial<CommerceApiError>>({
        code: "invalid_response",
      }),
    );
  });
});

function run() {
  return {
    id: RUN_ID,
    workspace_id: WORKSPACE_ID,
    case_id: CASE_ID,
    run_type: "case_investigation",
    status: "completed",
    phase: "verifying",
    goal: "Explain fulfillment",
    parent_run_id: null,
    subject_action_id: null,
    action_operation: null,
    requested_paths: ["fulfillment"],
    wait_reason: null,
    stop_reason: "goal_achieved",
    created_at: "2026-07-20T10:33:00Z",
    started_at: "2026-07-20T10:33:10Z",
    ended_at: "2026-07-20T10:33:22Z",
    updated_at: "2026-07-20T10:33:22Z",
    version: 4,
  };
}

function checkpoint() {
  return {
    id: "chk_0123456789abcdef0123456789abcdef",
    sequence: 7,
    checkpoint: {
      schema_version: "commerce.goal-loop-checkpoint@1.0.0",
      workspace_id: WORKSPACE_ID,
      run_id: RUN_ID,
      case_id: CASE_ID,
      goal: "Explain fulfillment",
      loop_iteration: 0,
      budget_snapshot: {
        limit: {
          max_iterations: 8,
          max_tool_calls: 20,
          max_path_agents: 3,
          max_tokens: 16000,
          max_wall_time_seconds: 300,
          max_model_escalations: 1,
          max_verification_repairs: 2,
          max_repeated_actions: 2,
          max_consecutive_no_new_evidence: 2,
        },
        usage: {
          iterations: 0,
          tool_calls: 0,
          path_agents: 0,
          tokens: 0,
          wall_time_seconds: 0,
          model_escalations: 0,
          verification_repairs: 0,
          repeated_actions: 0,
          consecutive_no_new_evidence: 0,
        },
      },
      evidence_ids: [],
      hypothesis_ids: [],
      active_path_task_ids: [],
      model_assignments: [],
      skill_versions: [],
      context_sha256: "a".repeat(64),
      tool_state: [],
      wait_reason: null,
      resume_token_sha256: null,
    },
    created_at: "2026-07-20T10:33:10Z",
  };
}

function requestUrl(input: RequestInfo | URL): string {
  return typeof input === "string"
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url;
}

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
