import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceMasterShellView } from "@/components/commerce/master-shell";
import {
  buildCommerceShellViewModel,
  type CommerceWorkspaceSnapshot,
} from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CASE_ID = "case_0123456789abcdef0123456789abcdef";
const RUN_ID = "run_0123456789abcdef0123456789abcdef";

describe("CommerceMasterShellView", () => {
  test("renders the approved Chinese Codex-inspired information hierarchy", () => {
    const markup = renderToStaticMarkup(
      createElement(CommerceMasterShellView, {
        viewModel: buildCommerceShellViewModel(readySnapshot()),
        isRefreshing: false,
        onRefresh: () => undefined,
        onSelectCase: () => undefined,
      }),
    );
    const text = visibleText(markup);

    for (const label of [
      "电商经营诊断",
      "新建诊断",
      "数据接入",
      "案例队列",
      "行动中心",
      "更多",
      "案例详情",
      "发生了什么",
      "当前判断",
      "证据边界",
      "下一步",
      "调查记录",
      "检查面板",
      "延迟履约率",
      "+31.6 个百分点",
      "审查承运商服务等级与超时订单分布",
    ]) {
      expect(text).toContain(label);
    }
    for (const forbidden of [
      "Case",
      "Evidence",
      "Action",
      "Agent runtime",
      "deepseek-v4-flash",
      "深度求索 V4",
      "子智能体",
      "租约已释放",
    ]) {
      expect(text).not.toContain(forbidden);
    }
  });

  test("renders the honest empty state without a fake running Agent", () => {
    const viewModel = buildCommerceShellViewModel({
      workspaceId: WORKSPACE_ID,
      cases: [],
      selectedCase: null,
      events: [],
      runs: [],
    });
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceMasterShellView, {
          viewModel,
          isRefreshing: false,
          onRefresh: () => undefined,
          onSelectCase: () => undefined,
        }),
      ),
    );

    expect(text).toContain("还没有经营案例");
    expect(text).toContain("当前没有运行中的调查");
    expect(text).not.toContain("正在思考");
    expect(text).not.toContain("正在运行子智能体");
  });
});

function readySnapshot(): CommerceWorkspaceSnapshot {
  const commerceCase = {
    id: CASE_ID,
    workspace_id: WORKSPACE_ID,
    title: "Deterministic anomaly for seller seller-4869",
    severity: "high",
    status: "investigating",
    summary: null,
    evidence_ids: ["evd_0123456789abcdef0123456789abcdef"],
    hypothesis_ids: [],
    action_ids: ["act_0123456789abcdef0123456789abcdef"],
    opened_at: "2026-07-20T02:32:41Z",
    updated_at: "2026-07-20T02:33:27Z",
    version: 2,
  };
  return {
    workspaceId: WORKSPACE_ID,
    cases: [commerceCase],
    selectedCase: {
      case: commerceCase,
      lineage: {
        schema_version: "1.0.0",
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        dataset_id: "dset_0123456789abcdef0123456789abcdef",
        seller_entity_id: "ent_0123456789abcdef0123456789abcdef",
        seller_external_key: "seller-4869",
        baseline_start: "2026-05-01T00:00:00Z",
        baseline_end: "2026-05-07T23:59:59Z",
        current_start: "2026-05-08T00:00:00Z",
        current_end: "2026-05-14T23:59:59Z",
        anomaly_ids: ["anom_0123456789abcdef0123456789abcdef"],
        metric_observation_ids: [
          "mobs_0123456789abcdef0123456789abcde1",
          "mobs_0123456789abcdef0123456789abcde2",
        ],
        analysis_artifact_relative_path: "analysis/case.json",
        analysis_artifact_sha256: "a".repeat(64),
        created_at: "2026-07-20T02:32:41Z",
      },
      evidence: [
        {
          id: "evd_0123456789abcdef0123456789abcdef",
          workspace_id: WORKSPACE_ID,
          case_id: CASE_ID,
          summary: "Late delivery rate increased.",
          relation: "supports",
          semantic_status: "observed",
          confidence: 0.98,
          fact_ids: [],
          metric_observation_ids: [
            "mobs_0123456789abcdef0123456789abcde1",
            "mobs_0123456789abcdef0123456789abcde2",
          ],
        },
      ],
      hypotheses: [],
      analysis: {
        status: "available",
        unavailable_reason: null,
        baseline_metrics: [
          metric(
            "mobs_0123456789abcdef0123456789abcde1",
            "0.048",
            "2026-05-01T00:00:00Z",
            "2026-05-08T00:00:00Z",
          ),
        ],
        current_metrics: [
          metric(
            "mobs_0123456789abcdef0123456789abcde2",
            "0.364",
            "2026-05-08T00:00:00Z",
            "2026-05-15T00:00:00Z",
          ),
        ],
        anomalies: [
          {
            id: "anom_0123456789abcdef0123456789abcdef",
            metric_name: "late_delivery_rate",
            baseline_observation_id: "mobs_0123456789abcdef0123456789abcde1",
            current_observation_id: "mobs_0123456789abcdef0123456789abcde2",
            baseline_value: "0.048",
            current_value: "0.364",
            absolute_change: "0.316",
            relative_change: "6.5833333333",
            direction: "increase",
            severity: "high",
            confidence: 0.98,
            baseline_sample_size: 125,
            current_sample_size: 132,
            sample_adequate: true,
            reason: "Current rate crossed the deterministic threshold.",
          },
        ],
      },
      actions: [
        {
          id: "act_0123456789abcdef0123456789abcdef",
          title: "Review carrier service levels and late orders",
          description: "Create a bounded internal review task.",
          kind: "create_internal_task",
          status: "policy_checked",
          risk_level: "low",
          policy_level: "auto_allowed",
          approval_required: false,
          approval_status: "not_required",
          evidence_ids: ["evd_0123456789abcdef0123456789abcdef"],
          created_at: "2026-07-20T02:33:20Z",
          updated_at: "2026-07-20T02:33:20Z",
          version: 1,
        },
      ],
    },
    events: [
      {
        id: "evt_0123456789abcdef0123456789abcdef",
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        run_id: RUN_ID,
        event_type: "path.completed",
        schema_version: "1.0.0",
        case_sequence: 1,
        run_sequence: 1,
        occurred_at: "2026-07-20T02:33:02Z",
        recorded_at: "2026-07-20T02:33:02Z",
        trace_id: "trace_0123456789abcdef0123456789abcdef",
        correlation_id: "corr_0123456789abcdef0123456789abcdef",
        causation_event_id: null,
        actor: "agent",
        payload: { path_type: "fulfillment" },
      },
      {
        id: "evt_1123456789abcdef0123456789abcdef",
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        run_id: RUN_ID,
        event_type: "verification.completed",
        schema_version: "1.0.0",
        case_sequence: 2,
        run_sequence: 2,
        occurred_at: "2026-07-20T02:33:27Z",
        recorded_at: "2026-07-20T02:33:27Z",
        trace_id: "trace_0123456789abcdef0123456789abcdef",
        correlation_id: "corr_0123456789abcdef0123456789abcdef",
        causation_event_id: null,
        actor: "agent",
        payload: {
          actual_model_identity: "deepseek-v4-flash",
          retry_count: 0,
        },
      },
      {
        id: "evt_2123456789abcdef0123456789abcdef",
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        run_id: RUN_ID,
        event_type: "run.lease_released",
        schema_version: "1.0.0",
        case_sequence: 3,
        run_sequence: 3,
        occurred_at: "2026-07-20T02:33:30Z",
        recorded_at: "2026-07-20T02:33:30Z",
        trace_id: "trace_0123456789abcdef0123456789abcdef",
        correlation_id: "corr_0123456789abcdef0123456789abcdef",
        causation_event_id: null,
        actor: "system",
        payload: {},
      },
    ],
    runs: [
      {
        id: RUN_ID,
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        run_type: "case_investigation",
        status: "completed",
        phase: "terminal",
        goal: "Investigate the anomaly.",
        parent_run_id: null,
        subject_action_id: null,
        action_operation: null,
        requested_paths: ["fulfillment"],
        wait_reason: null,
        stop_reason: "goal_achieved",
        created_at: "2026-07-20T02:32:45Z",
        started_at: "2026-07-20T02:32:50Z",
        ended_at: "2026-07-20T02:33:30Z",
        updated_at: "2026-07-20T02:33:30Z",
        version: 3,
      },
    ],
  };
}

function metric(id: string, value: string, start: string, end: string) {
  return {
    id,
    metric_name: "late_delivery_rate",
    semantic_status: "derived",
    value,
    unit: "ratio",
    formula_version: "late_delivery_rate@1.0.0",
    window_start: start,
    window_end: end,
    sample_size: 100,
    numerator: null,
    denominator: null,
    source_fact_count: 100,
    unknown_reason: null,
  };
}

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
