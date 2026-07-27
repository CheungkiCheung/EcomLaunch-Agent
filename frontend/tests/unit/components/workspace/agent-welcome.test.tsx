import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { AgentWelcome } from "@/components/workspace/agent-welcome";
import { I18nProvider } from "@/core/i18n/context";

describe("AgentWelcome", () => {
  test("renders the built-in Commerce Agent as a Chinese Chat-first product", () => {
    const text = visibleText(
      renderToStaticMarkup(
        <I18nProvider initialLocale="zh-CN">
          <AgentWelcome agent={null} agentName="commerce-agent" />
        </I18nProvider>,
      ),
    );

    expect(text).toContain("电商经营诊断");
    expect(text).toContain("上传真实经营数据");
    expect(text).toContain("确定性指标");
    expect(text).toContain("动态子任务");
    expect(text).toContain("证据与反证");
    expect(text).toContain("独立核验");
    expect(text).not.toContain("Launch Crew");
    expect(text).not.toContain("War Room");
  });
});

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
