import type { Message } from "@langchain/langgraph-sdk";
import { describe, expect, it } from "vitest";

import {
  buildStoreCrewActivity,
  storeTasksFromMessages,
} from "@/components/workspace/store-operator/store-crew-activity";

const taskCall = {
  type: "ai",
  content: "",
  tool_calls: [
    {
      id: "task-1",
      name: "task",
      args: {
        subagent_type: "analyst",
        description: "比较近期经营变化",
        prompt: "使用数据工具比较两个窗口",
      },
    },
  ],
} as Message;

describe("store crew activity", () => {
  it("maps a real task tool call to the matching working agent", () => {
    const activity = buildStoreCrewActivity([taskCall], false);

    expect(activity.agents.find((agent) => agent.id === "lead")?.active).toBe(
      true,
    );
    expect(
      activity.agents.find((agent) => agent.id === "analyst"),
    ).toMatchObject({
      active: true,
      status: "working",
      lastLine: "比较近期经营变化",
    });
    expect(
      activity.agents.find((agent) => agent.id === "explore")?.active,
    ).toBe(false);
  });

  it("returns a completed subagent to idle instead of showing fake work", () => {
    const completion = {
      type: "tool",
      tool_call_id: "task-1",
      content: "Task Succeeded. Result: done",
      additional_kwargs: { subagent_status: "completed" },
    } as Message;

    const activity = buildStoreCrewActivity([taskCall, completion], false);
    const analyst = activity.agents.find((agent) => agent.id === "analyst");

    expect(analyst?.active).toBe(false);
    expect(analyst?.lastLine).toContain("已完成");
    expect(activity.completedCount).toBe(1);
  });

  it("hides raw runtime errors behind a concise Chinese failure message", () => {
    const failure = {
      type: "tool",
      tool_call_id: "task-1",
      content: "Task Failed",
      additional_kwargs: {
        subagent_status: "failed",
        subagent_error: "Recursion limit of 24 reached",
      },
    } as Message;

    const activity = buildStoreCrewActivity([taskCall, failure], false);
    const analyst = activity.agents.find((agent) => agent.id === "analyst");

    expect(analyst).toMatchObject({
      active: false,
      status: "failed",
      lastLine: "任务未能在执行预算内完成。",
    });
  });

  it("does not mark the lead as busy for a background state refresh", () => {
    const activity = buildStoreCrewActivity([], false);

    expect(activity.agents.find((agent) => agent.id === "lead")).toMatchObject({
      active: false,
      status: "idle",
    });
  });

  it("ignores unrelated specialist profiles", () => {
    const unrelated = {
      ...taskCall,
      tool_calls: [
        {
          id: "task-2",
          name: "task",
          args: { subagent_type: "market-voc-researcher" },
        },
      ],
    } as Message;

    expect(storeTasksFromMessages([unrelated])).toEqual([]);
  });
});
