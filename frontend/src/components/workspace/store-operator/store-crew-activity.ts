import type { Message } from "@langchain/langgraph-sdk";

import { extractTextFromMessage } from "@/core/messages/utils";
import { parseSubtaskResult } from "@/core/tasks/subtask-result";
import type { Subtask } from "@/core/tasks/types";

export type StoreCrewRole = "lead" | "explore" | "analyst" | "verifier";

export type StoreCrewAgent = {
  id: StoreCrewRole;
  name: string;
  desk: string;
  active: boolean;
  status: "idle" | "working" | "failed";
  lastLine: string;
  task?: Subtask;
};

export type StoreCrewActivity = {
  agents: StoreCrewAgent[];
  activeCount: number;
  completedCount: number;
};

const ROLE_CONFIG: Array<Pick<StoreCrewAgent, "id" | "name" | "desk">> = [
  { id: "lead", name: "经营主理人", desk: "中央主控台" },
  { id: "explore", name: "数据侦察员", desk: "数据接入工位" },
  { id: "analyst", name: "经营分析师", desk: "经营分析工位" },
  { id: "verifier", name: "证据核验员", desk: "证据核验工位" },
];

function normalizeRole(
  value: string | undefined,
): Exclude<StoreCrewRole, "lead"> | null {
  if (value === "explore" || value === "analyst" || value === "verifier") {
    return value;
  }
  return null;
}

export function friendlyStoreTaskError(error: string | undefined): string {
  const normalized = error?.toLowerCase() ?? "";
  if (normalized.includes("recursion limit")) {
    return "任务未能在执行预算内完成。";
  }
  if (normalized.includes("timeout") || normalized.includes("timed out")) {
    return "任务执行超时。";
  }
  return "任务未完成，请返回对话查看详情。";
}

export function storeTasksFromMessages(messages: Message[]): Subtask[] {
  const tasks = new Map<string, Subtask>();
  for (const message of messages) {
    if (message.type === "ai") {
      for (const toolCall of message.tool_calls ?? []) {
        if (toolCall.name !== "task" || !toolCall.id) {
          continue;
        }
        const args = toolCall.args as {
          subagent_type?: string;
          description?: string;
          prompt?: string;
        };
        const role = normalizeRole(args.subagent_type);
        if (!role) {
          continue;
        }
        tasks.set(toolCall.id, {
          id: toolCall.id,
          subagent_type: role,
          description: args.description ?? role,
          prompt: args.prompt ?? "",
          status: "in_progress",
          latestMessage: message,
        });
      }
      continue;
    }
    if (message.type !== "tool" || typeof message.tool_call_id !== "string") {
      continue;
    }
    const task = tasks.get(message.tool_call_id);
    if (!task) {
      continue;
    }
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

export function buildStoreCrewActivity(
  messages: Message[],
  isStreaming: boolean,
): StoreCrewActivity {
  const tasks = storeTasksFromMessages(messages);
  const hasActiveTask = tasks.some((task) => task.status === "in_progress");
  const latestByRole = new Map<string, Subtask>();
  for (const task of tasks) {
    latestByRole.set(task.subagent_type, task);
  }
  const agents = ROLE_CONFIG.map((config): StoreCrewAgent => {
    if (config.id === "lead") {
      const active = isStreaming || hasActiveTask;
      return {
        ...config,
        active,
        status: active ? "working" : "idle",
        lastLine: active ? "正在理解问题并协调分析。" : "等待你的经营问题。",
      };
    }
    const task = latestByRole.get(config.id);
    const active = task?.status === "in_progress";
    const failed = task?.status === "failed";
    return {
      ...config,
      active,
      status: failed ? "failed" : active ? "working" : "idle",
      lastLine: failed
        ? friendlyStoreTaskError(task.error)
        : active
          ? task.description
          : task?.status === "completed"
            ? "本轮任务已完成，正在待命。"
            : "当前没有分配任务。",
      task,
    };
  });
  return {
    agents,
    activeCount: agents.filter((agent) => agent.active).length,
    completedCount: tasks.filter((task) => task.status === "completed").length,
  };
}
