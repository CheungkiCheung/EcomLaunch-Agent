import { describe, expect, test } from "vitest";

import {
  buildCommerceCollaborationSceneViewModel,
  type CommerceRunTaskActivityViewModel,
} from "@/core/commerce";

describe("buildCommerceCollaborationSceneViewModel", () => {
  test("creates exactly one event-backed actor for every durable task", () => {
    const scene = buildCommerceCollaborationSceneViewModel(
      activityView([
        item({
          taskId: "task-explore",
          profile: "explore",
          profileLabel: "探索",
          status: "working",
          activity: "tool",
          latestToolName: "commerce_dataset_profile",
        }),
        item({
          taskId: "task-verifier",
          profile: "verifier",
          profileLabel: "核验",
          status: "approval",
          activity: "waiting",
          statusLabel: "等待审批",
          detailLabel: "需要确认数据权限",
          waitReason: "需要确认数据权限",
        }),
        item({
          taskId: "task-operator",
          profile: "operator",
          profileLabel: "执行",
          status: "completed",
          activity: "completed",
          statusLabel: "已完成",
          detailLabel: "任务已完成",
        }),
      ]),
    );

    expect(scene.sceneStatus).toBe("active");
    expect(scene.actors).toHaveLength(3);
    expect(scene.actors).toEqual([
      expect.objectContaining({
        actorId: "task:task-explore",
        taskId: "task-explore",
        station: "intake",
        motion: "tool",
        propLabel: "数据概览",
      }),
      expect.objectContaining({
        actorId: "task:task-verifier",
        taskId: "task-verifier",
        station: "approval",
        motion: "waiting",
        detailLabel: "需要确认数据权限",
      }),
      expect.objectContaining({
        actorId: "task:task-operator",
        taskId: "task-operator",
        station: "action",
        motion: "completed",
      }),
    ]);
    expect(new Set(scene.actors.map((actor) => actor.taskId)).size).toBe(3);
  });

  test("keeps completed actors at their profile stations to avoid a terminal pile-up", () => {
    const scene = buildCommerceCollaborationSceneViewModel(
      activityView([
        item({ taskId: "explore", profile: "explore", status: "completed" }),
        item({ taskId: "analyst", profile: "analyst", status: "completed" }),
        item({ taskId: "verifier", profile: "verifier", status: "completed" }),
        item({ taskId: "operator", profile: "operator", status: "completed" }),
      ]),
    );

    expect(scene.actors.map((actor) => actor.station)).toEqual([
      "intake",
      "analysis",
      "verification",
      "action",
    ]);
  });

  test("keeps the last real tool prop visible after a task completes", () => {
    const scene = buildCommerceCollaborationSceneViewModel(
      activityView([
        item({
          taskId: "completed-coverage",
          profile: "explore",
          profileLabel: "探索",
          status: "completed",
          statusLabel: "已完成",
          activity: "completed",
          latestToolName: "commerce_seller_coverage",
        }),
      ]),
    );

    expect(scene.actors[0]).toMatchObject({
      station: "intake",
      status: "completed",
      propLabel: "全量覆盖",
    });
  });

  test("keeps failed, cancelled and timed out actors distinct in recovery", () => {
    const scene = buildCommerceCollaborationSceneViewModel(
      activityView([
        item({
          taskId: "task-failed",
          status: "failed",
          activity: "failed",
        }),
        item({
          taskId: "task-cancelled",
          status: "cancelled",
          activity: "cancelled",
        }),
        item({
          taskId: "task-timeout",
          status: "timed_out",
          activity: "timed_out",
        }),
      ]),
    );

    expect(scene.sceneStatus).toBe("failed");
    expect(
      scene.actors.map(({ station, status, motion }) => ({
        station,
        status,
        motion,
      })),
    ).toEqual([
      { station: "recovery", status: "failed", motion: "failed" },
      { station: "recovery", status: "cancelled", motion: "cancelled" },
      { station: "recovery", status: "timed_out", motion: "timed_out" },
    ]);
  });

  test("renders no actors and no fake activity when the run has no tasks", () => {
    const scene = buildCommerceCollaborationSceneViewModel(activityView([]));

    expect(scene).toMatchObject({
      sceneStatus: "empty",
      actors: [],
      statusText: "当前没有协作任务",
      hasProjectionWarnings: false,
    });
  });

  test("surfaces incomplete, reordered and unknown event projections", () => {
    const view = activityView([item({ taskId: "task-one" })]);
    view.hasIncompleteEventPages = true;
    view.wasReordered = true;
    view.unknownEventCount = 2;

    const scene = buildCommerceCollaborationSceneViewModel(view);

    expect(scene.hasProjectionWarnings).toBe(true);
    expect(scene.projectionWarnings).toEqual([
      "部分任务事件尚未加载完成",
      "任务事件曾发生乱序，已按序号恢复",
      "存在 2 条未知任务事件",
    ]);
  });
});

function activityView(
  items: CommerceRunTaskActivityViewModel["items"],
): CommerceRunTaskActivityViewModel {
  return {
    title: "协作任务",
    summary: {
      total: items.length,
      active: items.filter((entry) => entry.status === "working").length,
      waiting: items.filter((entry) =>
        ["waiting", "approval"].includes(entry.status),
      ).length,
      blocked: items.filter((entry) => entry.status === "blocked").length,
      completed: items.filter((entry) => entry.status === "completed").length,
      failed: items.filter((entry) => entry.status === "failed").length,
      cancelled: items.filter((entry) => entry.status === "cancelled").length,
      timedOut: items.filter((entry) => entry.status === "timed_out").length,
    },
    items,
    hasIncompleteEventPages: false,
    unknownEventCount: 0,
    wasReordered: false,
  };
}

function item(
  overrides: Partial<CommerceRunTaskActivityViewModel["items"][number]> &
    Pick<CommerceRunTaskActivityViewModel["items"][number], "taskId">,
): CommerceRunTaskActivityViewModel["items"][number] {
  return {
    parentTaskId: null,
    title: "调查当前经营问题",
    profile: "analyst",
    profileLabel: "分析",
    statusLabel: "进行中",
    detailLabel: "任务运行中，等待下一条事件",
    status: "working",
    activity: "idle",
    latestToolName: null,
    latestMessagePreview: null,
    waitReason: null,
    availableSkills: ["commerce-diagnostic-synthesis"],
    availableTools: ["commerce_dataset_profile"],
    budget: { max_tool_rounds: 2 },
    lastEventSeq: 1,
    unknownEventCount: 0,
    ...overrides,
  };
}
