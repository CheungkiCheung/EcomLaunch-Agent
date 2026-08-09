import type { Message } from "@langchain/langgraph-sdk";
import { describe, expect, it } from "vitest";

import {
  buildWarRoomReplay,
  buildWarRoomReplays,
} from "@/components/workspace/war-room/run-replay";
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

function growthSource(
  messages: Message[],
  artifacts: string[] = [],
): WarRoomSource {
  const dataThread = {
    thread_id: "growth-thread",
    context: { agent_name: "data-inspector" },
    values: {
      title: "转化实验分析",
      messages,
      artifacts,
    },
  } as AgentThread;
  return {
    dataThread,
    dataRunStatus: "success",
    dataRuns: [
      {
        run_id: "growth-run",
        status: "success",
        created_at: "2026-08-09T00:00:00Z",
        updated_at: "2026-08-09T00:00:12Z",
        llm_call_count: 4,
        total_tokens: 3200,
      },
    ],
  };
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

  it("replays the real Growth Analyst data workflow and focused metrics", () => {
    const messages = [
      { id: "growth-human", type: "human", content: "分析三份增长数据" },
      {
        id: "growth-inspect-call",
        type: "ai",
        content: "",
        tool_calls: [
          {
            id: "inspect-1",
            name: "inspect_data",
            args: { filenames: ["users.csv", "events.csv", "orders.csv"] },
          },
        ],
      },
      {
        id: "growth-inspect-result",
        type: "tool",
        tool_call_id: "inspect-1",
        content: "3 tables, 200 users",
      },
      {
        id: "growth-query-call",
        type: "ai",
        content: "",
        tool_calls: [
          {
            id: "query-1",
            name: "query_data",
            args: { sql: "SELECT variant, COUNT(*) FROM experiments" },
          },
        ],
      },
      {
        id: "growth-query-result",
        type: "tool",
        tool_call_id: "query-1",
        content: "control=100, variant=100",
      },
      {
        id: "growth-experiment-call",
        type: "ai",
        content: "",
        tool_calls: [
          {
            id: "experiment-1",
            name: "analyze_ab_test",
            args: { control_conversions: 10, variant_conversions: 20 },
          },
        ],
      },
      {
        id: "growth-experiment-result",
        type: "tool",
        tool_call_id: "experiment-1",
        content: "p=0.0477; uplift=+10.00 pp; no SRM",
      },
      {
        id: "growth-final",
        type: "ai",
        content: "SHIP WITH MONITORING",
      },
    ] as Message[];

    const replays = buildWarRoomReplays(
      growthSource(messages, ["growth-decision.md"]),
      zhCN.warRoom,
    );
    const replay = replays.find(
      (candidate) => candidate.team === "data-inspector",
    );

    expect(replay?.team).toBe("data-inspector");
    expect(replay?.events.map((event) => event.title)).toContain(
      "检查上传数据",
    );
    expect(replay?.events.map((event) => event.title)).toContain(
      "跨文件 Join 与查询",
    );
    expect(replay?.events.map((event) => event.title)).toContain(
      "执行确定性实验分析",
    );
    expect(
      replay?.events
        .slice(1)
        .every((event) => event.actorId === "data-inspector"),
    ).toBe(true);

    const finalSnapshot = replay?.events.at(-1)?.snapshot;
    expect(finalSnapshot?.focusTeam).toBe("data-inspector");
    expect(finalSnapshot?.runStatus).toBe("success");
    expect(finalSnapshot?.stages.at(-1)).toMatchObject({
      id: "data-decision",
      current: true,
    });
    expect(finalSnapshot?.metrics.dataQueries).toBe(2);
    expect(finalSnapshot?.metrics.experiments).toBe(1);
    expect(finalSnapshot?.artifactCount).toBe(1);
  });
});
