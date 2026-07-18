"use client";

import type { Message } from "@langchain/langgraph-sdk";

import {
  extractPresentFilesFromMessage,
  extractTextFromMessage,
  hasPresentFiles,
} from "@/core/messages/utils";
import { parseSubtaskResult } from "@/core/tasks/subtask-result";
import type { Subtask } from "@/core/tasks/types";
import type { AgentThreadState } from "@/core/threads";
import { getFileName } from "@/core/utils/files";

import {
  buildLaunchCrewActivityModel,
  type LaunchCrewActivityModel,
  type LaunchCrewRole,
  type LaunchCrewTask,
} from "./launch-crew-activity-model";

export function normalizeLaunchCrewRole(
  role: string | undefined,
): LaunchCrewRole | null {
  if (
    role === "market-voc-researcher" ||
    role === "offer-architect" ||
    role === "asset-studio" ||
    role === "evidence-checker" ||
    role === "growth-analyst"
  ) {
    return role;
  }
  return null;
}

function getToolName(task: Subtask | undefined) {
  return task?.latestMessage?.tool_calls?.at(-1)?.name ?? null;
}

export function fallbackTasksFromMessages(messages: Message[]) {
  const taskMap = new Map<string, Subtask>();

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
        const role = normalizeLaunchCrewRole(args.subagent_type);
        if (!role) {
          continue;
        }
        taskMap.set(toolCall.id, {
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

    if (message.type === "tool" && typeof message.tool_call_id === "string") {
      const task = taskMap.get(message.tool_call_id);
      if (!task) {
        continue;
      }
      taskMap.set(message.tool_call_id, {
        ...task,
        ...parseSubtaskResult(
          extractTextFromMessage(message),
          message.additional_kwargs,
        ),
      });
    }
  }

  return [...taskMap.values()];
}

export function fallbackArtifactsFromMessages(messages: Message[]) {
  const files: string[] = [];
  for (const message of messages) {
    if (hasPresentFiles(message)) {
      files.push(...extractPresentFilesFromMessage(message));
    }
  }
  return [...new Set(files)];
}

export function latestAssistantTextFromMessages(messages: Message[]) {
  for (const message of [...messages].reverse()) {
    if (message.type !== "ai" || (message.tool_calls?.length ?? 0) > 0) {
      continue;
    }
    const text = extractTextFromMessage(message).trim();
    if (text) {
      return text;
    }
  }
  for (const message of [...messages].reverse()) {
    if (message.type !== "ai") {
      continue;
    }
    const text = extractTextFromMessage(message).trim();
    if (text) {
      return text;
    }
  }
  return "";
}

export function toLaunchCrewTasks(
  tasks: Subtask[],
  explainAction: (task: Subtask) => string | null,
): LaunchCrewTask[] {
  const result: LaunchCrewTask[] = [];
  for (const task of tasks) {
    const role = normalizeLaunchCrewRole(task.subagent_type);
    if (!role) {
      continue;
    }
    result.push({
      id: task.id,
      role,
      status: task.status,
      description: task.description,
      prompt: task.prompt,
      result: task.result,
      error: task.error,
      currentAction:
        task.latestMessage && task.status === "in_progress"
          ? explainAction(task)
          : null,
      toolName: getToolName(task),
    });
  }
  return result;
}

export function buildLaunchCrewActivityModelFromThread({
  messages,
  contextTasks = {},
  threadValues,
  selectedAgentId,
  isStreaming,
  explainAction,
}: {
  messages: Message[];
  contextTasks?: Record<string, Subtask>;
  threadValues: AgentThreadState;
  selectedAgentId: LaunchCrewRole | null;
  isStreaming: boolean;
  explainAction: (task: Subtask) => string | null;
}): LaunchCrewActivityModel {
  const fallbackTasks = fallbackTasksFromMessages(messages);
  const taskMap = new Map<string, Subtask>();
  for (const task of fallbackTasks) {
    taskMap.set(task.id, task);
  }
  for (const task of Object.values(contextTasks)) {
    taskMap.set(task.id, task);
  }
  const fallbackArtifacts = fallbackArtifactsFromMessages(messages);
  const artifacts = [
    ...new Set([...(threadValues.artifacts ?? []), ...fallbackArtifacts]),
  ];

  return buildLaunchCrewActivityModel({
    tasks: toLaunchCrewTasks([...taskMap.values()], explainAction),
    artifacts: artifacts.map(getFileName),
    todos: threadValues.todos,
    selectedAgentId,
    finalResponseText: latestAssistantTextFromMessages(messages),
    isStreaming,
  });
}
