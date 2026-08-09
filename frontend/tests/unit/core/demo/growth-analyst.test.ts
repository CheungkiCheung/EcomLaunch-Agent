import { describe, expect, it } from "vitest";

import {
  createGrowthAnalystDemoFiles,
  GROWTH_ANALYST_DEMO_FILES,
  GROWTH_ANALYST_DEMO_SCENARIOS,
  GROWTH_ANALYST_DEMO_SCENARIO_IDS,
  isGrowthAnalystDemoFile,
} from "@/core/demo/growth-analyst";

async function readFiles(files: File[]) {
  return Object.fromEntries(
    await Promise.all(
      files.map(async (file) => [file.name, await file.text()] as const),
    ),
  );
}

function rows(csv: string) {
  return csv.trim().split("\n").slice(1).map((row) => row.split(","));
}

describe("Growth Analyst demo data", () => {
  it("exposes four interview-ready scenarios", () => {
    expect(GROWTH_ANALYST_DEMO_SCENARIO_IDS).toEqual([
      "experiment",
      "channel",
      "retention",
      "product",
    ]);
    expect(GROWTH_ANALYST_DEMO_FILES).toEqual([
      "customers.csv",
      "assignments.csv",
      "outcomes.csv",
    ]);
    expect(
      GROWTH_ANALYST_DEMO_SCENARIO_IDS.every(
        (scenarioId) =>
          GROWTH_ANALYST_DEMO_SCENARIOS[scenarioId].files.length === 3,
      ),
    ).toBe(true);
  });

  it("builds the deterministic A/B experiment bundle", async () => {
    const files = createGrowthAnalystDemoFiles("experiment");
    const data = await readFiles(files);

    expect(files.map((file) => file.name)).toEqual(GROWTH_ANALYST_DEMO_FILES);
    expect(files.every((file) => file.type === "text/csv")).toBe(true);
    expect(data["customers.csv"]?.trim().split("\n")).toHaveLength(201);
    expect(data["assignments.csv"]).toContain(
      "user-001,control,2026-08-01",
    );
    expect(data["assignments.csv"]).toContain(
      "user-101,variant,2026-08-01",
    );
    expect(data["outcomes.csv"]).toContain("user-010,1,99,2026-08-05");
    expect(data["outcomes.csv"]).toContain("user-120,1,129,2026-08-05");
    expect(data["outcomes.csv"]).toContain("user-121,0,0,");
  });

  it("builds channel data with the advertised ROAS contrast", async () => {
    const data = await readFiles(createGrowthAnalystDemoFiles("channel"));
    const spendByChannel = new Map<string, number>();
    const revenueByChannel = new Map<string, number>();

    for (const [, channel = "", , spend = "0"] of rows(
      data["ad_spend.csv"] ?? "",
    )) {
      spendByChannel.set(
        channel,
        (spendByChannel.get(channel) ?? 0) + Number(spend),
      );
    }
    for (const [, channel = "", , , revenue = "0"] of rows(
      data["orders.csv"] ?? "",
    )) {
      revenueByChannel.set(
        channel,
        (revenueByChannel.get(channel) ?? 0) + Number(revenue),
      );
    }

    expect(rows(data["ad_spend.csv"] ?? "")).toHaveLength(120);
    expect(
      (revenueByChannel.get("xiaohongshu") ?? 0) /
        (spendByChannel.get("xiaohongshu") ?? 1),
    ).toBeCloseTo(3.71, 1);
    expect(
      (revenueByChannel.get("display") ?? 0) /
        (spendByChannel.get("display") ?? 1),
    ).toBeLessThan(1);
  });

  it("builds weekly cohort data with distinct D30 retention", async () => {
    const data = await readFiles(createGrowthAnalystDemoFiles("retention"));
    const userChannel = new Map(
      rows(data["users.csv"] ?? "").map(
        ([userId = "", , , channel = ""]) => [userId, channel] as const,
      ),
    );
    const d30ByChannel = new Map<string, number>();

    for (const [userId = "", , eventName = ""] of rows(
      data["events.csv"] ?? "",
    )) {
      if (eventName !== "purchase") continue;
      const channel = userChannel.get(userId) ?? "";
      d30ByChannel.set(channel, (d30ByChannel.get(channel) ?? 0) + 1);
    }

    expect(rows(data["users.csv"] ?? "")).toHaveLength(240);
    expect(d30ByChannel.get("referral")).toBe(24);
    expect(d30ByChannel.get("organic")).toBe(12);
    expect(d30ByChannel.get("xiaohongshu")).toBe(12);
    expect(d30ByChannel.get("paid_display") ?? 0).toBe(0);
  });

  it("builds product data with volume, margin, and inventory contrasts", async () => {
    const data = await readFiles(createGrowthAnalystDemoFiles("product"));
    const itemCounts = new Map<string, number>();

    for (const [, productId = ""] of rows(data["order_items.csv"] ?? "")) {
      itemCounts.set(productId, (itemCounts.get(productId) ?? 0) + 1);
    }

    expect(rows(data["products.csv"] ?? "")).toHaveLength(8);
    expect(rows(data["orders.csv"] ?? "")).toHaveLength(240);
    expect(itemCounts.get("sku-001")).toBe(72);
    expect(itemCounts.get("sku-008")).toBe(3);
    expect(data["products.csv"]).toContain(
      "sku-008,Legacy Cup,drinkware,109,66,180",
    );
  });

  it("marks generated demo files without treating manual files as demos", () => {
    const demoFiles = createGrowthAnalystDemoFiles("channel");
    const manualFile = new File(["value\n1\n"], "manual.csv", {
      type: "text/csv",
    });

    expect(demoFiles.every((file) => isGrowthAnalystDemoFile(file))).toBe(true);
    expect(isGrowthAnalystDemoFile(manualFile)).toBe(false);
    expect(isGrowthAnalystDemoFile(undefined)).toBe(false);
  });
});
