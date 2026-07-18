import { describe, expect, test } from "vitest";

import { parseBooleanFeatureFlag } from "@/core/config/feature-flags";

describe("parseBooleanFeatureFlag", () => {
  test("keeps an unset flag disabled", () => {
    expect(parseBooleanFeatureFlag(undefined)).toBe(false);
  });

  test("requires an explicit true value", () => {
    for (const value of ["false", "0", "yes", "on", "unexpected", ""]) {
      expect(parseBooleanFeatureFlag(value)).toBe(false);
    }
  });

  test("accepts true without depending on letter case or whitespace", () => {
    for (const value of ["true", "TRUE", " True "]) {
      expect(parseBooleanFeatureFlag(value)).toBe(true);
    }
  });
});
