import type {
  CommerceCase,
  CommerceDomainEvent,
  CommerceRun,
  CommerceRunCheckpoint,
} from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";
const CASE_ID = "case_0123456789abcdef0123456789abcdef";
const RUN_ID = "run_0123456789abcdef0123456789abcdef";

export function commerceWarRoomCase(): CommerceCase {
  return {
    id: CASE_ID,
    workspace_id: WORKSPACE_ID,
    title: "Deterministic anomaly for seller fulfillment-4869",
    severity: "high",
    status: "investigating",
    summary: "延迟履约率显著上升，当前案例正在调查。",
    evidence_ids: ["evd_1", "evd_2", "evd_3", "evd_4"],
    hypothesis_ids: ["hyp_1"],
    action_ids: [],
    opened_at: "2026-07-20T10:30:00Z",
    updated_at: "2026-07-20T10:34:18Z",
    version: 4,
  };
}

export function commerceWarRoomRun(): CommerceRun {
  return {
    id: RUN_ID,
    workspace_id: WORKSPACE_ID,
    case_id: CASE_ID,
    run_type: "case_investigation",
    status: "running",
    phase: "investigating",
    goal: "Explain the fulfillment delay with traceable evidence",
    parent_run_id: null,
    subject_action_id: null,
    action_operation: null,
    requested_paths: ["fulfillment", "seller_peer", "review_experience"],
    wait_reason: null,
    stop_reason: null,
    created_at: "2026-07-20T10:32:00Z",
    started_at: "2026-07-20T10:32:05Z",
    ended_at: null,
    updated_at: "2026-07-20T10:34:18Z",
    version: 8,
  };
}

export function commerceWarRoomEvents(): CommerceDomainEvent[] {
  return [
    event(1, "run.created", {}),
    event(2, "run.phase_changed", { phase: "investigating" }),
    event(3, "run.checkpoint_saved", { checkpoint_sequence: 1 }),
    event(4, "path.started", { path_type: "fulfillment" }),
    event(5, "evidence.appended", {
      evidence_id: "evd_1",
      relation: "supports",
    }),
    event(6, "evidence.appended", {
      evidence_id: "evd_2",
      relation: "supports",
    }),
    event(7, "path.completed", {
      path_type: "fulfillment",
      evidence_ids: ["evd_1", "evd_2"],
    }),
    event(8, "run.checkpoint_saved", { checkpoint_sequence: 4 }),
    event(9, "path.started", { path_type: "review_experience" }),
    event(10, "path.blocked", {
      path_type: "review_experience",
      reason: "missing_review_text",
    }),
    event(11, "evidence.appended", {
      evidence_id: "evd_3",
      relation: "contradicts",
    }),
    event(12, "evidence.appended", {
      evidence_id: "evd_4",
      relation: "context",
    }),
    event(13, "run.checkpoint_saved", { checkpoint_sequence: 6 }),
    event(14, "path.started", { path_type: "seller_peer" }),
    event(15, "run.updated", { version: 6 }),
    event(16, "run.checkpoint_saved", { checkpoint_sequence: 6 }),
    event(17, "run.status_changed", { status: "running" }),
    event(18, "run.checkpoint_saved", { checkpoint_sequence: 7 }),
  ];
}

export function commerceWarRoomCheckpoint(): CommerceRunCheckpoint {
  return {
    id: "chk_0123456789abcdef0123456789abcdef",
    sequence: 7,
    checkpoint: {
      schema_version: "commerce.goal-loop-checkpoint@1.0.0",
      workspace_id: WORKSPACE_ID,
      run_id: RUN_ID,
      case_id: CASE_ID,
      goal: "Explain the fulfillment delay with traceable evidence",
      loop_iteration: 2,
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
          iterations: 2,
          tool_calls: 7,
          path_agents: 2,
          tokens: 9200,
          wall_time_seconds: 138,
          model_escalations: 0,
          verification_repairs: 0,
          repeated_actions: 0,
          consecutive_no_new_evidence: 0,
        },
      },
      evidence_ids: ["evd_1", "evd_2", "evd_3", "evd_4"],
      hypothesis_ids: ["hyp_1"],
      active_path_task_ids: ["task_seller_peer"],
      model_assignments: [],
      skill_versions: [
        { skill_id: "commerce.lead-synthesis", version: "1.3.0" },
      ],
      context_sha256: "a".repeat(64),
      tool_state: [],
      wait_reason: null,
      resume_token_sha256: null,
    },
    created_at: "2026-07-20T10:34:18Z",
  };
}

function event(
  sequence: number,
  eventType: string,
  payload: Record<string, unknown>,
): CommerceDomainEvent {
  return {
    id: `evt_${String(sequence).padStart(32, "0")}`,
    workspace_id: WORKSPACE_ID,
    case_id: CASE_ID,
    run_id: RUN_ID,
    event_type: eventType,
    schema_version: "1.0.0",
    case_sequence: sequence,
    run_sequence: sequence,
    occurred_at: `2026-07-20T10:34:${String(sequence).padStart(2, "0")}Z`,
    recorded_at: `2026-07-20T10:34:${String(sequence).padStart(2, "0")}Z`,
    trace_id: "trace_0123456789abcdef0123456789abcdef",
    correlation_id: "corr_0123456789abcdef0123456789abcdef",
    causation_event_id: null,
    actor: "agent",
    payload,
  };
}
