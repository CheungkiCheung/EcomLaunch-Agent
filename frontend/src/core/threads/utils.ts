import type { Message } from "@langchain/langgraph-sdk";

import type { AgentThread, AgentThreadContext } from "./types";

type ThreadAgentSource = {
  context?: Pick<AgentThreadContext, "agent_name"> | null;
  metadata?: Record<string, unknown> | null;
};

type ThreadRouteTarget =
  | string
  | (ThreadAgentSource & {
      thread_id: string;
    });

export function agentNameOfThread(
  thread: ThreadAgentSource,
): string | undefined {
  const contextAgent = thread.context?.agent_name;
  if (contextAgent) {
    return contextAgent;
  }
  const metadataAgent = thread.metadata?.agent_name;
  return typeof metadataAgent === "string" ? metadataAgent : undefined;
}

export function pathOfThread(
  thread: ThreadRouteTarget,
  context?: Pick<AgentThreadContext, "agent_name"> | null,
) {
  const threadId = typeof thread === "string" ? thread : thread.thread_id;
  let agentName: string | undefined;
  if (typeof thread === "string") {
    agentName = context?.agent_name;
  } else {
    agentName = agentNameOfThread(thread);
  }

  return agentName
    ? `/workspace/agents/${encodeURIComponent(agentName)}/chats/${threadId}`
    : `/workspace/chats/${threadId}`;
}

export function textOfMessage(message: Message) {
  if (typeof message.content === "string") {
    return message.content;
  } else if (Array.isArray(message.content)) {
    for (const part of message.content) {
      if (part.type === "text") {
        return part.text;
      }
    }
  }
  return null;
}

export function titleOfThread(thread: AgentThread) {
  return thread.values?.title ?? "Untitled";
}
