import type { Message } from "@langchain/langgraph-sdk";
import { describe, expect, it } from "vitest";

import {
  buildWarRoomSnapshot,
  hydrateWarRoomThread,
} from "@/components/workspace/war-room/adapter";
import { zhCN } from "@/core/i18n/locales/zh-CN";
import type { AgentThread } from "@/core/threads/types";

function thread(
  agentName: string,
  messages: Message[],
  artifacts: string[] = [],
): AgentThread {
  return {
    thread_id: `${agentName}-thread`,
    context: { agent_name: agentName } as AgentThread["context"],
    values: { title: "Test", messages, artifacts },
  } as AgentThread;
}

describe("buildWarRoomSnapshot", () => {
  it("always exposes the six configured real actors", () => {
    const snapshot = buildWarRoomSnapshot({});
    expect(snapshot.actors).toHaveLength(6);
    expect(snapshot.actors.map((actor) => actor.id)).toEqual([
      "ecom-launch",
      "market-voc-researcher",
      "offer-architect",
      "asset-studio",
      "evidence-checker",
      "data-inspector",
    ]);
    expect(snapshot.actors.every((actor) => actor.status === "idle")).toBe(
      true,
    );
  });

  it("localizes actor names, summaries, and pipeline labels without changing actor IDs", () => {
    const snapshot = buildWarRoomSnapshot({}, zhCN.warRoom);

    expect(snapshot.actors.map((actor) => actor.id)).toEqual([
      "ecom-launch",
      "market-voc-researcher",
      "offer-architect",
      "asset-studio",
      "evidence-checker",
      "data-inspector",
    ]);
    expect(snapshot.actors[0]?.name).toBe("OpenSKU 上新团队");
    expect(snapshot.actors[0]?.summary).toBe(
      "当前待命，等待新的真实任务事件。",
    );
    expect(snapshot.stages.map((stage) => stage.label)).toEqual([
      "分析需求",
      "市场研究",
      "方案设计",
      "内容生成",
      "打包交付",
      "确定性预检",
      "完成",
    ]);
  });

  it("shows the deterministic preflight stage while the atomic renderer is running", () => {
    const messages = [
      { id: "human-1", type: "human", content: "输出 Launch Validation Pack" },
      {
        id: "ai-1",
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
    ] as Message[];

    const snapshot = buildWarRoomSnapshot({
      ecomThread: thread("ecom-launch", messages),
      ecomRunStatus: "running",
    });

    expect(
      snapshot.stages.find((stage) => stage.id === "preflight"),
    ).toMatchObject({
      current: true,
      done: false,
    });
  });

  it("marks preflight complete after the renderer returns its success result", () => {
    const messages = [
      { id: "human-1", type: "human", content: "输出 Launch Validation Pack" },
      {
        id: "ai-1",
        type: "ai",
        content: "",
        tool_calls: [
          { id: "render-1", name: "render_launch_pack", args: { spec: {} } },
        ],
      },
      {
        id: "tool-1",
        type: "tool",
        tool_call_id: "render-1",
        content: "Successfully presented files",
      },
    ] as Message[];

    const snapshot = buildWarRoomSnapshot({
      ecomThread: thread("ecom-launch", messages),
      ecomRunStatus: "success",
    });

    expect(
      snapshot.stages.find((stage) => stage.id === "preflight"),
    ).toMatchObject({
      current: false,
      done: true,
    });
    expect(snapshot.stages.at(-1)).toMatchObject({ id: "done", current: true });
  });

  it("keeps the final stage pending until the run itself succeeds", () => {
    const messages = [
      { id: "human-1", type: "human", content: "输出 Launch Validation Pack" },
      {
        id: "ai-1",
        type: "ai",
        content: "",
        tool_calls: [
          { id: "render-1", name: "render_launch_pack", args: { spec: {} } },
        ],
      },
      {
        id: "tool-1",
        type: "tool",
        tool_call_id: "render-1",
        content: "Successfully presented files",
      },
    ] as Message[];

    const snapshot = buildWarRoomSnapshot({
      ecomThread: thread("ecom-launch", messages),
      ecomRunStatus: "running",
    });

    expect(
      snapshot.stages.find((stage) => stage.id === "preflight"),
    ).toMatchObject({
      current: true,
      done: false,
    });
    expect(snapshot.stages.at(-1)).toMatchObject({
      id: "done",
      current: false,
    });
  });

  it("maps a real EcomLaunch task call and result to its configured actor", () => {
    const messages = [
      {
        id: "human-1",
        type: "human",
        content: "研究这个商品的用户反馈",
      },
      {
        id: "ai-1",
        type: "ai",
        content: "",
        tool_calls: [
          {
            id: "task-1",
            name: "task",
            args: {
              subagent_type: "market-voc-researcher",
              description: "研究小红书和评论区用户反馈",
              prompt: "查找真实市场和 VOC 信号",
            },
          },
        ],
      },
    ] as Message[];
    const snapshot = buildWarRoomSnapshot({
      ecomThread: thread("ecom-launch", messages),
      ecomRunStatus: "running",
    });
    const researcher = snapshot.actors.find(
      (actor) => actor.id === "market-voc-researcher",
    );
    expect(researcher?.status).toBe("working");
    expect(researcher?.activity).toBe("searching");
    expect(researcher?.task).toContain("用户反馈");
    expect(snapshot.activeCount).toBe(2);
  });

  it("maps Data Inspector tools and artifacts without inventing subagents", () => {
    const messages = [
      { id: "human-1", type: "human", content: "分析这个店铺数据" },
      {
        id: "ai-1",
        type: "ai",
        content: "",
        tool_calls: [
          { id: "tool-1", name: "inspect_data", args: { filenames: [] } },
        ],
      },
    ] as Message[];
    const snapshot = buildWarRoomSnapshot({
      dataThread: thread("data-inspector", messages, ["analysis.md"]),
      dataRunStatus: "running",
    });
    const inspector = snapshot.actors.find(
      (actor) => actor.id === "data-inspector",
    );
    expect(inspector?.status).toBe("working");
    expect(inspector?.activity).toBe("reading");
    expect(inspector?.tool).toBe("inspect_data");
    expect(inspector?.artifacts).toEqual(["analysis.md"]);
    expect(snapshot.actors).toHaveLength(6);
  });

  it("keeps failed and completed paths visible", () => {
    const failed = buildWarRoomSnapshot({
      dataThread: thread("data-inspector", [
        { id: "human-1", type: "human", content: "分析数据" },
      ] as Message[]),
      dataRunStatus: "error",
    });
    expect(
      failed.actors.find((actor) => actor.id === "data-inspector")?.status,
    ).toBe("failed");
    expect(failed.failedCount).toBe(1);

    const completed = buildWarRoomSnapshot({
      dataThread: thread("data-inspector", [
        { id: "human-1", type: "human", content: "分析数据" },
      ] as Message[]),
      dataRunStatus: "success",
    });
    expect(
      completed.actors.find((actor) => actor.id === "data-inspector")?.status,
    ).toBe("done");
    expect(completed.completedCount).toBe(1);
  });

  it("uses a successful run as completion evidence when thread search omits messages", () => {
    const metadataOnlyThread = {
      thread_id: "data-inspector-thread",
      context: { agent_name: "data-inspector" },
    } as AgentThread;

    const snapshot = buildWarRoomSnapshot({
      dataThread: metadataOnlyThread,
      dataRunStatus: "success",
    });
    const inspector = snapshot.actors.find(
      (actor) => actor.id === "data-inspector",
    );

    expect(inspector?.status).toBe("done");
    expect(inspector?.threadId).toBe("data-inspector-thread");
    expect(inspector?.href).toBe(
      "/workspace/agents/data-inspector/chats/data-inspector-thread",
    );
    expect(snapshot.completedCount).toBe(1);
  });

  it("hydrates thread-search metadata with the latest checkpoint before counting artifacts", () => {
    const metadataOnlyThread = {
      thread_id: "ecom-launch-thread",
      context: { agent_name: "ecom-launch" },
    } as AgentThread;
    const hydrated = hydrateWarRoomThread(metadataOnlyThread, {
      values: {
        title: "Launch complete",
        messages: [],
        artifacts: ["one.md", "two.csv"],
      },
    });

    const snapshot = buildWarRoomSnapshot({
      ecomThread: hydrated,
      ecomRunStatus: "success",
    });

    expect(snapshot.artifactCount).toBe(2);
    expect(
      snapshot.actors.find((actor) => actor.id === "ecom-launch")?.artifacts,
    ).toEqual(["one.md", "two.csv"]);
    expect(snapshot.runTitle).toBe("Launch complete");
  });
});
