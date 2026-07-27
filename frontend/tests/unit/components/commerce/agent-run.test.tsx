import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceAgentRunView } from "@/components/commerce/agent-run";

describe("CommerceAgentRunView", () => {
  test("renders persisted run graph, fan-out, telemetry and checkpoint details", () => {
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceAgentRunView, {
          viewModel: {
            title: "检查一次智能体运行",
            subtitle:
              "所有状态来自 Run、Checkpoint 和 Domain Event，不从对话或动画推断。",
            filters: [
              { value: "all", label: "全部", count: 1 },
              { value: "running", label: "进行中", count: 0 },
              { value: "waiting", label: "等待中", count: 0 },
              { value: "completed", label: "已完成", count: 1 },
              { value: "failed", label: "失败", count: 0 },
            ],
            items: [
              {
                id: "run_1",
                caseId: "case_1",
                caseTitle: "履约延迟异常",
                title: "调查履约延迟原因",
                statusLabel: "已完成",
                statusGroup: "completed",
                typeLabel: "案例调查",
                timeLabel: "10:34",
                pathCountLabel: "3 条路径",
                stopReasonLabel: "目标已满足",
              },
            ],
            selected: {
              id: "run_1",
              caseId: "case_1",
              caseTitle: "履约延迟异常",
              title: "调查履约延迟原因",
              statusLabel: "已完成",
              statusGroup: "completed",
              typeLabel: "案例调查",
              timeLabel: "10:34",
              pathCountLabel: "3 条路径",
              stopReasonLabel: "目标已满足",
              shortId: "run_…abcdef",
              goal: "解释履约延迟异常并形成可追溯结论",
              durationLabel: "12.6 秒",
              periodLabel: "10:33—10:34",
              stages: [
                {
                  key: "goal",
                  title: "目标",
                  description: "解释履约延迟异常并形成可追溯结论",
                  status: "completed",
                  statusLabel: "已完成",
                  kind: "step",
                  paths: [],
                  derivationLabel: null,
                },
                {
                  key: "fanout",
                  title: "并行路径",
                  description: "3 条 requested Path 共享同一调查阶段",
                  status: "completed",
                  statusLabel: "已完成",
                  kind: "fanout",
                  paths: [
                    {
                      pathType: "fulfillment",
                      label: "履约路径",
                      status: "completed",
                      statusLabel: "已完成",
                      evidenceCountLabel: "2 条证据",
                    },
                    {
                      pathType: "seller_peer",
                      label: "卖家对标",
                      status: "completed",
                      statusLabel: "已完成",
                      evidenceCountLabel: "1 条证据",
                    },
                    {
                      pathType: "review_experience",
                      label: "评价体验",
                      status: "completed",
                      statusLabel: "已完成",
                      evidenceCountLabel: "1 条证据",
                    },
                  ],
                  derivationLabel: null,
                },
                {
                  key: "barrier",
                  title: "证据屏障",
                  description: "4 条证据已持久化，允许综合",
                  status: "completed",
                  statusLabel: "已完成",
                  kind: "step",
                  paths: [],
                  derivationLabel: "由全部路径终态与主智能体启动事件确认",
                },
                {
                  key: "verification",
                  title: "新鲜上下文验证",
                  description: "独立验证通过",
                  status: "completed",
                  statusLabel: "已完成",
                  kind: "step",
                  paths: [],
                  derivationLabel: null,
                },
              ],
              telemetry: {
                modelIdentityLabel: "deepseek-v4-flash",
                requestCountLabel: "5 个唯一 ID",
                tokenLabel: "18,420",
                latencyLabel: "12.6 秒",
                retryLabel: "0",
                stopReasonLabel: "stop",
              },
              budget: [
                { label: "循环", valueLabel: "1 / 8", ratio: 0.125 },
                { label: "工具", valueLabel: "6 / 20", ratio: 0.3 },
                { label: "路径", valueLabel: "3 / 3", ratio: 1 },
                { label: "令牌", valueLabel: "18,420 / 32,000", ratio: 0.575 },
              ],
              checkpoint: {
                sequenceLabel: "7",
                iterationLabel: "1",
                evidenceLabel: "4",
                hypothesisLabel: "1",
                contextLabel: "已记录",
              },
              selectedStageTitle: "新鲜上下文验证",
              selectedStageDescription:
                "验证器不继承主智能体的完整推理历史，只读取最小可审计上下文。",
              eventCountLabel: "12 条事件",
              checkpointCountLabel: "1 个检查点",
              auditBoundary:
                "提供方请求编号、实际模型、令牌用量、延迟和重试均来自真实领域事件；无事件时显示未观察。",
              events: [
                {
                  id: "evt_1",
                  sequenceLabel: "12",
                  title: "独立验证已完成",
                  timeLabel: "10:33",
                },
              ],
              checkpoints: [
                {
                  id: "chk_1",
                  sequenceLabel: "7",
                  iterationLabel: "1",
                  evidenceLabel: "4",
                  hypothesisLabel: "1",
                  createdLabel: "7月20日 10:33",
                },
              ],
              wasReordered: false,
            },
          },
          filter: "all",
          query: "",
          isLoading: false,
          error: null,
          onFilterChange: () => undefined,
          onQueryChange: () => undefined,
          onSelectRun: () => undefined,
          onOpenCase: () => undefined,
          onShowEvents: () => undefined,
        }),
      ),
    );

    for (const label of [
      "检查一次智能体运行",
      "调查履约延迟原因",
      "并行路径",
      "履约路径",
      "卖家对标",
      "评价体验",
      "由全部路径终态与主智能体启动事件确认",
      "deepseek-v4-flash",
      "18,420",
      "5 个唯一 ID",
      "新鲜上下文验证",
      "最新检查点",
      "上下文 SHA-256",
      "查看事件流",
    ]) {
      expect(text).toContain(label);
    }
    expect(text).not.toContain("继续询问当前案例");
    expect(text).not.toContain("正在思考");
    expect(text).not.toContain("推理过程");
  });
});

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
