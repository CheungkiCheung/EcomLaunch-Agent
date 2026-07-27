import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceCollaborationSpaceView } from "@/components/commerce/collaboration-space-view";
import type {
  CommerceCollaborationActorViewModel,
  CommerceCollaborationSceneViewModel,
} from "@/core/commerce/collaboration-scene-view-model";

describe("CommerceCollaborationSpaceView", () => {
  test("shows an honest empty state without a fixed crew", () => {
    const markup = renderToStaticMarkup(
      createElement(CommerceCollaborationSpaceView, {
        scene: scene([]),
        title: "协作空间",
        threadId: "thread-1",
        runId: null,
        backHref: "/workspace/agents/commerce-agent/chats/thread-1",
        selectedTaskId: null,
        isLoading: false,
        error: null,
        onSelectTask: () => undefined,
      }),
    );
    const text = visibleText(markup);

    expect(text).toContain("当前没有真实协作任务");
    expect(text).toContain("主智能体");
    expect(text).toContain("人物与动作来自真实任务/事件");
    expect(text).toContain("尚无运行");
    expect(markup).not.toContain("data-commerce-actor=");
    expect(markup).toContain(
      'data-commerce-room-sprite="/commerce/collaboration/commerce-room-v1.png"',
    );
    expect(markup).not.toContain("data-commerce-actor-sprite=");
    expect(markup).not.toContain("data-commerce-station-sprite=");
    expect(text).not.toContain("Launch Crew");
    expect(text).not.toContain("Parent");
    expect(text).not.toContain("Task/Event");
    expect(text).not.toContain("Thread");
    expect(text).not.toContain("Run");
  });

  test("renders one original actor per real task and an on-demand detail drawer", () => {
    const actors = [
      actor("task-explore", "探索", "intake", "completed", "任务已完成"),
      actor(
        "task-analyst",
        "分析",
        "analysis",
        "working",
        "正在使用：窗口对比",
        "窗口对比",
      ),
      actor(
        "task-verifier",
        "核验",
        "verification",
        "approval",
        "等待确认数据权限",
      ),
    ];
    const markup = renderToStaticMarkup(
      createElement(CommerceCollaborationSpaceView, {
        scene: scene(actors),
        title: "履约延迟为什么上升",
        threadId: "thread-1",
        runId: "run-1",
        backHref: "/workspace/agents/commerce-agent/chats/thread-1",
        selectedTaskId: "task-analyst",
        isLoading: false,
        error: null,
        onSelectTask: () => undefined,
      }),
    );
    const text = visibleText(markup);

    expect(markup.match(/data-commerce-actor=/gu)).toHaveLength(3);
    expect(markup).toContain('data-commerce-task-id="task-explore"');
    expect(markup).toContain('data-commerce-task-id="task-analyst"');
    expect(markup).toContain('data-commerce-task-id="task-verifier"');
    expect(text).toContain("探索");
    expect(text).toContain("分析");
    expect(text).toContain("核验");
    expect(text).toContain("窗口对比");
    expect(text).toContain("数据接入工位");
    expect(text).toContain("指标分析工位");
    expect(text).toContain("证据核验工位");
    expect(text).toContain("当前任务详情");
    expect(text).toContain("正在使用：窗口对比");
    expect(text).toContain("查看审计信息");
    expect(text).toContain("task-analyst");
    expect(text).toContain("人物与动作来自真实任务/事件");
    expect(markup.match(/data-commerce-task-station=/gu)).toHaveLength(3);
    expect(markup.match(/data-commerce-actor-sprite=/gu)).toHaveLength(3);
    expect(markup.match(/data-commerce-station-sprite=/gu)).toHaveLength(3);
    expect(markup).toContain(
      'data-commerce-actor-sprite="/commerce/collaboration/actors/explore-v1.png"',
    );
    expect(markup).toContain(
      'data-commerce-actor-sprite="/commerce/collaboration/actors/analyst-v1.png"',
    );
    expect(markup).toContain(
      'data-commerce-actor-sprite="/commerce/collaboration/actors/verifier-v1.png"',
    );
    expect(markup).toContain(
      'data-commerce-station-sprite="/commerce/collaboration/stations/intake-v1.png"',
    );
    expect(markup).toContain(
      'data-commerce-station-sprite="/commerce/collaboration/stations/analysis-v1.png"',
    );
    expect(markup).toContain(
      'data-commerce-station-sprite="/commerce/collaboration/stations/verification-v1.png"',
    );
  });

  test("surfaces projection warnings and distinct terminal states", () => {
    const view = scene([
      actor("failed", "分析", "recovery", "failed", "任务未完成"),
      actor("cancelled", "探索", "recovery", "cancelled", "任务已取消"),
      actor("timeout", "核验", "recovery", "timed_out", "任务已超时"),
    ]);
    view.hasProjectionWarnings = true;
    view.projectionWarnings = ["存在 1 条未知任务事件"];

    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceCollaborationSpaceView, {
          scene: view,
          title: "协作空间",
          threadId: "thread-1",
          runId: "run-1",
          backHref: "/workspace/agents/commerce-agent/chats/thread-1",
          selectedTaskId: null,
          isLoading: false,
          error: null,
          onSelectTask: () => undefined,
        }),
      ),
    );

    expect(text).toContain("任务未完成");
    expect(text).toContain("任务已取消");
    expect(text).toContain("任务已超时");
    expect(text).toContain("存在 1 条未知任务事件");
  });
});

function scene(
  actors: CommerceCollaborationActorViewModel[],
): CommerceCollaborationSceneViewModel {
  return {
    sceneStatus: actors.length === 0 ? "empty" : "active",
    statusText:
      actors.length === 0
        ? "当前没有协作任务"
        : `${actors.length} 个子任务正在协作`,
    actors,
    hasProjectionWarnings: false,
    projectionWarnings: [],
  };
}

function actor(
  taskId: string,
  profileLabel: string,
  station: CommerceCollaborationActorViewModel["station"],
  status: CommerceCollaborationActorViewModel["status"],
  detailLabel: string,
  propLabel: string | null = null,
): CommerceCollaborationActorViewModel {
  const profile =
    profileLabel === "探索"
      ? "explore"
      : profileLabel === "分析"
        ? "analyst"
        : profileLabel === "核验"
          ? "verifier"
          : "operator";
  return {
    actorId: `task:${taskId}`,
    taskId,
    parentTaskId: null,
    placementKey: taskId,
    title: `${profileLabel}当前经营问题`,
    profile,
    profileLabel,
    station,
    status,
    statusLabel: status,
    motion: status === "working" ? "tool" : "idle",
    detailLabel,
    propLabel,
    messagePreview: null,
    availableSkills: ["fulfillment-investigation"],
    availableTools: ["commerce_compare_windows"],
    budget: { max_tool_rounds: 2 },
    lastEventSeq: 3,
    ariaLabel: `${profileLabel}子任务，${status}，${detailLabel}`,
  };
}

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
