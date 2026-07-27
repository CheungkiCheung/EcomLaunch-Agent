import { describe, expect, it } from "vitest";

import { commerceMetricObservationSchema } from "@/core/commerce/types";

describe("Commerce deterministic metric contract", () => {
  it("accepts source-local metric windows without inventing a timezone", () => {
    const parsed = commerceMetricObservationSchema.safeParse({
      id: "mobs_0123456789abcdef0123456789abcdef",
      metric_name: "late_delivery_rate",
      semantic_status: "observed",
      value: "0.364",
      unit: "ratio",
      formula_version: "late_delivery_rate@1.0.0",
      window_start: "2018-01-31T00:00:00",
      window_end: "2018-04-01T00:00:00",
      sample_size: 132,
      numerator: "48",
      denominator: "132",
      source_fact_count: 132,
      unknown_reason: null,
    });

    expect(parsed.success ? [] : parsed.error.issues).toEqual([]);
  });
});
