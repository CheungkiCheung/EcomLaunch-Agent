import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceCaseQueueView } from "@/components/commerce/case-queue";
import { buildCommerceCaseQueueViewModel } from "@/core/commerce";

describe("CommerceCaseQueueView", () => {
  test("renders a Case-first Chinese work queue without Chat or fake Agent activity", () => {
    const viewModel = buildCommerceCaseQueueViewModel([], {
      filter: "all",
      query: "",
    });
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceCaseQueueView, {
          viewModel,
          filter: "all",
          query: "",
          creating: false,
          createOpen: false,
          createError: null,
          createNotice: null,
          createOptions: null,
          createOptionsLoading: false,
          onFilterChange: () => undefined,
          onQueryChange: () => undefined,
          onOpenCase: () => undefined,
          onOpenCreate: () => undefined,
          onCloseCreate: () => undefined,
          onCreateCase: () => undefined,
        }),
      ),
    );

    for (const label of [
      "案例队列",
      "需要处理的经营问题",
      "创建案例",
      "全部",
      "待调查",
      "等待数据",
      "等待审批",
      "执行中",
      "跟踪中",
      "还没有经营案例",
    ]) {
      expect(text).toContain(label);
    }
    expect(text).not.toContain("Chat");
    expect(text).not.toContain("Agent");
    expect(text).not.toContain("Token");
  });

  test("distinguishes Dataset loading from a real empty create state", () => {
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceCaseQueueView, {
          viewModel: buildCommerceCaseQueueViewModel([], {
            filter: "all",
            query: "",
          }),
          filter: "all",
          query: "",
          creating: false,
          createOpen: true,
          createError: null,
          createNotice: null,
          createOptions: null,
          createOptionsLoading: true,
          onFilterChange: () => undefined,
          onQueryChange: () => undefined,
          onOpenCase: () => undefined,
          onOpenCreate: () => undefined,
          onCloseCreate: () => undefined,
          onCreateCase: () => undefined,
        }),
      ),
    );

    expect(text).toContain("正在读取创建案例所需的数据能力");
    expect(text).not.toContain("还没有可用于创建案例的数据批次");
  });
});

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
