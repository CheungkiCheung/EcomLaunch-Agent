import { describe, expect, test } from "vitest";

import {
  buildCommerceShellViewModel,
  type CommerceWorkspaceSnapshot,
} from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CASE_ID = "case_0123456789abcdef0123456789abcdef";
const RUN_ID = "run_0123456789abcdef0123456789abcdef";

function readySnapshot(): CommerceWorkspaceSnapshot {
  return {
    workspaceId: WORKSPACE_ID,
    cases: [
      {
        id: CASE_ID,
        workspace_id: WORKSPACE_ID,
        title: "Deterministic anomaly for seller seller-4869",
        severity: "high",
        status: "investigating",
        summary: "Late delivery rate increased in the current window.",
        evidence_ids: ["evd_0123456789abcdef0123456789abcdef"],
        hypothesis_ids: ["hyp_0123456789abcdef0123456789abcdef"],
        action_ids: ["act_0123456789abcdef0123456789abcdef"],
        opened_at: "2026-07-20T02:32:41Z",
        updated_at: "2026-07-20T02:33:27Z",
        version: 3,
      },
    ],
    selectedCase: {
      case: {
        id: CASE_ID,
        workspace_id: WORKSPACE_ID,
        title: "Deterministic anomaly for seller seller-4869",
        severity: "high",
        status: "investigating",
        summary: "Late delivery rate increased in the current window.",
        evidence_ids: ["evd_0123456789abcdef0123456789abcdef"],
        hypothesis_ids: ["hyp_0123456789abcdef0123456789abcdef"],
        action_ids: ["act_0123456789abcdef0123456789abcdef"],
        opened_at: "2026-07-20T02:32:41Z",
        updated_at: "2026-07-20T02:33:27Z",
        version: 3,
      },
      lineage: {
        schema_version: "1.0.0",
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        dataset_id: "dset_0123456789abcdef0123456789abcdef",
        seller_entity_id: "ent_0123456789abcdef0123456789abcdef",
        seller_external_key: "0f0f0f0f0f0f0f0f0f0f0f0f0f0f4869",
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
          summary: "Late delivery rate increased by 31.6 percentage points.",
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
      hypotheses: [
        {
          id: "hyp_0123456789abcdef0123456789abcdef",
          workspace_id: WORKSPACE_ID,
          case_id: CASE_ID,
          statement: "Carrier performance may explain the delay.",
          status: "supported",
          confidence: 0.81,
          supporting_evidence_ids: ["evd_0123456789abcdef0123456789abcdef"],
          contradicting_evidence_ids: [],
          version: 1,
        },
      ],
      analysis: {
        status: "available",
        unavailable_reason: null,
        baseline_metrics: [
          {
            id: "mobs_0123456789abcdef0123456789abcde1",
            metric_name: "late_delivery_rate",
            semantic_status: "derived",
            value: "0.048",
            unit: "ratio",
            formula_version: "late_delivery_rate@1.0.0",
            window_start: "2026-05-01T00:00:00",
            window_end: "2026-05-08T00:00:00",
            sample_size: 125,
            numerator: "6",
            denominator: "125",
            source_fact_count: 125,
            unknown_reason: null,
          },
        ],
        current_metrics: [
          {
            id: "mobs_0123456789abcdef0123456789abcde2",
            metric_name: "late_delivery_rate",
            semantic_status: "derived",
            value: "0.364",
            unit: "ratio",
            formula_version: "late_delivery_rate@1.0.0",
            window_start: "2026-05-08T00:00:00",
            window_end: "2026-05-15T00:00:00",
            sample_size: 132,
            numerator: "48",
            denominator: "132",
            source_fact_count: 132,
            unknown_reason: null,
          },
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
      event({
        id: "evt_00000000000000000000000000000005",
        event_type: "verification.completed",
        case_sequence: 5,
        run_sequence: 5,
        occurred_at: "2026-07-20T02:33:27Z",
        payload: {
          actual_model_identity: "deepseek-v4-flash",
          retry_count: 0,
          overall_verdict: "passed",
        },
      }),
      event({
        id: "evt_00000000000000000000000000000002",
        event_type: "run.created",
        case_sequence: 2,
        run_sequence: 1,
        occurred_at: "2026-07-20T02:32:45Z",
        payload: { status: "queued", requested_paths: ["fulfillment"] },
      }),
      event({
        id: "evt_00000000000000000000000000000004",
        event_type: "path.completed",
        case_sequence: 4,
        run_sequence: 4,
        occurred_at: "2026-07-20T02:33:02Z",
        payload: { path_type: "fulfillment" },
      }),
      event({
        id: "evt_00000000000000000000000000000001",
        event_type: "case.created",
        case_sequence: 1,
        run_sequence: null,
        occurred_at: "2026-07-20T02:32:41Z",
        payload: {},
      }),
      event({
        id: "evt_00000000000000000000000000000003",
        event_type: "path.started",
        case_sequence: 3,
        run_sequence: 3,
        occurred_at: "2026-07-20T02:32:50Z",
        payload: { path_type: "fulfillment" },
      }),
      event({
        id: "evt_00000000000000000000000000000006",
        event_type: "run.lease_released",
        case_sequence: 6,
        run_sequence: 6,
        occurred_at: "2026-07-20T02:33:30Z",
        payload: {},
      }),
    ],
    runs: [
      {
        id: RUN_ID,
        workspace_id: WORKSPACE_ID,
        case_id: CASE_ID,
        run_type: "case_investigation",
        status: "completed",
        phase: "terminal",
        goal: "Investigate the deterministic anomaly.",
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
        version: 4,
      },
    ],
  };
}

function event(
  overrides: Partial<CommerceWorkspaceSnapshot["events"][number]>,
): CommerceWorkspaceSnapshot["events"][number] {
  return {
    id: "evt_0123456789abcdef0123456789abcdef",
    workspace_id: WORKSPACE_ID,
    case_id: CASE_ID,
    run_id: RUN_ID,
    event_type: "case.created",
    schema_version: "1.0.0",
    case_sequence: 1,
    run_sequence: null,
    occurred_at: "2026-07-20T02:32:41Z",
    recorded_at: "2026-07-20T02:32:41Z",
    trace_id: "trace_0123456789abcdef0123456789abcdef",
    correlation_id: "corr_0123456789abcdef0123456789abcdef",
    causation_event_id: null,
    actor: "system",
    payload: {},
    ...overrides,
  };
}

describe("buildCommerceShellViewModel", () => {
  test("projects an English backend case into a Chinese Case-first shell", () => {
    const view = buildCommerceShellViewModel(readySnapshot());

    expect(view.status).toBe("ready");
    expect(view.activeCase?.title).toBe("履约延迟异常");
    expect(view.activeCase?.sellerLabel).toBe("卖家 4869");
    expect(view.activeCase?.severityLabel).toBe("高风险");
    expect(view.activeCase?.statusLabel).toBe("调查中");
    expect(view.activeCase?.overview.comparison).toMatchObject({
      metricLabel: "延迟履约率",
      baselineValueLabel: "4.8%",
      currentValueLabel: "36.4%",
      changeLabel: "+31.6 个百分点",
    });
    expect(view.activeCase?.overview.periodLabel).toBe("5月8日—5月14日");
    expect(view.activeCase?.overview.conclusion.verificationLabel).toBe(
      "独立验证通过，保留因果限制",
    );
    expect(view.activeCase?.overview.evidenceBoundary).toMatchObject({
      verifiedCount: 1,
      supportingCount: 1,
      primaryEvidenceId: "evd_0123456789abcdef0123456789abcdef",
    });
    expect(view.activeCase?.overview.action).toMatchObject({
      title: "审查承运商服务等级与超时订单分布",
      statusLabel: "尚未执行",
      available: true,
    });
    expect(view.activeCase?.overview.evidenceInspector).toMatchObject({
      title: "延迟履约率变化",
      relationLabel: "支持",
      sourceLabel: "订单履约数据",
      formulaLabel: "延迟订单数 / 已履约订单数",
    });
    expect(view.activeCase?.evidence[0]?.summary).toBe("发现可追溯的指标变化");
    expect(view.runtime.modelLabel).toBe("深度求索 V4");
    expect(view.runtime.retryLabel).toBe("未重试");
    expect(view.runtime.leaseLabel).toBe("租约已释放");
    expect(JSON.stringify(view)).not.toContain("Late delivery");
    expect(JSON.stringify(view)).not.toContain("Carrier performance");
  });

  test("orders out-of-order Domain Events by authoritative sequence", () => {
    const view = buildCommerceShellViewModel(readySnapshot());

    expect(view.timeline.wasReordered).toBe(true);
    expect(view.timeline.items.map((item) => item.title)).toEqual([
      "案例已创建",
      "调查已开始",
      "履约分析已开始",
      "履约分析已完成",
      "独立验证完成",
      "运行资源已释放",
    ]);
  });

  test("uses the primary deterministic metric when no Path has run yet", () => {
    const snapshot = readySnapshot();
    snapshot.events = snapshot.events.filter(
      (item) => !item.event_type.startsWith("path."),
    );

    const view = buildCommerceShellViewModel(snapshot);

    expect(view.activeCase?.title).toBe("履约延迟异常");
    expect(view.navigation.cases[0]?.title).toBe("履约延迟异常");
  });

  test("does not label an explicit user Case as an anomaly when no signal exists", () => {
    const snapshot = readySnapshot();
    const explicitTitle = "User-requested investigation for seller seller-4869";
    snapshot.cases[0]!.title = explicitTitle;
    snapshot.cases[0]!.status = "new";
    snapshot.selectedCase!.case.title = explicitTitle;
    snapshot.selectedCase!.case.status = "new";
    snapshot.selectedCase!.analysis.anomalies = [];
    snapshot.events = snapshot.events.filter(
      (item) => item.event_type === "case.created",
    );
    snapshot.runs = [];

    const view = buildCommerceShellViewModel(snapshot);

    expect(view.activeCase?.title).toBe("用户发起的履约诊断");
    expect(view.navigation.cases[0]?.title).toBe("用户发起的履约诊断");
    expect(view.activeCase?.title).not.toContain("异常");
  });

  test("keeps source-local analysis dates stable in the operator timezone", () => {
    const originalTimezone = process.env.TZ;
    process.env.TZ = "Asia/Shanghai";
    try {
      const view = buildCommerceShellViewModel(readySnapshot());

      expect(view.activeCase?.overview.periodLabel).toBe("5月8日—5月14日");
    } finally {
      process.env.TZ = originalTimezone;
    }
  });

  test("renders an explicit Chinese fallback for an unknown event", () => {
    const snapshot = readySnapshot();
    snapshot.events.push(
      event({
        id: "evt_00000000000000000000000000000007",
        event_type: "future.vendor_event",
        case_sequence: 7,
        occurred_at: "2026-07-20T02:33:31Z",
      }),
    );

    const view = buildCommerceShellViewModel(snapshot);
    const unknown = view.timeline.items.at(-1);

    expect(unknown?.kind).toBe("unknown");
    expect(unknown?.title).toBe("未知事件");
    expect(unknown?.description).toBe("收到暂不支持展示的结构化事件。");
    expect(`${unknown?.title}${unknown?.description}`).not.toContain("vendor");
  });

  test("shows an honest empty state without inventing Agent activity", () => {
    const view = buildCommerceShellViewModel({
      workspaceId: WORKSPACE_ID,
      cases: [],
      selectedCase: null,
      events: [],
      runs: [],
    });

    expect(view.status).toBe("empty");
    expect(view.emptyState).toEqual({
      title: "还没有经营案例",
      description:
        "接入电商数据后，系统会先检查数据能力，再创建可追溯的诊断案例。",
      actionLabel: "接入数据",
    });
    expect(view.subagents).toEqual([]);
    expect(view.timeline.items).toEqual([]);
    expect(view.runtime.stateLabel).toBe("当前没有运行中的调查");
  });
});
