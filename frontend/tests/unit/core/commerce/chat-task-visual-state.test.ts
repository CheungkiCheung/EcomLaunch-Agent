import { describe, expect, it } from "vitest";

import {
  reduceCommerceTaskVisualState,
  type CommerceSubagentTaskEvent,
  type CommerceSubagentTaskSnapshot,
} from "@/core/commerce/chat-task-visual-state";

const snapshot: CommerceSubagentTaskSnapshot = {
  task_id: "task-explore",
  thread_id: "thread-1",
  run_id: "run-1",
  parent_task_id: null,
  subagent_type: "explore",
  description: "检查履约数据能力",
  status: "queued",
  context_packet: {
    available_skills: ["fulfillment-investigation"],
    available_tools: ["commerce_dataset_profile", "commerce_capabilities"],
    budget: { max_tool_rounds: 1 },
  },
  created_at: "2026-07-26T00:00:00+00:00",
  updated_at: "2026-07-26T00:00:00+00:00",
  completed_at: null,
};

function event(
  seq: number,
  event_type: string,
  payload: Record<string, unknown> = {},
): CommerceSubagentTaskEvent {
  return {
    id: `event-${seq}`,
    task_id: snapshot.task_id,
    thread_id: snapshot.thread_id,
    run_id: snapshot.run_id,
    seq,
    event_type,
    payload,
    created_at: `2026-07-26T00:00:0${seq}+00:00`,
  };
}

describe("reduceCommerceTaskVisualState", () => {
  it("orders events by sequence and derives activity only from event types", () => {
    const result = reduceCommerceTaskVisualState(snapshot, [
      event(3, "task.tool_result", { tool_name: "commerce_capabilities" }),
      event(1, "task.created"),
      event(2, "task.running"),
      event(4, "task.completed"),
    ]);

    expect(result.wasReordered).toBe(true);
    expect(result.state.status).toBe("completed");
    expect(result.state.activity).toBe("completed");
    expect(result.state.latestToolName).toBe("commerce_capabilities");
    expect(result.appliedEventIds).toEqual([
      "event-1",
      "event-2",
      "event-3",
      "event-4",
    ]);
  });

  it("keeps waiting approval and blocked as explicit non-busy states", () => {
    const waiting = reduceCommerceTaskVisualState(snapshot, [
      event(1, "task.running"),
      event(2, "task.waiting_approval", { wait_reason: "需要审批" }),
    ]);
    const blocked = reduceCommerceTaskVisualState(snapshot, [
      event(1, "task.running"),
      event(2, "task.recovery_blocked", { wait_reason: "Worker 重启" }),
    ]);

    expect(waiting.state).toMatchObject({
      status: "approval",
      activity: "waiting",
      waitReason: "需要审批",
    });
    expect(blocked.state).toMatchObject({
      status: "blocked",
      activity: "blocked",
      waitReason: "Worker 重启",
    });
  });

  it("deduplicates repeated events and preserves unknown events without guessing", () => {
    const result = reduceCommerceTaskVisualState(snapshot, [
      event(1, "task.created"),
      event(2, "task.future_event", { status: "running" }),
      event(2, "task.future_event", { status: "completed" }),
    ]);

    expect(result.state.status).toBe("queued");
    expect(result.state.activity).toBe("idle");
    expect(result.unknownEvents).toEqual([
      { eventType: "task.future_event", seq: 2 },
    ]);
    expect(result.appliedEventIds).toEqual(["event-1", "event-2"]);
  });

  it("uses the persisted task snapshot when no event has arrived", () => {
    const running = reduceCommerceTaskVisualState(
      { ...snapshot, status: "running" },
      [],
    );

    expect(running.state).toMatchObject({
      status: "working",
      activity: "idle",
    });
    expect(running.wasReordered).toBe(false);
  });

  it.each([
    ["queued", "queued", "idle"],
    ["running", "working", "idle"],
    ["waiting", "waiting", "waiting"],
    ["waiting_approval", "approval", "waiting"],
    ["blocked", "blocked", "blocked"],
    ["completed", "completed", "completed"],
    ["failed", "failed", "failed"],
    ["cancelled", "cancelled", "cancelled"],
    ["timed_out", "timed_out", "timed_out"],
  ] as const)(
    "projects persisted %s without inventing activity",
    (persistedStatus, visualStatus, activity) => {
      const result = reduceCommerceTaskVisualState(
        { ...snapshot, status: persistedStatus },
        [],
      );

      expect(result.state).toMatchObject({
        status: visualStatus,
        activity,
      });
      expect(result.state.lastEventSeq).toBe(0);
    },
  );

  it("keeps cancelled and timed out as distinct terminal states after lease release", () => {
    const cancelled = reduceCommerceTaskVisualState(snapshot, [
      event(1, "task.running"),
      event(2, "task.cancelled"),
      event(3, "task.lease_released"),
    ]);
    const timedOut = reduceCommerceTaskVisualState(snapshot, [
      event(1, "task.running"),
      event(2, "task.timed_out"),
      event(3, "task.lease_released"),
    ]);

    expect(cancelled.state).toMatchObject({
      status: "cancelled",
      activity: "cancelled",
    });
    expect(timedOut.state).toMatchObject({
      status: "timed_out",
      activity: "timed_out",
    });
  });

  it("does not turn a failed terminal task idle when its lease is released", () => {
    const failed = reduceCommerceTaskVisualState(snapshot, [
      event(1, "task.running"),
      event(2, "task.failed"),
      event(3, "task.lease_released"),
    ]);

    expect(failed.state).toMatchObject({
      status: "failed",
      activity: "failed",
    });
  });

  it("keeps delayed tool and message events from reviving non-working tasks", () => {
    const approval = reduceCommerceTaskVisualState(snapshot, [
      event(1, "task.running"),
      event(2, "task.waiting_approval", { wait_reason: "需要审批" }),
      event(3, "task.tool_result", { tool_name: "commerce_capabilities" }),
    ]);
    const completed = reduceCommerceTaskVisualState(snapshot, [
      event(1, "task.running"),
      event(2, "task.completed"),
      event(3, "task.message", { content_preview: "延迟到达的摘要" }),
      event(4, "task.lease_renewed"),
    ]);

    expect(approval.state).toMatchObject({
      status: "approval",
      activity: "waiting",
      latestToolName: "commerce_capabilities",
    });
    expect(completed.state).toMatchObject({
      status: "completed",
      activity: "completed",
      latestMessagePreview: "延迟到达的摘要",
    });
  });

  it("compacts verbose task messages before projecting them into the game drawer", () => {
    const result = reduceCommerceTaskVisualState(snapshot, [
      event(1, "task.running"),
      event(2, "task.message", {
        content_preview: `## 完整分析\n${"| 指标 | 基准 | 当前 |\n".repeat(40)}`,
      }),
    ]);

    expect(result.state.latestMessagePreview?.length).toBeLessThanOrEqual(240);
    expect(result.state.latestMessagePreview).not.toContain("\n");
    expect(result.state.latestMessagePreview).not.toContain("##");
    expect(result.state.latestMessagePreview).toMatch(/…$/);
  });
});
