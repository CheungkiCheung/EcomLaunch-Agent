import type { Message } from "@langchain/langgraph-sdk";
import { describe, expect, it } from "vitest";

import { buildWarRoomReplay } from "@/components/workspace/war-room/run-replay";
import type { WarRoomSource } from "@/components/workspace/war-room/types";
import { zhCN } from "@/core/i18n/locales/zh-CN";
import type { AgentThread } from "@/core/threads/types";

function source(messages: Message[], artifacts: string[] = []): WarRoomSource {
  const ecomThread = {
    thread_id: "launch-thread",
    context: { agent_name: "ecom-launch" },
    values: {
      title: "通勤咖啡杯验证",
      messages,
      artifacts,
    },
  } as AgentThread;
  return { ecomThread, ecomRunStatus: "success" };
}

describe("buildWarRoomReplay", () => {
  it("replays the latest real request and ignores older turns", () => {
    const messages = [
      { id: "old-human", type: "human", content: "旧任务" },
      { id: "new-human", type: "human", content: "研究通勤咖啡杯" },
      {
        id: "handoff",
        type: "ai",
        content: "",
        tool_calls: [
          {
            id: "task-1",
            name: "task",
            args: {
              subagent_type: "market-voc-researcher",
              description: "采集公开用户声音",
            },
          },
        ],
      },
      {
        id: "task-result",
        type: "tool",
        tool_call_id: "task-1",
        content: "Task Succeeded. Result: 发现价格带信号",
        additional_kwargs: { subagent_status: "completed" },
      },
      {
        id: "verify",
        type: "ai",
        content: "",
        tool_calls: [
          {
            id: "render-1",
            name: "render_launch_pack",
            args: { spec: { category: "coffee mug" } },
          },
        ],
      },
      {
        id: "delivery",
        type: "tool",
        tool_call_id: "render-1",
        content: "Successfully presented files",
      },
      { id: "final", type: "ai", content: "建议进入 7 天验证。" },
    ] as Message[];

    const replay = buildWarRoomReplay(
      source(messages, ["launch-war-room.html"]),
      zhCN.warRoom,
    );

    expect(replay?.events.map((event) => event.kind)).toEqual([
      "request",
      "handoff",
      "observation",
      "verification",
      "delivery",
      "observation",
      "completed",
    ]);
    expect(replay?.events[0]?.detail).toBe("研究通勤咖啡杯");
    expect(replay?.events[1]?.actorId).toBe("market-voc-researcher");
    expect(replay?.events.at(-1)?.snapshot.runStatus).toBe("success");
    expect(
      replay?.events.at(-1)?.snapshot.artifactCount,
    ).toBeGreaterThanOrEqual(1);
  });

  it("does not create a replay from a thread without a real request flow", () => {
    const replay = buildWarRoomReplay(source([]), zhCN.warRoom);
    expect(replay).toBeNull();
  });
});
