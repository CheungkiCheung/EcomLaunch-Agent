import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceRunActivityStrip } from "@/components/commerce/run-activity-strip";
import type { CommerceRunTaskActivityViewModel } from "@/core/commerce/run-task-activity-view-model";

describe("CommerceRunActivityStrip", () => {
  test("stays absent when no durable task exists", () => {
    const markup = renderToStaticMarkup(
      createElement(CommerceRunActivityStrip, {
        viewModel: activityView([]),
        isLoading: false,
        isRefreshing: false,
        error: null,
        collaborationHref:
          "/workspace/agents/commerce-agent/war-room?threadId=thread-1",
      }),
    );

    expect(markup).toBe("");
  });

  test("renders compact real task state and the collaboration-space link", () => {
    const markup = renderToStaticMarkup(
      createElement(CommerceRunActivityStrip, {
        viewModel: activityView([
          item("task-explore", "探索", "completed", "已完成"),
          item("task-analyst", "分析", "working", "进行中"),
          item("task-verifier", "核验", "approval", "等待审批"),
        ]),
        isLoading: false,
        isRefreshing: true,
        error: null,
        collaborationHref:
          "/workspace/agents/commerce-agent/war-room?threadId=thread-1&runId=run-1",
      }),
    );
    const text = visibleText(markup);

    expect(text).toContain("3 个协作任务");
    expect(text).toContain("1 个进行中");
    expect(text).toContain("探索");
    expect(text).toContain("分析");
    expect(text).toContain("核验");
    expect(text).toContain("等待审批");
    expect(text).toContain("查看协作空间");
    expect(markup).toContain(
      "/workspace/agents/commerce-agent/war-room?threadId=thread-1&amp;runId=run-1",
    );
    expect(text).not.toContain("固定 Crew");
  });

  test("keeps failed cancelled and timed-out terminal states separate", () => {
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceRunActivityStrip, {
          viewModel: activityView([
            item("task-failed", "分析", "failed", "未完成"),
            item("task-cancelled", "探索", "cancelled", "已取消"),
            item("task-timeout", "核验", "timed_out", "已超时"),
          ]),
          isLoading: false,
          isRefreshing: false,
          error: null,
          collaborationHref:
            "/workspace/agents/commerce-agent/war-room?runId=run-1",
        }),
      ),
    );

    expect(text).toContain("未完成");
    expect(text).toContain("已取消");
    expect(text).toContain("已超时");
  });
});

function activityView(
  items: CommerceRunTaskActivityViewModel["items"],
): CommerceRunTaskActivityViewModel {
  return {
    title: "协作任务",
    summary: {
      total: items.length,
      active: items.filter((value) => value.status === "working").length,
      waiting: items.filter((value) =>
        ["waiting", "approval"].includes(value.status),
      ).length,
      blocked: items.filter((value) => value.status === "blocked").length,
      completed: items.filter((value) => value.status === "completed").length,
      failed: items.filter((value) => value.status === "failed").length,
      cancelled: items.filter((value) => value.status === "cancelled").length,
      timedOut: items.filter((value) => value.status === "timed_out").length,
    },
    items,
    hasIncompleteEventPages: false,
    unknownEventCount: 0,
    wasReordered: false,
  };
}

function item(
  taskId: string,
  profileLabel: string,
  status: CommerceRunTaskActivityViewModel["items"][number]["status"],
  statusLabel: string,
): CommerceRunTaskActivityViewModel["items"][number] {
  return {
    taskId,
    parentTaskId: null,
    title: `${profileLabel}当前经营问题`,
    profile: profileLabel,
    profileLabel,
    statusLabel,
    detailLabel: `${statusLabel}详情`,
    status,
    activity: status === "working" ? "tool" : "idle",
    latestToolName: status === "working" ? "commerce_compare_windows" : null,
    latestMessagePreview: null,
    waitReason: status === "approval" ? "需要确认数据权限" : null,
    availableSkills: [],
    availableTools: [],
    budget: {},
    lastEventSeq: 1,
    unknownEventCount: 0,
  };
}

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
