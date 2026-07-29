import type { Message } from "@langchain/langgraph-sdk";

import {
  extractPresentFilesFromMessage,
  extractTextFromMessage,
  hasPresentFiles,
} from "@/core/messages/utils";
import { parseSubtaskResult } from "@/core/tasks/subtask-result";
import type { Subtask } from "@/core/tasks/types";
import { pathOfThread, textOfMessage } from "@/core/threads/utils";

import { WAR_ROOM_ACTORS } from "./config";
import type {
  WarRoomActivity,
  WarRoomActorId,
  WarRoomActorSnapshot,
  WarRoomRunStatus,
  WarRoomSnapshot,
  WarRoomSource,
  WarRoomStatus,
} from "./types";

const SUBAGENT_IDS = new Set<WarRoomActorId>([
  "market-voc-researcher",
  "offer-architect",
  "asset-studio",
  "evidence-checker",
]);

type TaskRecord = Subtask & {
  sequence: number;
};

function messagesOf(source: WarRoomSource["ecomThread"]) {
  return source?.values?.messages ?? [];
}

function artifactsOf(source: WarRoomSource["ecomThread"]) {
  const files = [...(source?.values?.artifacts ?? [])];
  for (const message of messagesOf(source)) {
    if (hasPresentFiles(message)) {
      files.push(...extractPresentFilesFromMessage(message));
    }
  }
  return [...new Set(files)];
}

function tasksFromMessages(messages: Message[]) {
  const tasks = new Map<string, TaskRecord>();
  let sequence = 0;

  for (const message of messages) {
    if (message.type === "ai") {
      for (const toolCall of message.tool_calls ?? []) {
        if (toolCall.name !== "task" || !toolCall.id) continue;
        const args = toolCall.args as {
          subagent_type?: string;
          description?: string;
          prompt?: string;
        };
        if (!SUBAGENT_IDS.has(args.subagent_type as WarRoomActorId)) continue;
        tasks.set(toolCall.id, {
          id: toolCall.id,
          status: "in_progress",
          subagent_type: args.subagent_type!,
          description: args.description ?? args.subagent_type!,
          prompt: args.prompt ?? "",
          latestMessage: message,
          sequence: sequence++,
        });
      }
      continue;
    }

    if (message.type !== "tool" || !message.tool_call_id) continue;
    const task = tasks.get(message.tool_call_id);
    if (!task) continue;
    tasks.set(message.tool_call_id, {
      ...task,
      ...parseSubtaskResult(
        extractTextFromMessage(message),
        message.additional_kwargs,
      ),
    });
  }

  return [...tasks.values()];
}

function latestTaskForRole(tasks: TaskRecord[], id: WarRoomActorId) {
  return tasks
    .filter((task) => task.subagent_type === id)
    .sort((a, b) => b.sequence - a.sequence)[0];
}

function latestHumanRequest(messages: Message[]) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.type !== "human") continue;
    const text = textOfMessage(message)?.trim();
    if (text) return text;
  }
  return undefined;
}

function latestTool(messages: Message[], includeTask = false) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.type !== "ai") continue;
    const toolCall = [...(message.tool_calls ?? [])]
      .reverse()
      .find((tool) => includeTask || tool.name !== "task");
    if (toolCall) return toolCall.name;
  }
  return undefined;
}

function statusFromRun(runStatus: WarRoomRunStatus | undefined): WarRoomStatus {
  if (runStatus === "pending") return "queued";
  if (runStatus === "running") return "working";
  if (
    runStatus === "error" ||
    runStatus === "timeout" ||
    runStatus === "interrupted"
  ) {
    return "failed";
  }
  if (runStatus === "success") return "done";
  return "idle";
}

function statusFromTask(task: TaskRecord | undefined): WarRoomStatus {
  if (!task) return "idle";
  if (task.status === "failed") return "failed";
  if (task.status === "completed") return "done";
  return "working";
}

function activityFromTool(
  tool: string | undefined,
  fallback: WarRoomActivity,
): WarRoomActivity {
  if (!tool) return fallback;
  if (tool === "web_search" || tool === "image_search") return "searching";
  if (tool === "read_file" || tool === "web_fetch" || tool === "inspect_data") {
    return "reading";
  }
  if (
    tool === "query_data" ||
    tool === "analyze_ab_test" ||
    tool.includes("python") ||
    tool.includes("sql")
  ) {
    return "analyzing";
  }
  if (tool === "write_file") return "writing";
  if (tool === "present_files") return "delivering";
  return fallback;
}

function activityFromTask(task: TaskRecord | undefined): WarRoomActivity {
  if (!task) return "waiting";
  if (task.status === "completed") return "delivering";
  if (task.status === "failed") return "reviewing";
  const text = `${task.description} ${task.prompt}`.toLowerCase();
  if (/search|research|market|voc|竞品|市场|用户|评价/.test(text)) {
    return "searching";
  }
  if (/evidence|verify|audit|review|证据|审核|检查/.test(text)) {
    return "reviewing";
  }
  if (/asset|content|copy|listing|素材|内容|文案/.test(text)) {
    return "writing";
  }
  return "analyzing";
}

function summaryFor(
  status: WarRoomStatus,
  activity: WarRoomActivity,
  task?: string,
) {
  if (status === "failed") return "任务遇到阻塞，等待查看失败信息。";
  if (status === "done") return "本轮任务已经完成，交付结果可查看。";
  if (status === "queued") return "任务已经进入队列，等待开始执行。";
  if (status === "idle") return "当前待命，等待新的真实任务事件。";
  const labels: Record<WarRoomActivity, string> = {
    waiting: "正在等待上游任务。",
    orchestrating: "正在拆解目标并调度协作任务。",
    searching: "正在采集市场、用户或公开信息。",
    reading: "正在读取文件、页面或数据结构。",
    analyzing: "正在计算、比较并识别关键变化。",
    writing: "正在组织结论并生成交付内容。",
    reviewing: "正在检查来源、边界和交付质量。",
    delivering: "正在整理产物并交付结果。",
  };
  return task ? `${labels[activity]} ${task}` : labels[activity];
}

function hrefFor(source: WarRoomSource["ecomThread"]) {
  return source ? pathOfThread(source) : undefined;
}

function buildLeadActor(source: WarRoomSource): WarRoomActorSnapshot {
  const config = WAR_ROOM_ACTORS.find((actor) => actor.id === "ecom-launch")!;
  const messages = messagesOf(source.ecomThread);
  const tool = latestTool(messages, true);
  const status = statusFromRun(source.ecomRunStatus);
  const activity = activityFromTool(tool, "orchestrating");
  const task = latestHumanRequest(messages);
  return {
    ...config,
    status,
    activity: status === "idle" ? "waiting" : activity,
    summary: summaryFor(status, activity, task),
    task,
    tool,
    artifacts: artifactsOf(source.ecomThread),
    threadId: source.ecomThread?.thread_id,
    href: hrefFor(source.ecomThread),
  };
}

function buildSubagentActor(
  id: WarRoomActorId,
  source: WarRoomSource,
  tasks: TaskRecord[],
): WarRoomActorSnapshot {
  const config = WAR_ROOM_ACTORS.find((actor) => actor.id === id)!;
  const task = latestTaskForRole(tasks, id);
  const status = statusFromTask(task);
  const activity = activityFromTask(task);
  return {
    ...config,
    status,
    activity,
    summary: summaryFor(status, activity, task?.description),
    task: task?.description,
    tool: task?.latestMessage?.tool_calls?.at(-1)?.name,
    artifacts: [],
    threadId: source.ecomThread?.thread_id,
    href: hrefFor(source.ecomThread),
  };
}

function buildDataActor(source: WarRoomSource): WarRoomActorSnapshot {
  const config = WAR_ROOM_ACTORS.find(
    (actor) => actor.id === "data-inspector",
  )!;
  const messages = messagesOf(source.dataThread);
  const tool = latestTool(messages);
  const status = statusFromRun(source.dataRunStatus);
  const activity = activityFromTool(tool, "analyzing");
  const task = latestHumanRequest(messages);
  return {
    ...config,
    status,
    activity: status === "idle" ? "waiting" : activity,
    summary: summaryFor(status, activity, task),
    task,
    tool,
    artifacts: artifactsOf(source.dataThread),
    threadId: source.dataThread?.thread_id,
    href: hrefFor(source.dataThread),
  };
}

export function buildWarRoomSnapshot(source: WarRoomSource): WarRoomSnapshot {
  const tasks = tasksFromMessages(messagesOf(source.ecomThread));
  const actors = WAR_ROOM_ACTORS.map((actor) => {
    if (actor.id === "ecom-launch") return buildLeadActor(source);
    if (actor.id === "data-inspector") return buildDataActor(source);
    return buildSubagentActor(actor.id, source, tasks);
  });
  return {
    actors,
    activeCount: actors.filter(
      (actor) => actor.status === "queued" || actor.status === "working",
    ).length,
    completedCount: actors.filter((actor) => actor.status === "done").length,
    failedCount: actors.filter((actor) => actor.status === "failed").length,
    artifactCount: new Set(actors.flatMap((actor) => actor.artifacts)).size,
    updatedAt: new Date().toISOString(),
  };
}
