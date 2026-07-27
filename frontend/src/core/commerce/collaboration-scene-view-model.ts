import type {
  CommerceTaskVisualActivity,
  CommerceTaskVisualStatus,
} from "./chat-task-visual-state";
import type { CommerceRunTaskActivityViewModel } from "./run-task-activity-view-model";

export type CommerceCollaborationSceneStatus =
  | "empty"
  | "active"
  | "waiting"
  | "blocked"
  | "completed"
  | "failed";

export type CommerceCollaborationStation =
  | "intake"
  | "analysis"
  | "verification"
  | "action"
  | "approval"
  | "delivery"
  | "recovery"
  | "general";

export interface CommerceCollaborationActorViewModel {
  actorId: string;
  taskId: string;
  parentTaskId: string | null;
  placementKey: string;
  title: string;
  profile: string;
  profileLabel: string;
  station: CommerceCollaborationStation;
  status: CommerceTaskVisualStatus;
  statusLabel: string;
  motion: CommerceTaskVisualActivity;
  detailLabel: string;
  propLabel: string | null;
  messagePreview: string | null;
  availableSkills: string[];
  availableTools: string[];
  budget: Record<string, unknown>;
  lastEventSeq: number;
  ariaLabel: string;
}

export interface CommerceCollaborationSceneViewModel {
  sceneStatus: CommerceCollaborationSceneStatus;
  statusText: string;
  actors: CommerceCollaborationActorViewModel[];
  hasProjectionWarnings: boolean;
  projectionWarnings: string[];
}

/**
 * Project durable Task/Event state into a renderer-neutral collaboration scene.
 *
 * One unique task produces at most one actor. The projection contains no
 * timers, random motion, fixed crew members, or message-text inference. Canvas,
 * Pixi and reduced-motion list renderers must all consume this same contract.
 */
export function buildCommerceCollaborationSceneViewModel(
  activity: CommerceRunTaskActivityViewModel,
): CommerceCollaborationSceneViewModel {
  const seenTaskIds = new Set<string>();
  let duplicateTaskCount = 0;
  const actors: CommerceCollaborationActorViewModel[] = [];

  for (const item of activity.items) {
    if (seenTaskIds.has(item.taskId)) {
      duplicateTaskCount += 1;
      continue;
    }
    seenTaskIds.add(item.taskId);
    actors.push({
      actorId: `task:${item.taskId}`,
      taskId: item.taskId,
      parentTaskId: item.parentTaskId,
      placementKey: item.taskId,
      title: item.title,
      profile: item.profile,
      profileLabel: item.profileLabel,
      station: stationFor(item.profile, item.status),
      status: item.status,
      statusLabel: item.statusLabel,
      motion: item.activity,
      detailLabel: item.detailLabel,
      propLabel: item.latestToolName ? toolLabel(item.latestToolName) : null,
      messagePreview: item.latestMessagePreview,
      availableSkills: [...item.availableSkills],
      availableTools: [...item.availableTools],
      budget: { ...item.budget },
      lastEventSeq: item.lastEventSeq,
      ariaLabel: `${item.profileLabel}子任务，${item.statusLabel}，${item.detailLabel}`,
    });
  }

  const projectionWarnings = buildProjectionWarnings(
    activity,
    duplicateTaskCount,
  );
  const sceneStatus = sceneStatusFor(actors);
  return {
    sceneStatus,
    statusText: sceneStatusText(sceneStatus, actors),
    actors,
    hasProjectionWarnings: projectionWarnings.length > 0,
    projectionWarnings,
  };
}

function stationFor(
  profile: string,
  status: CommerceTaskVisualStatus,
): CommerceCollaborationStation {
  if (status === "approval") return "approval";
  if (["failed", "cancelled", "timed_out", "blocked"].includes(status)) {
    return "recovery";
  }
  return (
    (
      {
        explore: "intake",
        analyst: "analysis",
        verifier: "verification",
        operator: "action",
      } satisfies Record<string, CommerceCollaborationStation>
    )[profile] ?? "general"
  );
}

function sceneStatusFor(
  actors: CommerceCollaborationActorViewModel[],
): CommerceCollaborationSceneStatus {
  if (actors.length === 0) return "empty";
  if (actors.some((actor) => actor.status === "working")) return "active";
  if (actors.some((actor) => ["waiting", "approval"].includes(actor.status))) {
    return "waiting";
  }
  if (actors.some((actor) => actor.status === "blocked")) return "blocked";
  if (
    actors.some((actor) =>
      ["failed", "cancelled", "timed_out"].includes(actor.status),
    )
  ) {
    return "failed";
  }
  if (actors.every((actor) => actor.status === "completed")) {
    return "completed";
  }
  return "active";
}

function sceneStatusText(
  status: CommerceCollaborationSceneStatus,
  actors: CommerceCollaborationActorViewModel[],
): string {
  switch (status) {
    case "empty":
      return "当前没有协作任务";
    case "active":
      return `${actors.filter((actor) => actor.status === "working").length || actors.length} 个子任务正在协作`;
    case "waiting":
      return `${actors.filter((actor) => ["waiting", "approval"].includes(actor.status)).length} 个子任务正在等待`;
    case "blocked":
      return `${actors.filter((actor) => actor.status === "blocked").length} 个子任务已阻塞`;
    case "completed":
      return "协作任务已全部完成";
    case "failed":
      return `${actors.filter((actor) => ["failed", "cancelled", "timed_out"].includes(actor.status)).length} 个子任务未正常完成`;
  }
}

function buildProjectionWarnings(
  activity: CommerceRunTaskActivityViewModel,
  duplicateTaskCount: number,
): string[] {
  const warnings: string[] = [];
  if (activity.hasIncompleteEventPages) {
    warnings.push("部分任务事件尚未加载完成");
  }
  if (activity.wasReordered) {
    warnings.push("任务事件曾发生乱序，已按序号恢复");
  }
  if (activity.unknownEventCount > 0) {
    warnings.push(`存在 ${activity.unknownEventCount} 条未知任务事件`);
  }
  if (duplicateTaskCount > 0) {
    warnings.push(`存在 ${duplicateTaskCount} 条重复任务投影，已保留首次记录`);
  }
  return warnings;
}

function toolLabel(toolName: string): string {
  return (
    {
      commerce_dataset_profile: "数据概览",
      commerce_capabilities: "能力检查",
      commerce_seller_coverage: "全量覆盖",
      commerce_compare_windows: "窗口对比",
      commerce_evidence_query: "证据抽查",
      commerce_peer_comparison: "同类对标",
      commerce_geographic_segments: "地域分段",
    }[toolName] ?? toolName
  );
}
