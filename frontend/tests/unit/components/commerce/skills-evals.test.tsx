import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceSkillsEvalsView } from "@/components/commerce/skills-evals";
import { buildCommerceSkillsEvalsViewModel } from "@/core/commerce";

import {
  commerceSkillCandidate,
  commerceSkillCandidateEvidence,
} from "../../core/commerce/skills-evals-fixture";

describe("CommerceSkillsEvalsView", () => {
  test("renders immutable experiment shadow and human governance boundaries", () => {
    const candidate = commerceSkillCandidate();
    const viewModel = buildCommerceSkillsEvalsViewModel({
      candidates: [candidate],
      selectedCandidateId: candidate.id,
      selectedEvidence: commerceSkillCandidateEvidence(),
    });
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceSkillsEvalsView, {
          viewModel,
          filter: "all",
          query: "",
          isLoading: false,
          isSubmitting: false,
          actorAvailable: true,
          notice: null,
          error: null,
          rollbackReason: "",
          showExperimentEvidence: true,
          onFilterChange: () => undefined,
          onQueryChange: () => undefined,
          onSelectCandidate: () => undefined,
          onRollbackReasonChange: () => undefined,
          onPrimaryAction: () => undefined,
          onToggleExperimentEvidence: () => undefined,
        }),
      ),
    );

    for (const label of [
      "治理技能演进",
      "候选技能不会直接生效",
      "未建立指针",
      "诊断综合 1.3.0",
      "待人工审查",
      "修复模型自造行动阈值的问题",
      "安全扫描",
      "留出集",
      "人工审查",
      "冻结实验对比",
      "8 / 8",
      "6 / 8",
      "质量提升，令牌 -12.1%，延迟 -26.0%",
      "32 个唯一请求编号",
      "2 条真实运行",
      "请求遥测未由当前接口开放",
      "运行中智能体不能修改生效技能",
      "人工批准并激活",
    ]) {
      expect(text).toContain(label);
    }
    expect(text).not.toContain("4 个唯一请求编号");
    expect(text).not.toContain("继续询问当前案例");
    expect(text).not.toContain("自动生效");
  });
});

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
