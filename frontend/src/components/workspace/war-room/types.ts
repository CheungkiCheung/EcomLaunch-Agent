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

export type WarRoomActorSnapshot = WarRoomActorConfig & {
  status: WarRoomStatus;
  activity: WarRoomActivity;
  summary: string;
  task?: string;
  tool?: string;
  artifacts: string[];
  threadId?: string;
  href?: string;
};

export type WarRoomSnapshot = {
  actors: WarRoomActorSnapshot[];
  activeCount: number;
  completedCount: number;
  failedCount: number;
  artifactCount: number;
  updatedAt: string;
};

export type WarRoomSource = {
  ecomThread?: AgentThread;
  ecomRunStatus?: WarRoomRunStatus;
  dataThread?: AgentThread;
  dataRunStatus?: WarRoomRunStatus;
};
