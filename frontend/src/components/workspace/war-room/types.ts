import type { AgentThread } from "@/core/threads/types";

export type WarRoomActorId =
  | "ecom-launch"
  | "market-voc-researcher"
  | "offer-architect"
  | "asset-studio"
  | "evidence-checker"
  | "data-inspector";

export type WarRoomTeam = "ecom-launch" | "data-inspector";

export type WarRoomStatus = "idle" | "queued" | "working" | "done" | "failed";

export type WarRoomActivity =
  | "waiting"
  | "orchestrating"
  | "searching"
  | "reading"
  | "analyzing"
  | "writing"
  | "reviewing"
  | "delivering";

export type WarRoomRunStatus =
  | "pending"
  | "running"
  | "error"
  | "success"
  | "timeout"
  | "interrupted";

export type WarRoomPosition = {
  x: number;
  y: number;
  workX: number;
  workY: number;
};

export type WarRoomActorConfig = {
  id: WarRoomActorId;
  team: WarRoomTeam;
  name: string;
  shortName: string;
  role: string;
  description: string;
  accent: string;
  glow: number;
  position: WarRoomPosition;
};

export type WarRoomTaskDetail = {
  id: string;
  description: string;
  status: "in_progress" | "completed" | "failed";
  output?: string;
  error?: string;
};

export type WarRoomActorSnapshot = WarRoomActorConfig & {
  status: WarRoomStatus;
  activity: WarRoomActivity;
  summary: string;
  task?: string;
  tool?: string;
  artifacts: string[];
  threadId?: string;
  href?: string;
  /** Latest task detail for this actor (subagents only). */
  taskDetail?: WarRoomTaskDetail;
};

export type WarRoomStage = {
  id: string;
  label: string;
  done: boolean;
  current: boolean;
};

export type WarRoomMetrics = {
  llmCalls: number;
  totalTokens: number;
  durationSeconds?: number;
  webSearches: number;
  webFetches: number;
  writeFiles: number;
  presentCalls: number;
  dataQueries: number;
  experiments: number;
};

export type WarRoomSnapshot = {
  /** Team whose run details, stages, and metrics are currently in focus. */
  focusTeam: WarRoomTeam;
  actors: WarRoomActorSnapshot[];
  activeCount: number;
  completedCount: number;
  failedCount: number;
  artifactCount: number;
  updatedAt: string;
  /** Pipeline stages for the focused Launch Team or Growth Analyst run. */
  stages: WarRoomStage[];
  /** Run metrics for the focused team's latest run. */
  metrics: WarRoomMetrics;
  /** Latest run status for the focused team's thread. */
  runStatus?: WarRoomRunStatus;
  /** Thread title of the focused team's latest run. */
  runTitle?: string;
};

export type WarRoomReplayEventKind =
  | "request"
  | "handoff"
  | "tool"
  | "observation"
  | "verification"
  | "delivery"
  | "completed"
  | "failed";

export type WarRoomReplayEvent = {
  id: string;
  actorId: WarRoomActorId;
  kind: WarRoomReplayEventKind;
  title: string;
  detail?: string;
  tool?: string;
  snapshot: WarRoomSnapshot;
};

export type WarRoomReplay = {
  id: string;
  team: WarRoomTeam;
  title: string;
  events: WarRoomReplayEvent[];
};

export type WarRoomRunRecord = {
  run_id: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
  llm_call_count?: number;
  total_tokens?: number;
  total_input_tokens?: number;
  total_output_tokens?: number;
};

export type WarRoomSource = {
  ecomThread?: AgentThread;
  ecomRunStatus?: WarRoomRunStatus;
  ecomRuns?: WarRoomRunRecord[];
  dataThread?: AgentThread;
  dataRunStatus?: WarRoomRunStatus;
  dataRuns?: WarRoomRunRecord[];
};
