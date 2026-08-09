import type { Message } from "@langchain/langgraph-sdk";

export type StreamingStatusKey =
  | "preparing"
  | "thinking"
  | "searching"
  | "reading"
  | "researcher"
  | "offer"
  | "assets"
  | "analyzing"
  | "joining"
  | "experiment"
  | "rendering"
  | "writing"
  | "preflight"
  | "repairing"
  | "finalizing"
  | "failed";

export type StreamingStatus = {
  key: StreamingStatusKey;
  toolName?: string;
  subagentType?: string;
};

type TrackedToolCall = {
  id: string;
  name: string;
  args: Record<string, unknown>;
};

const LAUNCH_SUBAGENTS: Record<string, StreamingStatusKey> = {
  "market-voc-researcher": "researcher",
  "offer-architect": "offer",
  "asset-studio": "assets",
};

function asArgs(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

function classifyToolCall(call: TrackedToolCall): StreamingStatus {
  if (call.name === "task") {
    const subagentType =
      typeof call.args.subagent_type === "string"
        ? call.args.subagent_type
        : undefined;
    const specialistStatus = subagentType
      ? LAUNCH_SUBAGENTS[subagentType]
      : undefined;
    return {
      key: specialistStatus ?? "thinking",
      toolName: call.name,
      subagentType,
    };
  }

  if (call.name === "web_search" || call.name === "image_search") {
    return { key: "searching", toolName: call.name };
  }
  if (call.name === "web_fetch" || call.name === "read_file") {
    return { key: "reading", toolName: call.name };
  }
  if (
    call.name === "inspect_data" ||
    call.name === "query_data" ||
    call.name === "list_tables"
  ) {
    return { key: "analyzing", toolName: call.name };
  }
  if (call.name === "join_files" || call.name === "join_data") {
    return { key: "joining", toolName: call.name };
  }
  if (
    call.name === "analyze_ab_test" ||
    call.name === "analyze_cohort" ||
    call.name === "calculate_statistics"
  ) {
    return { key: "experiment", toolName: call.name };
  }
  if (call.name === "render_launch_pack") {
    return { key: "rendering", toolName: call.name };
  }
  if (call.name === "present_files") {
    return { key: "preflight", toolName: call.name };
  }
  if (call.name === "write_file" || call.name === "str_replace") {
    return {
      key: call.name === "str_replace" ? "repairing" : "writing",
      toolName: call.name,
    };
  }

  return { key: "thinking", toolName: call.name };
}

function classifyCompletedTool(name: string, content: string): StreamingStatus {
  const normalized = content.toLowerCase();
  if (
    (name === "present_files" || name === "render_launch_pack") &&
    normalized.includes("error")
  ) {
    return { key: "repairing", toolName: name };
  }
  if (name === "present_files" || name === "render_launch_pack") {
    return { key: "finalizing", toolName: name };
  }
  if (name === "str_replace") {
    return { key: "preflight", toolName: name };
  }
  return { key: "thinking", toolName: name };
}

function extractText(message: Message): string {
  if (typeof message.content === "string") {
    return message.content;
  }
  if (Array.isArray(message.content)) {
    return message.content
      .map((part) => (part.type === "text" ? part.text : ""))
      .join("\n");
  }
  return "";
}

/**
 * Derive a truthful, compact status from the event-shaped messages already
 * present in the LangGraph stream. No elapsed-time or synthetic progress is
 * used, so the label never claims a phase that the backend has not entered.
 */
export function deriveStreamingStatus(
  messages: readonly Message[],
  options: { hasError?: boolean } = {},
): StreamingStatus {
  if (options.hasError) {
    return { key: "failed" };
  }
  const calls: TrackedToolCall[] = [];
  const results = new Map<string, { name: string; content: string }>();
  let latestReasoning = false;
  let latestCompleted: { name: string; content: string } | undefined;

  for (const message of messages) {
    if (message.type === "ai") {
      latestReasoning = Boolean(message.additional_kwargs?.reasoning_content);
      for (const [index, toolCall] of (message.tool_calls ?? []).entries()) {
        const id =
          typeof toolCall.id === "string" && toolCall.id.length > 0
            ? toolCall.id
            : `${message.id ?? "message"}:${index}:${toolCall.name}`;
        calls.push({ id, name: toolCall.name, args: asArgs(toolCall.args) });
      }
    } else if (message.type === "tool") {
      const id = message.tool_call_id;
      if (typeof id === "string" && id.length > 0) {
        const call = calls.find((item) => item.id === id);
        const result = {
          name: call?.name ?? message.name ?? "tool",
          content: extractText(message),
        };
        results.set(id, result);
        latestCompleted = result;
      }
    }
  }

  const pendingCall = [...calls].reverse().find((call) => !results.has(call.id));
  if (pendingCall) {
    return classifyToolCall(pendingCall);
  }
  if (latestCompleted) {
    return classifyCompletedTool(
      latestCompleted.name,
      latestCompleted.content,
    );
  }
  if (calls.length > 0) {
    return { key: "finalizing" };
  }
  return { key: latestReasoning ? "thinking" : "preparing" };
}
