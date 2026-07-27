import { describe, expect, test } from "vitest";

import {
  buildCommerceRunTaskActivityViewModel,
  type CommerceRunTaskActivity,
} from "@/core/commerce";

describe("buildCommerceRunTaskActivityViewModel", () => {
  test("projects compact Chat and collaboration state from the same task events", () => {
    const view = buildCommerceRunTaskActivityViewModel([
      activity("task-explore", "explore", "completed", [
        event("task-explore", 1, "task.created"),
        event("task-explore", 2, "task.running"),
        event("task-explore", 3, "task.completed"),
      ]),
      activity("task-analyst", "analyst", "running", [
        event("task-analyst", 1, "task.created"),
        event("task-analyst", 2, "task.running"),
        event("task-analyst", 3, "task.tool_result", {
          tool_name: "commerce_compare_windows",
        }),
      ]),
      activity("task-verifier", "verifier", "waiting_approval", [
        event("task-verifier", 1, "task.waiting_approval", {
          wait_reason: "需要确认数据权限",
        }),
      ]),
    ]);

    expect(view.summary).toEqual({
      total: 3,
      active: 1,
      waiting: 1,
      blocked: 0,
      completed: 1,
      failed: 0,
      cancelled: 0,
      timedOut: 0,
    });
    expect(view.items).toEqual([
      expect.objectContaining({
        taskId: "task-explore",
        profileLabel: "探索",
        statusLabel: "已完成",
        detailLabel: "任务已完成",
      }),
      expect.objectContaining({
        taskId: "task-analyst",
        profileLabel: "分析",
        statusLabel: "进行中",
        detailLabel: "正在使用：窗口对比",
      }),
      expect.objectContaining({
        taskId: "task-verifier",
        profileLabel: "核验",
        statusLabel: "等待审批",
        detailLabel: "需要确认数据权限",
      }),
    ]);
  });

  test("keeps unknown events and incomplete event pages explicit", () => {
    const item = activity("task-future", "future-profile", "running", [
      event("task-future", 2, "task.future"),
      event("task-future", 1, "task.running"),
    ]);
    item.hasMore = true;

    const view = buildCommerceRunTaskActivityViewModel([item]);

    expect(view.hasIncompleteEventPages).toBe(true);
    expect(view.unknownEventCount).toBe(1);
    expect(view.wasReordered).toBe(true);
    expect(view.items[0]).toMatchObject({
      profileLabel: "future-profile",
      statusLabel: "进行中",
    });
  });

  test("reports failed, cancelled and timed out tasks separately", () => {
    const view = buildCommerceRunTaskActivityViewModel([
      activity("task-failed", "analyst", "failed", [
        event("task-failed", 1, "task.failed"),
        event("task-failed", 2, "task.lease_released"),
      ]),
      activity("task-cancelled", "explore", "cancelled", [
        event("task-cancelled", 1, "task.cancelled"),
        event("task-cancelled", 2, "task.lease_released"),
      ]),
      activity("task-timeout", "verifier", "timed_out", [
        event("task-timeout", 1, "task.timed_out"),
        event("task-timeout", 2, "task.lease_released"),
      ]),
    ]);

    expect(view.summary).toEqual({
      total: 3,
      active: 0,
      waiting: 0,
      blocked: 0,
      completed: 0,
      failed: 1,
      cancelled: 1,
      timedOut: 1,
    });
    expect(view.items).toEqual([
      expect.objectContaining({
        status: "failed",
        statusLabel: "未完成",
        detailLabel: "任务未完成，可查看原因",
      }),
      expect.objectContaining({
        status: "cancelled",
        statusLabel: "已取消",
        detailLabel: "任务已取消",
      }),
      expect.objectContaining({
        status: "timed_out",
        statusLabel: "已超时",
        detailLabel: "任务已超时",
      }),
    ]);
  });
});

function activity(
  taskId: string,
  profile: string,
  status: CommerceRunTaskActivity["task"]["status"],
  events: CommerceRunTaskActivity["events"],
): CommerceRunTaskActivity {
  return {
    task: {
      task_id: taskId,
      thread_id: "thread-1",
      run_id: "run-1",
      user_id: "user-1",
      parent_task_id: null,
      subagent_type: profile,
      description: `${profile} task`,
      context_packet: {
        schema_version: "deerflow.subagent-context@1.0.0",
        goal: "调查",
        source_refs: [],
        evidence_refs: [],
        constraints: {},
        available_skills: ["fulfillment-investigation"],
        available_tools: ["commerce_compare_windows"],
        budget: { max_tool_rounds: 2 },
        expected_output_schema: {},
        metadata: {},
      },
      tool_policy: {},
      depends_on: [],
      metadata: {},
      status,
      result: null,
      error: null,
      checkpoint: null,
      telemetry: {},
      wait_reason: null,
      version: 1,
      event_seq: 1,
      attempt: 1,
      max_attempts: 2,
      priority: 0,
      lease_owner: null,
      lease_token: 0,
      lease_expires_at: null,
      created_at: "2026-07-26T00:00:00+00:00",
      updated_at: "2026-07-26T00:00:00+00:00",
      started_at: null,
      completed_at: null,
    },
    events,
    nextAfterSeq: events.at(-1)?.seq ?? 0,
    hasMore: false,
  };
}

function event(
  taskId: string,
  seq: number,
  event_type: string,
  payload: Record<string, unknown> = {},
): CommerceRunTaskActivity["events"][number] {
  return {
    task_id: taskId,
    thread_id: "thread-1",
    run_id: "run-1",
    seq,
    event_type,
    payload,
    idempotency_key: null,
    created_at: `2026-07-26T00:00:0${seq}+00:00`,
  };
}
