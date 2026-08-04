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
};

export type WarRoomSnapshot = {
  actors: WarRoomActorSnapshot[];
  activeCount: number;
  completedCount: number;
  failedCount: number;
  artifactCount: number;
  updatedAt: string;
  /** EcomLaunch pipeline stages (init → research → design → content → pack → done). */
  stages: WarRoomStage[];
  /** Run metrics for the latest EcomLaunch run. */
  metrics: WarRoomMetrics;
  /** Latest run status for the EcomLaunch thread. */
  runStatus?: WarRoomRunStatus;
  /** Thread title of the latest EcomLaunch run. */
  runTitle?: string;
};

export type WarRoomSource = {
  ecomThread?: AgentThread;
  ecomRunStatus?: WarRoomRunStatus;
  ecomRuns?: Array<{
    run_id: string;
    status?: string;
    created_at?: string;
    updated_at?: string;
    llm_call_count?: number;
    total_tokens?: number;
    total_input_tokens?: number;
    total_output_tokens?: number;
  }>;
  dataThread?: AgentThread;
  dataRunStatus?: WarRoomRunStatus;
};
