import { reduceCommerceTaskVisualState } from "./chat-task-visual-state";
import type { CommerceRunTaskActivity } from "./subagent-task-api";

export interface CommerceRunTaskActivityViewModel {
  title: string;
  summary: {
    total: number;
    active: number;
    waiting: number;
    blocked: number;
    completed: number;
    failed: number;
    cancelled: number;
    timedOut: number;
  };
  items: Array<{
    taskId: string;
    parentTaskId: string | null;
    title: string;
    profile: string;
    profileLabel: string;
    statusLabel: string;
    detailLabel: string;
    status: ReturnType<typeof reduceCommerceTaskVisualState>["state"]["status"];
    activity: ReturnType<
      typeof reduceCommerceTaskVisualState
    >["state"]["activity"];
    latestToolName: string | null;
    latestMessagePreview: string | null;
    waitReason: string | null;
    availableSkills: string[];
    availableTools: string[];
    budget: Record<string, unknown>;
    lastEventSeq: number;
    unknownEventCount: number;
  }>;
  hasIncompleteEventPages: boolean;
  unknownEventCount: number;
  wasReordered: boolean;
}

export function buildCommerceRunTaskActivityViewModel(
  activities: CommerceRunTaskActivity[],
): CommerceRunTaskActivityViewModel {
  let wasReordered = false;
  let unknownEventCount = 0;
  const items = activities.map(({ task, events }) => {
    const reduction = reduceCommerceTaskVisualState(task, events);
    wasReordered ||= reduction.wasReordered;
    unknownEventCount += reduction.unknownEvents.length;
    return {
      taskId: task.task_id,
      parentTaskId: task.parent_task_id,
      title: task.description,
      profile: reduction.state.profile,
      profileLabel: profileLabel(task.subagent_type),
      statusLabel: statusLabel(reduction.state.status),
      detailLabel: detailLabel(reduction.state),
      status: reduction.state.status,
      activity: reduction.state.activity,
      latestToolName: reduction.state.latestToolName,
      latestMessagePreview: reduction.state.latestMessagePreview,
      waitReason: reduction.state.waitReason,
      availableSkills: reduction.state.availableSkills,
      availableTools: reduction.state.availableTools,
      budget: reduction.state.budget,
      lastEventSeq: reduction.state.lastEventSeq,
      unknownEventCount: reduction.unknownEvents.length,
    };
  });

  return {
    title: "协作任务",
    summary: {
      total: items.length,
      active: items.filter((item) => item.status === "working").length,
      waiting: items.filter((item) =>
        ["waiting", "approval"].includes(item.status),
      ).length,
      blocked: items.filter((item) => item.status === "blocked").length,
      completed: items.filter((item) => item.status === "completed").length,
      failed: items.filter((item) => item.status === "failed").length,
      cancelled: items.filter((item) => item.status === "cancelled").length,
      timedOut: items.filter((item) => item.status === "timed_out").length,
    },
    items,
    hasIncompleteEventPages: activities.some((item) => item.hasMore),
    unknownEventCount,
    wasReordered,
  };
}

function profileLabel(profile: string) {
  return (
    {
      explore: "探索",
      analyst: "分析",
      verifier: "核验",
      operator: "执行",
      "general-purpose": "通用",
    }[profile] ?? profile
  );
}

function statusLabel(
  status: ReturnType<typeof reduceCommerceTaskVisualState>["state"]["status"],
) {
  return {
    queued: "已排队",
    working: "进行中",
    waiting: "等待中",
    approval: "等待审批",
    blocked: "已阻塞",
    completed: "已完成",
    failed: "未完成",
    cancelled: "已取消",
    timed_out: "已超时",
  }[status];
}

function detailLabel(
  state: ReturnType<typeof reduceCommerceTaskVisualState>["state"],
) {
  if (state.status === "completed") return "任务已完成";
  if (state.status === "failed") return "任务未完成，可查看原因";
  if (state.status === "cancelled") return "任务已取消";
  if (state.status === "timed_out") return "任务已超时";
  if (state.status === "blocked") return state.waitReason ?? "任务已阻塞";
  if (state.status === "approval") return state.waitReason ?? "等待人工审批";
  if (state.status === "waiting")
    return state.waitReason ?? "等待依赖或外部条件";
  if (state.status === "queued") return "任务已排队";
  if (state.activity === "tool" && state.latestToolName) {
    return `正在使用：${toolLabel(state.latestToolName)}`;
  }
  if (state.activity === "message") return "已更新阶段结果";
  if (state.activity === "dispatching") return "任务已开始执行";
  return "任务运行中，等待下一条事件";
}

function toolLabel(toolName: string) {
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
