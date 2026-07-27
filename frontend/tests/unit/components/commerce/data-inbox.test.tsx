import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { CommerceDataInboxView } from "@/components/commerce/data-inbox";
import { buildCommerceDataInboxViewModel } from "@/core/commerce";

const WORKSPACE_ID = "wsp_0123456789abcdef0123456789abcdef";

describe("CommerceDataInboxView", () => {
  test("renders the Chinese empty state without a chat composer or fake activity", () => {
    const viewModel = buildCommerceDataInboxViewModel({
      workspaceId: WORKSPACE_ID,
      datasets: [],
      selectedDataset: null,
    });
    const text = visibleText(
      renderToStaticMarkup(
        createElement(CommerceDataInboxView, {
          viewModel,
          isUploading: false,
          isConfirming: false,
          error: null,
          notice: null,
          actorConfigured: false,
          onChooseFiles: () => undefined,
          onDropFiles: () => undefined,
          onRefresh: () => undefined,
          onSelectDataset: () => undefined,
          onConfirm: () => undefined,
          onDefer: () => undefined,
          onContinue: () => undefined,
        }),
      ),
    );

    for (const label of [
      "接入经营数据",
      "添加数据",
      "拖入文件或文件夹",
      "选择文件",
      "系统会检查",
      "文件完整性",
      "字段语义",
      "最近的数据批次",
      "还没有导入记录",
      "继续检查数据能力",
    ]) {
      expect(text).toContain(label);
    }
    expect(text).not.toContain("正在运行");
    expect(text).not.toContain("聊天");
    expect(text).not.toContain("Agent");
  });
});

function visibleText(markup: string): string {
  return markup
    .replace(/<[^>]+>/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}
