import { describe, expect, it } from "vitest";

import { DEFAULT_LOCALE, resolvePreferredLocale } from "@/core/i18n/locale";

describe("Chinese-first product locale", () => {
  it("uses Chinese on first visit while preserving an explicit user choice", () => {
    expect(DEFAULT_LOCALE).toBe("zh-CN");
    expect(resolvePreferredLocale(null)).toBe("zh-CN");
    expect(resolvePreferredLocale(undefined)).toBe("zh-CN");
    expect(resolvePreferredLocale("en-US")).toBe("en-US");
    expect(resolvePreferredLocale("zh")).toBe("zh-CN");
  });
});
