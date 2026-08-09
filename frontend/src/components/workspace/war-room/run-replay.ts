import type { Message } from "@langchain/langgraph-sdk";

import { enUS } from "@/core/i18n/locales/en-US";
import type { Translations } from "@/core/i18n/locales/types";
import { extractTextFromMessage } from "@/core/messages/utils";
import { parseSubtaskResult } from "@/core/tasks/subtask-result";
import { textOfMessage } from "@/core/threads/utils";

import { buildWarRoomSnapshot } from "./adapter";
import { localizeWarRoomActors } from "./config";
import type {
  WarRoomActorId,
  WarRoomReplay,
  WarRoomReplayEvent,
  WarRoomReplayEventKind,
  WarRoomRunStatus,
  WarRoomSource,
} from "./types";

const SUBAGENT_IDS = new Set<WarRoomActorId>([
  "market-voc-researcher",
  "offer-architect",
  "asset-studio",
  "evidence-checker",
]);

type TaskCall = {
  actorId: WarRoomActorId;
  description: string;
};

type ReplayToolCall = {
  id?: string;
  name: string;
  args?: unknown;
};

function messagesOf(source: WarRoomSource["ecomThread"]): Message[] {
  return [...(source?.values?.messages ?? [])];
}

function toolCallsOf(message: Message): ReplayToolCall[] {
  if (!("tool_calls" in message)) return [];
  const calls = (message as Message & { tool_calls?: unknown }).tool_calls;
  return Array.isArray(calls) ? (calls as ReplayToolCall[]) : [];
}

function preview(value: string | undefined, limit = 180) {
  const normalized = value?.replace(/\s+/g, " ").trim();
  if (!normalized) return undefined;
  return normalized.length > limit
    ? `${normalized.slice(0, limit - 1)}…`
    : normalized;
}

function latestHumanIndex(messages: Message[]) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.type === "human") return index;
  }
  return -1;
}

function withToolCalls(message: Message, toolCalls: ReplayToolCall[]) {
  return { ...message, tool_calls: toolCalls } as unknown as Message;
}

function withMessages(
  thread: NonNullable<WarRoomSource["ecomThread"]>,
  messages: Message[],
  includeArtifacts: boolean,
) {
  const values = thread.values ?? {};
  return {
    ...thread,
    values: {
      ...values,
      messages,
      artifacts: includeArtifacts ? [...(values.artifacts ?? [])] : [],
    },
  };
}

function actorNames(copy: Translations["warRoom"]) {
  return new Map(
    localizeWarRoomActors(copy.actors).map((actor) => [actor.id, actor.name]),
  );
}

function taskCallOf(
  call: ReplayToolCall,
  names: Map<WarRoomActorId, string>,
): TaskCall | undefined {
  if (call.name !== "task") return undefined;
  const args = (call.args ?? {}) as {
    subagent_type?: string;
    description?: string;
    prompt?: string;
  };
  const actorId = args.subagent_type as WarRoomActorId | undefined;
  if (!actorId || !SUBAGENT_IDS.has(actorId)) return undefined;
  return {
    actorId,
    description:
      preview(args.description) ??
      preview(args.prompt) ??
      names.get(actorId) ??
      actorId,
  };
}

function toolEvent(toolName: string, copy: Translations["warRoom"]) {
  if (toolName === "render_launch_pack") {
    return { kind: "verification" as const, title: copy.replay.verification };
  }
  if (toolName === "present_files") {
    return { kind: "delivery" as const, title: copy.replay.delivery };
  }
  return { kind: "tool" as const, title: copy.replay.tool(toolName) };
}

function terminalKind(
  status: WarRoomRunStatus | undefined,
): WarRoomReplayEventKind | null {
  if (status === "success") return "completed";
  if (status === "error" || status === "timeout" || status === "interrupted") {
    return "failed";
  }
  return null;
}

function snapshotFor(
  source: WarRoomSource,
  messages: Message[],
  runStatus: WarRoomRunStatus | undefined,
  copy: Translations["warRoom"],
  includeArtifacts = false,
) {
  return buildWarRoomSnapshot(
    {
      ...source,
      ecomThread:
        source.ecomThread &&
        withMessages(source.ecomThread, messages, includeArtifacts),
      ecomRunStatus: runStatus,
    },
    copy,
  );
}

function addEvent(
  events: WarRoomReplayEvent[],
  source: WarRoomSource,
  messages: Message[],
  runStatus: WarRoomRunStatus | undefined,
  copy: Translations["warRoom"],
  event: Omit<WarRoomReplayEvent, "id" | "snapshot">,
  includeArtifacts = false,
) {
  events.push({
    ...event,
    id: `replay-${events.length + 1}`,
    snapshot: snapshotFor(source, messages, runStatus, copy, includeArtifacts),
  });
}

/**
 * Reconstructs a replay from the latest real human request in the Launch Team
 * thread. The replay is deliberately derived from persisted messages and
 * task/tool results; it never creates synthetic agent activity.
 */
export function buildWarRoomReplay(
  source: WarRoomSource,
  copy: Translations["warRoom"] = enUS.warRoom,
): WarRoomReplay | null {
  const thread = source.ecomThread;
  if (!thread) return null;

  const allMessages = messagesOf(thread);
  const startIndex = latestHumanIndex(allMessages);
  if (startIndex < 0) return null;

  const runMessages = allMessages.slice(startIndex);
  const request =
    preview(textOfMessage(runMessages[0]!) ?? undefined) ?? copy.replay.request;
  const names = actorNames(copy);
  const taskCalls = new Map<string, TaskCall>();
  const toolNames = new Map<string, string>();
  const events: WarRoomReplayEvent[] = [];

  addEvent(events, source, runMessages.slice(0, 1), "pending", copy, {
    actorId: "ecom-launch",
    kind: "request",
    title: copy.replay.request,
    detail: request,
  });

  for (let index = 1; index < runMessages.length; index += 1) {
    const message = runMessages[index]!;

    if (message.type === "ai") {
      const calls = toolCallsOf(message);
      for (let callIndex = 0; callIndex < calls.length; callIndex += 1) {
        const call = calls[callIndex]!;
        const task = taskCallOf(call, names);
        const prefix = [
          ...runMessages.slice(0, index),
          withToolCalls(message, calls.slice(0, callIndex + 1)),
        ];
        if (task && call.id) {
          taskCalls.set(call.id, task);
          toolNames.set(call.id, call.name);
          addEvent(events, source, prefix, "running", copy, {
            actorId: task.actorId,
            kind: "handoff",
            title: copy.replay.handoff(names.get(task.actorId) ?? task.actorId),
            detail: task.description,
            tool: call.name,
          });
          continue;
        }

        if (call.id) toolNames.set(call.id, call.name);
        const tool = toolEvent(call.name, copy);
        addEvent(events, source, prefix, "running", copy, {
          actorId: "ecom-launch",
          kind: tool.kind,
          title: tool.title,
          detail: preview(JSON.stringify(call.args)),
          tool: call.name,
        });
      }

      if (calls.length === 0) {
        const detail = preview(extractTextFromMessage(message));
        if (detail) {
          addEvent(
            events,
            source,
            runMessages.slice(0, index + 1),
            "running",
            copy,
            {
              actorId: "ecom-launch",
              kind: "observation",
              title: copy.replay.observation,
              detail,
            },
          );
        }
      }
      continue;
    }

    if (message.type !== "tool") continue;
    const detail = preview(extractTextFromMessage(message));
    const task = message.tool_call_id
      ? taskCalls.get(message.tool_call_id)
      : undefined;
    const parsed = task
      ? parseSubtaskResult(
          extractTextFromMessage(message),
          message.additional_kwargs,
        )
      : undefined;
    const failed = parsed?.status === "failed";
    const toolName = message.tool_call_id
      ? toolNames.get(message.tool_call_id)
      : undefined;
    const tool = task
      ? {
          kind: failed ? ("failed" as const) : ("observation" as const),
          title: failed ? copy.replay.failed : copy.replay.observation,
        }
      : toolName === "render_launch_pack" &&
          detail?.includes("Successfully presented files")
        ? { kind: "delivery" as const, title: copy.replay.delivery }
        : toolName
          ? toolEvent(toolName, copy)
          : { kind: "observation" as const, title: copy.replay.observation };
    addEvent(events, source, runMessages.slice(0, index + 1), "running", copy, {
      actorId: task?.actorId ?? "ecom-launch",
      kind: tool.kind,
      title: tool.title,
      detail,
      tool: task ? "task" : toolName,
    });
  }

  const finalKind = terminalKind(source.ecomRunStatus);
  if (finalKind) {
    addEvent(
      events,
      source,
      runMessages,
      source.ecomRunStatus,
      copy,
      {
        actorId: "ecom-launch",
        kind: finalKind,
        title:
          finalKind === "completed"
            ? copy.replay.completed
            : copy.replay.failed,
        detail: preview(extractTextFromMessage(runMessages.at(-1)!)),
      },
      true,
    );
  }

  return events.length > 1
    ? {
        id: thread.thread_id,
        team: "ecom-launch",
        title: thread.values?.title ?? copy.replay.latestRun,
        events,
      }
    : null;
}
