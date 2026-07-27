import { describe, expect, test } from "vitest";

import { buildCommerceSkillsEvalsViewModel } from "@/core/commerce";

import {
  commerceSkillCandidate,
  commerceSkillCandidateEvidence,
} from "./skills-evals-fixture";

describe("buildCommerceSkillsEvalsViewModel", () => {
  test("projects gates frozen experiment shadow and human review honestly", () => {
    const candidate = commerceSkillCandidate();
    const view = buildCommerceSkillsEvalsViewModel({
      candidates: [candidate],
      selectedCandidateId: candidate.id,
      selectedEvidence: commerceSkillCandidateEvidence(),
    });

    expect(view.summary).toEqual([
      expect.objectContaining({ label: "当前生效", valueLabel: "未建立指针" }),
      expect.objectContaining({ label: "待人工审查", valueLabel: "1" }),
      expect.objectContaining({ label: "冻结评测", valueLabel: "8 / 8" }),
      expect.objectContaining({ label: "影子运行", valueLabel: "2 / 2" }),
    ]);
    expect(view.selected).toMatchObject({
      title: "诊断综合 1.3.0",
      statusLabel: "待人工审查",
      purpose: "修复模型自造行动阈值的问题，只允许引用服务端已配置策略。",
      hashLabel: "f46d…b228",
      primaryActionLabel: "人工批准并激活",
      canPromote: true,
      canRollback: false,
      experiment: {
        decisionLabel: "建议晋级",
        recommendationLabel: "质量提升，令牌 -12.1%，延迟 -26.0%",
        requestCountLabel: "32 个唯一请求编号",
      },
      shadow: {
        summaryLabel: "2 条真实运行",
        telemetryBoundaryLabel: "请求遥测未由当前接口开放",
      },
    });
    expect(view.selected?.stages.map((item) => item.title)).toEqual([
      "候选提出",
      "安全扫描",
      "离线评测",
      "留出集",
      "影子运行",
      "人工审查",
      "生效",
    ]);
    expect(view.selected?.stages.map((item) => item.status)).toEqual([
      "completed",
      "completed",
      "completed",
      "completed",
      "completed",
      "current",
      "not_started",
    ]);
    expect(view.selected?.experiment?.rows).toEqual([
      { label: "通过", candidateLabel: "8 / 8", controlLabel: "6 / 8" },
      { label: "硬门禁失败", candidateLabel: "0", controlLabel: "2" },
      { label: "平均令牌", candidateLabel: "2,052", controlLabel: "2,335" },
      { label: "平均延迟", candidateLabel: "4.2 秒", controlLabel: "5.7 秒" },
    ]);
    expect(view.selected?.experiment?.caseLabels).toEqual([
      "履约",
      "评价",
      "能力边界",
      "卖家对标",
    ]);
    expect(JSON.stringify(view)).not.toContain("4 个唯一请求编号");
    expect(JSON.stringify(view)).not.toContain("自动生效");
  });
});
