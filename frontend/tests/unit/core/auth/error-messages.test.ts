import { describe, expect, it } from "vitest";

import {
  getLocalizedAuthErrorMessage,
  type LocalizedAuthErrorMessages,
} from "@/core/auth/error-messages";

const messages: LocalizedAuthErrorMessages = {
  invalid_credentials: "邮箱或密码不正确",
  token_expired: "登录状态已过期",
  token_invalid: "登录状态无效",
  user_not_found: "未找到该账号",
  email_already_exists: "该邮箱已被注册",
  provider_not_found: "当前登录方式不可用",
  not_authenticated: "请先登录",
  system_already_initialized: "系统已经完成初始化",
  fallback: "认证失败",
};

describe("getLocalizedAuthErrorMessage", () => {
  it("returns the localized message for the backend error code", () => {
    expect(
      getLocalizedAuthErrorMessage(
        { code: "invalid_credentials", message: "Incorrect password" },
        messages,
      ),
    ).toBe("邮箱或密码不正确");
  });
});
