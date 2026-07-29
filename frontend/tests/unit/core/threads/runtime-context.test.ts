import { describe, expect, it } from "vitest";

import { buildThreadRunContext } from "@/core/threads/runtime-context";

describe("buildThreadRunContext", () => {
  it("keeps the normal mode-derived runtime behavior", () => {
    expect(
      buildThreadRunContext({
        context: {
          mode: "pro",
          model_name: "model-a",
          reasoning_effort: undefined,
        },
        threadId: "thread-1",
      }),
    ).toMatchObject({
      model_name: "model-a",
      thinking_enabled: true,
      is_plan_mode: true,
      subagent_enabled: false,
      reasoning_effort: "medium",
      thread_id: "thread-1",
    });
  });

  it("supports Flash reasoning with bounded EcomLaunch subagents and no todo-planning overhead", () => {
    expect(
      buildThreadRunContext({
        context: {
          mode: "flash",
          model_name: "model-a",
          reasoning_effort: "minimal",
        },
        extraContext: { agent_name: "ecom-launch" },
        runtimeContext: {
          is_plan_mode: false,
          subagent_enabled: true,
          max_concurrent_subagents: 2,
        },
        threadId: "thread-2",
      }),
    ).toMatchObject({
      agent_name: "ecom-launch",
      thinking_enabled: false,
      is_plan_mode: false,
      subagent_enabled: true,
      reasoning_effort: "minimal",
      max_concurrent_subagents: 2,
      thread_id: "thread-2",
    });
  });
});
