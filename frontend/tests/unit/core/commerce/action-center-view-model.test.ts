import { describe, expect, test } from "vitest";

import {
  buildCommerceActionCenterViewModel,
  type CommerceActionParameters,
  type CommerceActionRecord,
  type CommerceCase,
} from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CASE_ID = "case_0123456789abcdef0123456789abcdef";
const REVIEW_CASE_ID = "case_1123456789abcdef0123456789abcdef";
const ACTION_ID = "act_0123456789abcdef0123456789abcdef";

describe("buildCommerceActionCenterViewModel", () => {
  test("projects the authoritative policy plan rollback and queue states", () => {
    const selected = actionRecord();
    const view = buildCommerceActionCenterViewModel({
      cases: [
        {
          ...commerceCase(
            CASE_ID,
            "Deterministic anomaly for seller fulfillment-4869",
            "high",
          ),
          summary: "延迟履约率显著上升，当前案例正在调查。",
        },
        commerceCase(REVIEW_CASE_ID, "评价体验异常", "medium"),
      ],
      records: [
        selected,
        actionRecord({
          id: "act_1123456789abcdef0123456789abcdef",
          caseId: REVIEW_CASE_ID,
          kind: "request_missing_data",
          status: "monitoring",
          title: "Request review details",
        }),
        actionRecord({
          id: "act_2123456789abcdef0123456789abcdef",
          status: "succeeded",
          kind: "export_audit_cohort",
          title: "Export delayed orders",
        }),
        actionRecord({
          id: "act_3123456789abcdef0123456789abcdef",
          status: "rejected",
          kind: "external_mutation",
          title: "Blocked merchant change",
          policyLevel: "L5",
          riskLevel: "critical",
          disposition: "blocked",
        }),
      ],
      selectedActionId: ACTION_ID,
      selectedDetail: {
        record: selected,
        approval: null,
        artifact: null,
        follow_ups: [],
      },
    });

    expect(view.filters).toEqual([
      expect.objectContaining({ value: "all", count: 4 }),
      expect.objectContaining({ value: "needs_action", count: 1 }),
      expect.objectContaining({ value: "in_progress", count: 0 }),
      expect.objectContaining({ value: "monitoring", count: 1 }),
      expect.objectContaining({ value: "ended", count: 2 }),
    ]);
    expect(view.selected).toMatchObject({
      id: ACTION_ID,
      title: "创建延迟履约率跟踪",
      caseTitle: "履约延迟异常",
      statusLabel: "待执行",
      riskLabel: "中风险",
      policyLabel: "策略 L2",
      policyDispositionLabel: "允许执行",
      approvalLabel: "无需审批",
      canExecute: true,
      canRollback: false,
      canApprove: false,
      canReject: false,
      evidenceSummary: "引用 2 条证据和 1 个工作假设",
      executionToolLabel: "internal_metric_monitor.create",
      rollback: {
        strategy: "停用本次指标跟踪",
        trigger: "发现配置错误或监控对象不一致时",
        verification: "确认跟踪任务已停用且不再产生新检查记录",
      },
    });
    expect(view.selected?.planRows).toEqual([
      { label: "行动类型", value: "指标跟踪" },
      { label: "监控指标", value: "延迟履约率" },
      { label: "判断条件", value: "小于或等于 4.8%" },
      { label: "检查频率", value: "每 24 小时" },
      { label: "复评时间", value: "7 天后" },
    ]);
    expect(JSON.stringify(view)).not.toContain("改善了");
    expect(view.selected?.hypothesisSummary).toContain("不能单独证明因果关系");
    expect(JSON.stringify(view)).not.toContain("证明了因果");
  });

  test("keeps approval-gated work non-executable until the required actors approve", () => {
    const record = actionRecord({
      kind: "external_mutation",
      status: "awaiting_approval",
      riskLevel: "high",
      policyLevel: "L4",
      disposition: "approval_required",
    });
    const approvalId = "apr_0123456789abcdef0123456789abcdef";
    record.action.approval = {
      required: true,
      status: "pending",
      approval_id: approvalId,
      reason: "Policy L4 requires human approval",
    };
    record.decision.action = record.action;
    record.decision.required_approvals = 2;
    record.decision.execution_tool =
      "connector:merchant_ads:update_campaign_budget";
    const view = buildCommerceActionCenterViewModel({
      cases: [commerceCase(CASE_ID, "履约延迟异常", "high")],
      records: [record],
      selectedActionId: record.action.id,
      selectedDetail: {
        record,
        approval: {
          schema_version: "commerce.approval-request@1.0.0",
          id: approvalId,
          workspace_id: WORKSPACE_ID,
          case_id: CASE_ID,
          action_id: record.action.id,
          required_approvals: 2,
          status: "pending",
          approved_actor_ids: [],
          rejected_actor_id: null,
          modified_by_actor_id: null,
          replacement_draft_sha256: null,
          created_at: "2026-07-20T02:42:41Z",
          updated_at: "2026-07-20T02:42:41Z",
          version: 1,
        },
        artifact: null,
        follow_ups: [],
      },
    });

    expect(view.selected).toMatchObject({
      statusLabel: "等待审批",
      approvalLabel: "等待审批",
      policyDispositionLabel: "审批后可执行",
      approvalProgressLabel: "已批准 0 / 2",
      canApprove: true,
      canReject: true,
      canExecute: false,
      primaryActionLabel: "批准行动",
    });
  });
});

function commerceCase(
  id: string,
  title: string,
  severity: CommerceCase["severity"],
): CommerceCase {
  return {
    id,
    workspace_id: WORKSPACE_ID,
    title,
    severity,
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

function actionRecord(
  options: {
    id?: string;
    caseId?: string;
    kind?: CommerceActionParameters["kind"];
    status?: CommerceActionRecord["action"]["status"];
    title?: string;
    policyLevel?: CommerceActionRecord["decision"]["level"];
    riskLevel?: CommerceActionRecord["action"]["risk_level"];
    disposition?: CommerceActionRecord["decision"]["disposition"];
  } = {},
): CommerceActionRecord {
  const id = options.id ?? ACTION_ID;
  const caseId = options.caseId ?? CASE_ID;
  const title = options.title ?? "Monitor late-delivery recovery";
  const kind = options.kind ?? "create_metric_monitor";
  const status = options.status ?? "policy_checked";
  const riskLevel = options.riskLevel ?? "medium";
  const rollbackPlan = {
    strategy: "停用本次指标跟踪",
    trigger: "发现配置错误或监控对象不一致时",
    verification: "确认跟踪任务已停用且不再产生新检查记录",
  };
  let parameters: CommerceActionParameters;
  if (kind === "create_metric_monitor") {
    parameters = {
      kind,
      metric_name: "late_delivery_rate",
      metric_observation_ids: ["mobs_0123456789abcdef0123456789abcdef"],
      comparison: "less_than_or_equal",
      threshold: "0.048",
      cadence_hours: 24,
      follow_up_after_days: 7,
    };
  } else if (kind === "request_missing_data") {
    parameters = { kind, missing_fields: ["review.score"], due_days: 7 };
  } else if (kind === "export_audit_cohort") {
    parameters = {
      kind,
      format: "csv",
      max_rows: 1000,
      include_direct_identifiers: false,
    };
  } else if (kind === "external_mutation") {
    parameters = {
      kind,
      connector_id: "merchant_ads",
      operation: "update_campaign_budget",
      target_ref_sha256: "c".repeat(64),
      reversible: false,
      dry_run: false,
    };
  } else if (kind === "create_internal_task") {
    parameters = {
      kind,
      owner_role: "履约运营",
      due_days: 7,
      checklist: ["复核问题订单"],
    };
  } else {
    parameters = { kind, reason: "No safe operation is available" };
  }
  const action: CommerceActionRecord["action"] = {
    id,
    workspace_id: WORKSPACE_ID,
    case_id: caseId,
    title,
    description: "Create a reversible internal metric monitor.",
    status,
    evidence_ids: [
      "evd_0123456789abcdef0123456789abcdef",
      "evd_1123456789abcdef0123456789abcdef",
    ],
    risk_level: riskLevel,
    approval: {
      required: false,
      status: "not_required",
      approval_id: null,
      reason: "Internal reversible Action is below the approval threshold",
    },
    rollback_plan: rollbackPlan,
  };
  const draft = {
    schema_version: "commerce.action-draft@1.0.0",
    id,
    workspace_id: WORKSPACE_ID,
    case_id: caseId,
    title,
    description: action.description,
    evidence_ids: action.evidence_ids,
    hypothesis_ids: ["hyp_0123456789abcdef0123456789abcdef"],
    expected_signal_metric_ids: ["mobs_0123456789abcdef0123456789abcdef"],
    parameters,
    rollback_plan: rollbackPlan,
  };
  return {
    action,
    decision: {
      schema_version: "commerce.action-policy-decision@1.0.0",
      validated: {
        schema_version: "commerce.validated-action@1.0.0",
        draft,
        validation_sha256: "a".repeat(64),
      },
      level: options.policyLevel ?? "L2",
      disposition: options.disposition ?? "auto_execute",
      reason_codes: ["reversible_internal_operation"],
      required_approvals: 0,
      execution_tool:
        kind === "create_metric_monitor"
          ? "internal_metric_monitor.create"
          : null,
      action,
    },
    created_at: "2026-07-20T02:32:41Z",
    updated_at: "2026-07-20T02:42:41Z",
    version: 1,
  };
}
