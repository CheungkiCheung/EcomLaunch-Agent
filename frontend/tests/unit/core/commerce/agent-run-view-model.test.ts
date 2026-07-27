import { describe, expect, test } from "vitest";

import { buildCommerceAgentRunViewModel } from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CASE_ID = "case_0123456789abcdef0123456789abcdef";
const RUN_ID = "run_0123456789abcdef0123456789abcdef";

describe("buildCommerceAgentRunViewModel", () => {
  test("projects persisted fan-out barrier verification telemetry and checkpoint state", () => {
    const run = commerceRun();
    const view = buildCommerceAgentRunViewModel({
      cases: [commerceCase()],
      runs: [run],
      selectedRunId: RUN_ID,
      selectedDetail: { run, latest_checkpoint: checkpoint() },
      events: runEvents(),
      checkpoints: [checkpoint()],
    });

    expect(view.filters).toEqual([
      expect.objectContaining({ value: "all", count: 1 }),
      expect.objectContaining({ value: "running", count: 0 }),
      expect.objectContaining({ value: "waiting", count: 0 }),
      expect.objectContaining({ value: "completed", count: 1 }),
      expect.objectContaining({ value: "failed", count: 0 }),
    ]);
    expect(view.selected).toMatchObject({
      id: RUN_ID,
      title: "调查履约延迟原因",
      caseTitle: "履约延迟异常",
      statusLabel: "已完成",
      typeLabel: "案例调查",
      stopReasonLabel: "目标已满足",
      durationLabel: "12.6 秒",
      telemetry: {
        modelIdentityLabel: "deepseek-v4-flash",
        requestCountLabel: "5 个唯一 ID",
        tokenLabel: "18,420",
        latencyLabel: "12.6 秒",
        retryLabel: "0",
        stopReasonLabel: "stop",
      },
      checkpoint: {
        sequenceLabel: "7",
        iterationLabel: "1",
        evidenceLabel: "4",
        hypothesisLabel: "1",
        contextLabel: "已记录",
      },
      selectedStageTitle: "新鲜上下文验证",
      selectedStageDescription:
        "验证器不继承主智能体的完整推理历史，只读取最小可审计上下文。",
    });
    expect(view.selected?.stages.map((item) => item.title)).toEqual([
      "目标",
      "能力路由",
      "并行路径",
      "证据屏障",
      "主智能体综合",
      "新鲜上下文验证",
      "停止",
    ]);
    const fanout = view.selected?.stages[2];
    expect(fanout?.kind).toBe("fanout");
    expect(fanout?.paths).toEqual([
      expect.objectContaining({
        label: "履约路径",
        evidenceCountLabel: "2 条证据",
      }),
      expect.objectContaining({
        label: "卖家对标",
        evidenceCountLabel: "1 条证据",
      }),
      expect.objectContaining({
        label: "评价体验",
        evidenceCountLabel: "1 条证据",
      }),
    ]);
    expect(view.selected?.stages[3]).toMatchObject({
      title: "证据屏障",
      status: "completed",
      derivationLabel: "由全部路径终态与主智能体启动事件确认",
    });
    expect(view.selected?.budget).toEqual([
      expect.objectContaining({ label: "循环", valueLabel: "1 / 8" }),
      expect.objectContaining({ label: "工具", valueLabel: "6 / 20" }),
      expect.objectContaining({ label: "路径", valueLabel: "3 / 3" }),
      expect.objectContaining({
        label: "令牌",
        valueLabel: "18,420 / 32,000",
      }),
    ]);
    expect(JSON.stringify(view)).not.toContain("正在思考");
    expect(JSON.stringify(view)).not.toContain("推理过程");
  });

  test("keeps missing model telemetry explicitly unobserved", () => {
    const run = commerceRun();
    const view = buildCommerceAgentRunViewModel({
      cases: [commerceCase()],
      runs: [run],
      selectedRunId: RUN_ID,
      selectedDetail: { run, latest_checkpoint: null },
      events: runEvents().map((item) => ({ ...item, payload: {} })),
      checkpoints: [],
    });

    expect(view.selected?.telemetry).toMatchObject({
      modelIdentityLabel: "未观察",
      requestCountLabel: "未观察",
      tokenLabel: "未观察",
      latencyLabel: "未观察",
      retryLabel: "未观察",
      stopReasonLabel: "未观察",
    });
  });
});

function commerceCase() {
  return {
    id: CASE_ID,
    workspace_id: WORKSPACE_ID,
    title: "Deterministic anomaly for seller fulfillment-4869",
    severity: "high",
    status: "investigating",
    summary: "延迟履约率显著上升，当前案例正在调查。",
    evidence_ids: [],
    hypothesis_ids: [],
    action_ids: [],
    opened_at: "2026-07-20T10:33:00Z",
    updated_at: "2026-07-20T10:34:00Z",
    version: 1,
  };
}

function commerceRun() {
  return {
    id: RUN_ID,
    workspace_id: WORKSPACE_ID,
    case_id: CASE_ID,
    run_type: "case_investigation",
    status: "completed",
    phase: "verifying",
    goal: "Explain the fulfillment delay with traceable evidence",
    parent_run_id: null,
    subject_action_id: null,
    action_operation: null,
    requested_paths: ["fulfillment", "seller_peer", "review_experience"],
    wait_reason: null,
    stop_reason: "goal_achieved",
    created_at: "2026-07-20T10:33:00Z",
    started_at: "2026-07-20T10:33:10Z",
    ended_at: "2026-07-20T10:33:22.600Z",
    updated_at: "2026-07-20T10:33:22.600Z",
    version: 4,
  };
}

function runEvents() {
  return [
    event(1, "run.created", {}),
    event(2, "path.started", { path_type: "fulfillment" }),
    event(3, "path.started", { path_type: "seller_peer" }),
    event(4, "path.started", { path_type: "review_experience" }),
    event(
      5,
      "path.completed",
      telemetry("req-path-a", 4200, 3100, 0, {
        path_type: "fulfillment",
        evidence_ids: ["evd_1", "evd_2"],
        provider_request_ids: ["req-path-a"],
      }),
    ),
    event(
      6,
      "path.completed",
      telemetry("req-path-b", 3600, 2600, 0, {
        path_type: "seller_peer",
        evidence_ids: ["evd_3"],
        provider_request_ids: ["req-path-b"],
      }),
    ),
    event(
      7,
      "path.completed",
      telemetry("req-path-c", 3200, 2200, 0, {
        path_type: "review_experience",
        evidence_ids: ["evd_4"],
        provider_request_ids: ["req-path-c"],
      }),
    ),
    event(8, "lead.started", {}),
    event(
      9,
      "lead.completed",
      telemetry("req-lead", 4400, 3000, 0, {
        provider_request_ids: ["req-lead"],
        model_call_count: 1,
        claim_count: 1,
      }),
    ),
    event(10, "verification.started", {}),
    event(
      11,
      "verification.completed",
      telemetry("req-verify", 3020, 1700, 0, {
        accepted: true,
      }),
    ),
    event(12, "run.lease_released", {}),
  ];
}

function telemetry(
  requestId: string,
  totalTokens: number,
  latencyMs: number,
  retryCount: number,
  extra: Record<string, unknown>,
) {
  return {
    provider_request_id: requestId,
    actual_model_identity: "deepseek-v4-flash",
    total_tokens: totalTokens,
    latency_ms: latencyMs,
    retry_count: retryCount,
    stop_reason: "stop",
    ...extra,
  };
}

function event(
  sequence: number,
  eventType: string,
  payload: Record<string, unknown>,
) {
  return {
    id: `evt_${String(sequence).padStart(32, "0")}`,
    workspace_id: WORKSPACE_ID,
    case_id: CASE_ID,
    run_id: RUN_ID,
    event_type: eventType,
    schema_version: "1.0.0",
    case_sequence: sequence,
    run_sequence: sequence,
    occurred_at: `2026-07-20T10:33:${String(sequence).padStart(2, "0")}Z`,
    recorded_at: `2026-07-20T10:33:${String(sequence).padStart(2, "0")}Z`,
    trace_id: "trace_0123456789abcdef0123456789abcdef",
    correlation_id: "corr_0123456789abcdef0123456789abcdef",
    causation_event_id: null,
    actor: "agent",
    payload,
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
      goal: "Explain the fulfillment delay with traceable evidence",
      loop_iteration: 1,
      budget_snapshot: {
        limit: {
          max_iterations: 8,
          max_tool_calls: 20,
          max_path_agents: 3,
          max_tokens: 32000,
          max_wall_time_seconds: 300,
          max_model_escalations: 1,
          max_verification_repairs: 2,
          max_repeated_actions: 2,
          max_consecutive_no_new_evidence: 2,
        },
        usage: {
          iterations: 1,
          tool_calls: 6,
          path_agents: 3,
          tokens: 18420,
          wall_time_seconds: 12.6,
          model_escalations: 0,
          verification_repairs: 0,
          repeated_actions: 0,
          consecutive_no_new_evidence: 0,
        },
      },
      evidence_ids: ["evd_1", "evd_2", "evd_3", "evd_4"],
      hypothesis_ids: ["hyp_1"],
      active_path_task_ids: [],
      model_assignments: [],
      skill_versions: [
        { skill_id: "commerce.lead-synthesis", version: "1.0.0" },
      ],
      context_sha256: "a".repeat(64),
      tool_state: [],
      wait_reason: null,
      resume_token_sha256: null,
    },
    created_at: "2026-07-20T10:33:22.600Z",
  };
}
