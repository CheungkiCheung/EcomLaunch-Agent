import { describe, expect, test } from "vitest";

import { buildCommerceWarRoomViewModel } from "@/core/commerce";

import {
  commerceWarRoomCase,
  commerceWarRoomCheckpoint,
  commerceWarRoomEvents,
  commerceWarRoomRun,
} from "./war-room-fixture";

describe("buildCommerceWarRoomViewModel", () => {
  test("projects only persisted event-backed activity and an honest quiet state", () => {
    const run = commerceWarRoomRun();
    const view = buildCommerceWarRoomViewModel({
      cases: [commerceWarRoomCase()],
      runs: [run],
      selectedRunId: run.id,
      selectedDetail: { run, latest_checkpoint: commerceWarRoomCheckpoint() },
      events: commerceWarRoomEvents(),
      checkpoints: [commerceWarRoomCheckpoint()],
    });

    expect(view.selected).toMatchObject({
      title: "调查履约延迟原因",
      caseTitle: "履约延迟异常",
      statusLabel: "进行中",
      latestEventLabel: "最新事件 #18 · 18:34",
      quietLabel: "等待下一条持久化事件",
      summary: [
        { label: "当前阶段", valueLabel: "并行路径" },
        { label: "循环", valueLabel: "2 / 8" },
        { label: "工具", valueLabel: "7 / 20" },
        { label: "路径", valueLabel: "2 / 3" },
      ],
      checkpointLabel:
        "最新检查点 #7 · 循环 2 · 证据 4 · 工作假设 1 · 上下文已记录",
    });
    expect(view.selected?.lanes).toEqual([
      expect.objectContaining({
        key: "goal",
        title: "目标循环",
        status: "completed",
        eventLabel: "事件 #1",
      }),
      expect.objectContaining({
        key: "fulfillment",
        title: "履约路径",
        status: "completed",
        description: "已完成 · 2 条证据",
        eventLabel: "事件 #7",
      }),
      expect.objectContaining({
        key: "seller_peer",
        title: "卖家对标",
        status: "running",
        eventLabel: "事件 #14",
      }),
      expect.objectContaining({
        key: "review_experience",
        title: "评价体验",
        status: "blocked",
        eventLabel: "事件 #10",
      }),
      expect.objectContaining({
        key: "barrier",
        title: "证据屏障",
        status: "waiting",
        eventLabel: "等待路径终态",
      }),
      expect.objectContaining({
        key: "synthesis_verification",
        title: "主智能体综合 / 新鲜上下文验证",
        status: "not_started",
        eventLabel: "尚未开始",
      }),
    ]);
    expect(view.selected?.evidenceSummary).toEqual([
      { label: "支持", countLabel: "2", tone: "support" },
      { label: "矛盾", countLabel: "1", tone: "contradict" },
      { label: "未知", countLabel: "1", tone: "unknown" },
    ]);
    expect(view.selected?.eventItems.at(-1)).toMatchObject({
      sequenceLabel: "18",
      title: "检查点已保存",
    });
    expect(JSON.stringify(view)).not.toContain("正在思考");
    expect(JSON.stringify(view)).not.toContain("模型调用");
    expect(JSON.stringify(view)).not.toContain("倒计时");
  });
});
