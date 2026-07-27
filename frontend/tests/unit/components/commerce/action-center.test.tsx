import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceActionCenterView } from "@/components/commerce/action-center";

describe("CommerceActionCenterView", () => {
  test("renders evidence policy execution and rollback without runtime telemetry", () => {
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceActionCenterView, {
          viewModel: {
            title: "审查与执行行动",
            subtitle: "行动必须有证据、策略判断和回滚方案，执行后再进入跟踪。",
            filters: [
              { value: "all", label: "全部", count: 1 },
              { value: "needs_action", label: "待处理", count: 1 },
              { value: "in_progress", label: "执行中", count: 0 },
              { value: "monitoring", label: "跟踪中", count: 0 },
              { value: "ended", label: "已结束", count: 0 },
            ],
            items: [
              {
                id: "act_1",
                caseId: "case_1",
                caseTitle: "履约延迟异常",
                title: "创建延迟履约率跟踪",
                statusLabel: "待执行",
                statusGroup: "needs_action",
                riskLabel: "中风险",
                policyLabel: "策略 L2",
                approvalLabel: "无需审批",
                updatedLabel: "10:42",
              },
            ],
            selected: {
              id: "act_1",
              caseId: "case_1",
              caseTitle: "履约延迟异常",
              title: "创建延迟履约率跟踪",
              statusLabel: "待执行",
              statusGroup: "needs_action",
              riskLabel: "中风险",
              policyLabel: "策略 L2",
              approvalLabel: "无需审批",
              updatedLabel: "10:42",
              description:
                "每 24 小时检查一次延迟履约率，并在 7 天后重新评估当前案例。",
              policyDispositionLabel: "允许执行",
              policyDescription: "内部可逆操作，无需人工审批。",
              executionToolLabel: "internal_metric_monitor.create",
              evidenceSummary: "引用 2 条证据和 1 个工作假设",
              hypothesisSummary:
                "行动引用已验证的工作假设，但不能单独证明因果关系。",
              planRows: [
                { label: "行动类型", value: "指标跟踪" },
                { label: "判断条件", value: "小于或等于 4.8%" },
              ],
              rollback: {
                strategy: "停用本次指标跟踪",
                trigger: "发现配置错误或监控对象不一致时",
                verification: "确认跟踪任务已停用且不再产生新检查记录",
              },
              approvalProgressLabel: null,
              artifactLabel: null,
              canExecute: true,
              canRollback: false,
              canApprove: false,
              canReject: false,
              primaryActionLabel: "执行行动",
            },
          },
          filter: "all",
          query: "",
          isLoading: false,
          isSubmitting: false,
          notice: null,
          error: null,
          actorAvailable: true,
          onFilterChange: () => undefined,
          onQueryChange: () => undefined,
          onSelectAction: () => undefined,
          onOpenCase: () => undefined,
          onOpenEvidence: () => undefined,
          onPrimaryAction: () => undefined,
          onReject: () => undefined,
        }),
      ),
    );

    for (const label of [
      "审查与执行行动",
      "创建延迟履约率跟踪",
      "为什么建议这样做",
      "引用 2 条证据和 1 个工作假设",
      "执行计划",
      "小于或等于 4.8%",
      "策略与权限",
      "允许执行",
      "回滚方案",
      "执行行动",
    ]) {
      expect(text).toContain(label);
    }
    expect(text).not.toContain("Token");
    expect(text).not.toContain("Retry");
    expect(text).not.toContain("深度求索");
  });
});

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
