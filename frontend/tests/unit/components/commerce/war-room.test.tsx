import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceWarRoomView } from "@/components/commerce/war-room";
import { buildCommerceWarRoomViewModel } from "@/core/commerce";

import {
  commerceWarRoomCase,
  commerceWarRoomCheckpoint,
  commerceWarRoomEvents,
  commerceWarRoomRun,
} from "../../core/commerce/war-room-fixture";

describe("CommerceWarRoomView", () => {
  test("renders event-backed lanes evidence checkpoint and quiet state", () => {
    const run = commerceWarRoomRun();
    const viewModel = buildCommerceWarRoomViewModel({
      cases: [commerceWarRoomCase()],
      runs: [run],
      selectedRunId: run.id,
      selectedDetail: { run, latest_checkpoint: commerceWarRoomCheckpoint() },
      events: commerceWarRoomEvents(),
      checkpoints: [commerceWarRoomCheckpoint()],
    });
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceWarRoomView, {
          viewModel,
          isLoading: false,
          error: null,
          onSelectRun: () => undefined,
          onOpenCase: () => undefined,
          onOpenRun: () => undefined,
        }),
      ),
    );

    for (const label of [
      "观察正在进行的调查",
      "只展示已持久化的领域事件",
      "调查履约延迟原因",
      "并行路径",
      "调查泳道",
      "履约路径",
      "已完成 · 2 条证据",
      "卖家对标",
      "正在读取同类卖家对标",
      "评价体验",
      "缺少评价文本，路径已阻塞",
      "等待全部请求路径进入终态",
      "主智能体综合 / 新鲜上下文验证",
      "当前证据构成",
      "支持",
      "矛盾",
      "未知",
      "最新检查点 #7",
      "领域事件流",
      "按运行事件序号排序",
      "检查点已保存",
      "等待下一条持久化事件",
      "检查完整运行记录",
      "打开案例",
    ]) {
      expect(text).toContain(label);
    }
    expect(text).not.toContain("模型调用");
    expect(text).not.toContain("令牌");
    expect(text).not.toContain("继续询问当前案例");
    expect(text).not.toContain("正在思考");
  });
});

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
