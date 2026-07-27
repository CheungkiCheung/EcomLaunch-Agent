import { describe, expect, it } from "vitest";

import { zhCN } from "@/core/i18n/locales/zh-CN";

describe("Chinese DeerFlow workspace copy", () => {
  it("localizes the chat artifact panel and completion states", () => {
    expect(zhCN.common).toMatchObject({
      noArtifactSelected: "当前没有选中文件",
      selectArtifactDescription: "选择一个文件后，可在这里查看详情",
      showArtifacts: "查看本次对话的文件",
      file: "文件",
      selectFile: "选择文件",
      installSkillFailed: "安装技能失败",
      conversationFinished: "本轮对话已完成",
    });
    expect(zhCN.inputBox.submit).toBe("发送");
    expect(zhCN.pages.appName).toBe("电商经营诊断");
    expect(zhCN.tokenUsage).toMatchObject({
      title: "模型用量",
      label: "用量",
    });
    expect(JSON.stringify(zhCN.tokenUsage)).not.toContain("Token");
  });
});
