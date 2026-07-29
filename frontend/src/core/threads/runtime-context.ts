import type { LocalSettings } from "../settings";

import type { AgentThreadContext } from "./types";

export type ThreadRuntimeContextOverrides = Partial<
  Pick<
    AgentThreadContext,
    "thinking_enabled" | "is_plan_mode" | "subagent_enabled"
  >
> & {
  max_concurrent_subagents?: number;
};

export function buildThreadRunContext({
  context,
  extraContext,
  runtimeContext,
  threadId,
}: {
  context: LocalSettings["context"];
  extraContext?: Record<string, unknown>;
  runtimeContext?: ThreadRuntimeContextOverrides;
  threadId: string;
}) {
  return {
    ...extraContext,
    ...context,
    thinking_enabled: context.mode !== "flash",
    is_plan_mode: context.mode === "pro" || context.mode === "ultra",
    subagent_enabled: context.mode === "ultra",
    reasoning_effort:
      context.reasoning_effort ??
      (context.mode === "ultra"
        ? "high"
        : context.mode === "pro"
          ? "medium"
          : context.mode === "thinking"
            ? "low"
            : undefined),
    thread_id: threadId,
    ...runtimeContext,
  };
}
