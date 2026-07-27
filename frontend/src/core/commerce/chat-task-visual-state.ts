export type CommerceSubagentTaskStatus =
  | "queued"
  | "running"
  | "waiting"
  | "waiting_approval"
  | "blocked"
  | "completed"
  | "failed"
  | "cancelled"
  | "timed_out";

export interface CommerceSubagentTaskSnapshot {
  task_id: string;
  thread_id: string;
  run_id: string;
  parent_task_id: string | null;
  subagent_type: string;
  description: string;
  status: CommerceSubagentTaskStatus;
  context_packet?: {
    available_skills?: string[];
    available_tools?: string[];
    budget?: Record<string, unknown>;
  };
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface CommerceSubagentTaskEvent {
  id?: string;
  task_id: string;
  thread_id: string;
  run_id: string;
  seq: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export type CommerceTaskVisualStatus =
  | "queued"
  | "working"
  | "waiting"
  | "approval"
  | "blocked"
  | "completed"
  | "failed"
  | "cancelled"
  | "timed_out";

export type CommerceTaskVisualActivity =
  | "idle"
  | "dispatching"
  | "tool"
  | "message"
  | "waiting"
  | "blocked"
  | "completed"
  | "failed"
  | "cancelled"
  | "timed_out";

export interface CommerceTaskVisualState {
  taskId: string;
  profile: string;
  description: string;
  status: CommerceTaskVisualStatus;
  activity: CommerceTaskVisualActivity;
  latestToolName: string | null;
  latestMessagePreview: string | null;
  waitReason: string | null;
  lastEventSeq: number;
  availableSkills: string[];
  availableTools: string[];
  budget: Record<string, unknown>;
}

export interface CommerceTaskVisualReduction {
  state: CommerceTaskVisualState;
  appliedEventIds: string[];
  unknownEvents: Array<{ eventType: string; seq: number }>;
  wasReordered: boolean;
}

const STATUS_EVENTS: Record<string, CommerceSubagentTaskStatus> = {
  "task.created": "queued",
  "task.queued": "queued",
  "task.running": "running",
  "task.waiting": "waiting",
  "task.waiting_approval": "waiting_approval",
  "task.blocked": "blocked",
  "task.completed": "completed",
  "task.failed": "failed",
  "task.cancelled": "cancelled",
  "task.timed_out": "timed_out",
  "task.resumed": "running",
  "task.recovery_blocked": "blocked",
};

function visualStatus(
  status: CommerceSubagentTaskStatus,
): CommerceTaskVisualStatus {
  switch (status) {
    case "running":
      return "working";
    case "waiting":
      return "waiting";
    case "waiting_approval":
      return "approval";
    case "blocked":
      return "blocked";
    case "completed":
      return "completed";
    case "failed":
      return "failed";
    case "cancelled":
      return "cancelled";
    case "timed_out":
      return "timed_out";
    default:
      return "queued";
  }
}

function initialActivity(
  status: CommerceSubagentTaskStatus,
): CommerceTaskVisualActivity {
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  if (status === "cancelled") return "cancelled";
  if (status === "timed_out") return "timed_out";
  if (status === "blocked") return "blocked";
  if (["waiting", "waiting_approval"].includes(status)) return "waiting";
  return "idle";
}

function stringPayload(
  payload: Record<string, unknown>,
  key: string,
): string | null {
  const value = payload[key];
  return typeof value === "string" && value.trim() ? value : null;
}

const MESSAGE_PREVIEW_MAX_CHARS = 240;

function compactMessagePreview(
  payload: Record<string, unknown>,
): string | null {
  const raw = stringPayload(payload, "content_preview");
  if (!raw) return null;
  const normalized = raw
    .replace(/[`*_#|>-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) return null;
  if (normalized.length <= MESSAGE_PREVIEW_MAX_CHARS) return normalized;
  return `${normalized.slice(0, MESSAGE_PREVIEW_MAX_CHARS - 1).trimEnd()}…`;
}

function applyStatus(
  state: CommerceTaskVisualState,
  status: CommerceSubagentTaskStatus,
  payload: Record<string, unknown>,
): CommerceTaskVisualState {
  const nextStatus = visualStatus(status);
  return {
    ...state,
    status: nextStatus,
    activity:
      nextStatus === "working" ? "dispatching" : initialActivity(status),
    waitReason: stringPayload(payload, "wait_reason") ?? state.waitReason,
  };
}

export function reduceCommerceTaskVisualState(
  snapshot: CommerceSubagentTaskSnapshot,
  events: CommerceSubagentTaskEvent[],
): CommerceTaskVisualReduction {
  const sorted = [...events].sort(
    (left, right) =>
      left.seq - right.seq || eventId(left).localeCompare(eventId(right)),
  );
  const wasReordered = sorted.some((event, index) => event !== events[index]);
  const initial: CommerceTaskVisualState = {
    taskId: snapshot.task_id,
    profile: snapshot.subagent_type,
    description: snapshot.description,
    status: visualStatus(snapshot.status),
    activity: initialActivity(snapshot.status),
    latestToolName: null,
    latestMessagePreview: null,
    waitReason: null,
    lastEventSeq: 0,
    availableSkills: [...(snapshot.context_packet?.available_skills ?? [])],
    availableTools: [...(snapshot.context_packet?.available_tools ?? [])],
    budget: { ...(snapshot.context_packet?.budget ?? {}) },
  };
  const appliedEventIds: string[] = [];
  const unknownEvents: Array<{ eventType: string; seq: number }> = [];
  const seenSequences = new Set<number>();
  let state = initial;

  for (const event of sorted) {
    if (seenSequences.has(event.seq)) continue;
    seenSequences.add(event.seq);
    appliedEventIds.push(eventId(event));
    state = { ...state, lastEventSeq: event.seq };
    const nextStatus = STATUS_EVENTS[event.event_type];
    if (nextStatus) {
      state = applyStatus(state, nextStatus, event.payload);
      continue;
    }
    if (event.event_type === "task.tool_result") {
      state = {
        ...state,
        activity:
          state.status === "working"
            ? "tool"
            : stableActivityForStatus(state.status),
        latestToolName:
          stringPayload(event.payload, "tool_name") ?? state.latestToolName,
      };
      continue;
    }
    if (event.event_type === "task.message") {
      state = {
        ...state,
        activity:
          state.status === "working"
            ? "message"
            : stableActivityForStatus(state.status),
        latestMessagePreview:
          compactMessagePreview(event.payload) ?? state.latestMessagePreview,
      };
      continue;
    }
    if (
      ["task.lease_acquired", "task.lease_renewed"].includes(event.event_type)
    ) {
      state = {
        ...state,
        activity:
          state.status === "working"
            ? "dispatching"
            : stableActivityForStatus(state.status),
      };
      continue;
    }
    if (event.event_type === "task.lease_released") {
      state = {
        ...state,
        activity: stableActivityForStatus(state.status),
      };
      continue;
    }
    unknownEvents.push({ eventType: event.event_type, seq: event.seq });
  }

  return { state, appliedEventIds, unknownEvents, wasReordered };
}

function stableActivityForStatus(
  status: CommerceTaskVisualStatus,
): CommerceTaskVisualActivity {
  switch (status) {
    case "completed":
      return "completed";
    case "failed":
      return "failed";
    case "cancelled":
      return "cancelled";
    case "timed_out":
      return "timed_out";
    case "blocked":
      return "blocked";
    case "waiting":
    case "approval":
      return "waiting";
    case "queued":
    case "working":
      return "idle";
  }
}

function eventId(event: CommerceSubagentTaskEvent): string {
  return event.id ?? `${event.task_id}:${event.seq}`;
}
