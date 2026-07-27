import { afterEach, describe, expect, test, vi } from "vitest";

import {
  decideCommerceActionApproval,
  executeCommerceAction,
  loadCommerceActionCenterSnapshot,
  type CommerceActionRecord,
  type CommerceApiError,
} from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CASE_ID = "case_0123456789abcdef0123456789abcdef";
const ACTION_ID = "act_0123456789abcdef0123456789abcdef";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Commerce Action API", () => {
  test("loads case-scoped records and the selected authoritative detail", async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = requestUrl(input);
        requests.push({ url, init });
        if (url.endsWith(`/api/commerce/cases/${CASE_ID}/actions`)) {
          return jsonResponse({ items: [actionRecord()] });
        }
        if (url.endsWith(`/api/commerce/actions/${ACTION_ID}`)) {
          return jsonResponse({
            record: actionRecord(),
            approval: null,
            artifact: null,
            follow_ups: [],
          });
        }
        return new Response("not found", { status: 404 });
      }),
    );

    const snapshot = await loadCommerceActionCenterSnapshot({
      workspaceId: WORKSPACE_ID,
      caseIds: [CASE_ID],
      selectedActionId: ACTION_ID,
    });

    expect(snapshot.records).toHaveLength(1);
    expect(snapshot.selectedDetail?.record.action.id).toBe(ACTION_ID);
    expect(requests).toHaveLength(2);
    for (const request of requests) {
      expect(
        new Headers(request.init?.headers).get("X-Commerce-Workspace-Id"),
      ).toBe(WORKSPACE_ID);
    }
  });

  test("executes with auditable actor and idempotency headers without guessing the response", async () => {
    let request: { url: string; init?: RequestInit } | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        request = { url: requestUrl(input), init };
        return jsonResponse({
          run: actionRun(),
          record: actionRecord("monitoring"),
          artifact: metricMonitorArtifact(),
          created: true,
          replayed: false,
          error_message: null,
        });
      }),
    );

    const result = await executeCommerceAction({
      workspaceId: WORKSPACE_ID,
      actorId: "operator-a",
      actionId: ACTION_ID,
      operation: "execute",
      idempotencyKey: "execute-action-001",
    });

    expect(result.record.action.status).toBe("monitoring");
    expect(request?.url).toContain(
      `/api/commerce/actions/${ACTION_ID}/executions`,
    );
    expect(request?.init?.method).toBe("POST");
    const headers = new Headers(request?.init?.headers);
    expect(headers.get("X-Commerce-Workspace-Id")).toBe(WORKSPACE_ID);
    expect(headers.get("X-Commerce-Actor-Id")).toBe("operator-a");
    expect(JSON.parse(request?.init?.body as string)).toEqual({
      operation: "execute",
      idempotency_key: "execute-action-001",
    });
  });

  test("rejects malformed Action records instead of inferring missing policy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ items: [{ action: { id: ACTION_ID } }] }),
      ),
    );

    await expect(
      loadCommerceActionCenterSnapshot({
        workspaceId: WORKSPACE_ID,
        caseIds: [CASE_ID],
      }),
    ).rejects.toEqual(
      expect.objectContaining<Partial<CommerceApiError>>({
        code: "invalid_response",
      }),
    );
  });

  test("records an approval decision with actor identity and a stable key", async () => {
    let request: { url: string; init?: RequestInit } | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        request = { url: requestUrl(input), init };
        return jsonResponse(approvalDecisionResponse());
      }),
    );

    const result = await decideCommerceActionApproval({
      workspaceId: WORKSPACE_ID,
      actorId: "risk-reviewer",
      actionId: ACTION_ID,
      decision: "approve",
      idempotencyKey: `approve-${ACTION_ID}`,
      reason: "证据和回滚边界已复核",
    });

    expect(result.approval.status).toBe("approved");
    expect(request?.url).toContain(
      `/api/commerce/actions/${ACTION_ID}/approvals/approve`,
    );
    const headers = new Headers(request?.init?.headers);
    expect(headers.get("X-Commerce-Actor-Id")).toBe("risk-reviewer");
    expect(JSON.parse(request?.init?.body as string)).toEqual({
      idempotency_key: `approve-${ACTION_ID}`,
      reason: "证据和回滚边界已复核",
    });
  });
});

function actionRecord(status = "policy_checked") {
  const rollbackPlan = {
    strategy: "Disable the internal monitor",
    trigger: "The metric contract or seller scope changes",
    verification: "Confirm no active monitor remains for this Action",
  };
  const action = {
    id: ACTION_ID,
    workspace_id: WORKSPACE_ID,
    case_id: CASE_ID,
    title: "Monitor late-delivery recovery",
    description: "Create a reversible internal metric monitor.",
    status,
    evidence_ids: ["evd_0123456789abcdef0123456789abcdef"],
    risk_level: "medium",
    approval: {
      required: false,
      status: "not_required",
      approval_id: null,
      reason: "Internal reversible Action is below the approval threshold",
    },
    rollback_plan: rollbackPlan,
  };
  return {
    action,
    decision: {
      schema_version: "commerce.action-policy-decision@1.0.0",
      validated: {
        schema_version: "commerce.validated-action@1.0.0",
        draft: {
          schema_version: "commerce.action-draft@1.0.0",
          id: ACTION_ID,
          workspace_id: WORKSPACE_ID,
          case_id: CASE_ID,
          title: action.title,
          description: action.description,
          evidence_ids: action.evidence_ids,
          hypothesis_ids: ["hyp_0123456789abcdef0123456789abcdef"],
          expected_signal_metric_ids: ["mobs_0123456789abcdef0123456789abcdef"],
          parameters: {
            kind: "create_metric_monitor",
            metric_name: "late_delivery_rate",
            metric_observation_ids: ["mobs_0123456789abcdef0123456789abcdef"],
            comparison: "less_than_or_equal",
            threshold: "0.048",
            cadence_hours: 24,
            follow_up_after_days: 7,
          },
          rollback_plan: rollbackPlan,
        },
        validation_sha256: "a".repeat(64),
      },
      level: "L2",
      disposition: "auto_execute",
      reason_codes: ["reversible_internal_operation"],
      required_approvals: 0,
      execution_tool: "internal_metric_monitor.create",
      action,
    },
    created_at: "2026-07-20T02:32:41Z",
    updated_at: "2026-07-20T02:42:41Z",
    version: 1,
  };
}

function actionRun() {
  return {
    id: "run_0123456789abcdef0123456789abcdef",
    workspace_id: WORKSPACE_ID,
    case_id: CASE_ID,
    run_type: "action_execution",
    status: "completed",
    phase: "executing",
    goal: "Execute Action",
    parent_run_id: null,
    subject_action_id: ACTION_ID,
    action_operation: "execute",
    requested_paths: [],
    wait_reason: null,
    stop_reason: "action_execution_verified",
    created_at: "2026-07-20T02:42:41Z",
    started_at: "2026-07-20T02:42:42Z",
    ended_at: "2026-07-20T02:42:43Z",
    updated_at: "2026-07-20T02:42:43Z",
    version: 3,
  };
}

function metricMonitorArtifact() {
  return {
    schema_version: "commerce.action-execution-artifact@1.0.0",
    workspace_id: WORKSPACE_ID,
    case_id: CASE_ID,
    action_id: ACTION_ID,
    execution_tool: "internal_metric_monitor.create",
    payload: {
      kind: "metric_monitor",
      metric_name: "late_delivery_rate",
      metric_observation_ids: ["mobs_0123456789abcdef0123456789abcdef"],
      comparison: "less_than_or_equal",
      threshold: "0.048",
      cadence_hours: 24,
      follow_up_after_days: 7,
      next_evaluation_at: "2026-07-27T02:42:43Z",
    },
    status: "active",
    execution_input_sha256: "b".repeat(64),
    verification_sha256: "c".repeat(64),
    created_at: "2026-07-20T02:42:43Z",
    updated_at: "2026-07-20T02:42:43Z",
    version: 1,
  };
}

function approvalDecisionResponse() {
  const record = actionRecord("approved") as unknown as CommerceActionRecord;
  const approvalId = "apr_0123456789abcdef0123456789abcdef";
  record.action.approval = {
    required: true,
    status: "approved",
    approval_id: approvalId,
    reason: "Policy L4 requires human approval",
  };
  record.decision.action = record.action;
  record.decision.level = "L4";
  record.decision.disposition = "approval_required";
  record.decision.required_approvals = 1;
  const approval = {
    schema_version: "commerce.approval-request@1.0.0",
    id: approvalId,
    workspace_id: WORKSPACE_ID,
    case_id: CASE_ID,
    action_id: ACTION_ID,
    required_approvals: 1,
    status: "approved",
    approved_actor_ids: ["risk-reviewer"],
    rejected_actor_id: null,
    modified_by_actor_id: null,
    replacement_draft_sha256: null,
    created_at: "2026-07-20T02:42:41Z",
    updated_at: "2026-07-20T02:42:43Z",
    version: 2,
  };
  return {
    record,
    approval,
    command: {
      schema_version: "commerce.approval-decision@1.0.0",
      id: "apd_0123456789abcdef0123456789abcdef",
      workspace_id: WORKSPACE_ID,
      case_id: CASE_ID,
      action_id: ACTION_ID,
      approval_id: approvalId,
      decision: "approve",
      actor_id: "risk-reviewer",
      idempotency_key_sha256: "d".repeat(64),
      reason: "证据和回滚边界已复核",
      replacement_draft: null,
      created_at: "2026-07-20T02:42:43Z",
    },
    replayed: false,
  };
}

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function requestUrl(input: RequestInfo | URL): string {
  return typeof input === "string"
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url;
}
