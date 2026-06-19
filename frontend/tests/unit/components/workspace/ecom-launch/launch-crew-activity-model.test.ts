import { describe, expect, it } from "vitest";

import {
  buildLaunchCrewActivityModel,
  type LaunchCrewTask,
} from "@/components/workspace/ecom-launch/launch-crew-activity-model";

function task(overrides: Partial<LaunchCrewTask>): LaunchCrewTask {
  return {
    id: overrides.id ?? "task-1",
    role: overrides.role ?? "market-voc-researcher",
    status: overrides.status ?? "in_progress",
    description: overrides.description ?? "研究公开市场信号",
    prompt: overrides.prompt ?? "",
    ...overrides,
  };
}

describe("launch crew activity model", () => {
  it("returns a quiet cockpit with pending evidence and artifact states", () => {
    const model = buildLaunchCrewActivityModel({
      tasks: [],
      artifacts: [],
      todos: [],
      isStreaming: false,
    });

    expect(model.activeAgentCount).toBe(0);
    expect(model.selectedAgent.id).toBe("launch-director");
    expect(model.liveComms).toEqual([]);
    expect(model.evidenceBadges.map((badge) => badge.status)).toEqual([
      "pending",
      "pending",
      "info",
      "pending",
    ]);
    expect(model.artifactStatuses.every((artifact) => artifact.status === "pending")).toBe(
      true,
    );
  });

  it("marks active tasks, caps live comms, and selects the working agent", () => {
    const model = buildLaunchCrewActivityModel({
      tasks: [
        task({
          id: "market",
          role: "market-voc-researcher",
          currentAction: "正在搜索公开信号",
        }),
        task({
          id: "offer",
          role: "offer-architect",
          description: "定位首个 offer wedge",
        }),
        task({
          id: "asset",
          role: "asset-studio",
          currentAction: "正在整理内容资产",
        }),
        task({
          id: "evidence",
          role: "evidence-checker",
          currentAction: "正在检查 claim readiness",
        }),
        task({
          id: "growth",
          role: "growth-analyst",
          currentAction: "正在设计 7 天实验",
        }),
        task({
          id: "market-2",
          role: "market-voc-researcher",
          currentAction: "正在读取用户评论",
        }),
      ],
      artifacts: [],
      todos: [],
      isStreaming: true,
    });

    expect(model.selectedAgent.id).toBe("market-voc-researcher");
    expect(model.selectedAgent.status).toBe("working");
    expect(model.liveComms).toHaveLength(5);
    expect(model.liveComms.at(0)?.role).toBe("offer-architect");
    expect(model.liveComms.at(-1)?.text).toBe("正在读取用户评论");
  });

  it("prioritizes failed agents when the current selection is stale", () => {
    const model = buildLaunchCrewActivityModel({
      selectedAgentId: "asset-studio",
      tasks: [
        task({
          id: "evidence",
          role: "evidence-checker",
          status: "failed",
          error: "Evidence ledger JSON parse failed",
        }),
        task({
          id: "market",
          role: "market-voc-researcher",
          status: "completed",
          result: "公开信号已回传",
        }),
      ],
      artifacts: [],
      todos: [],
      isStreaming: false,
    });

    expect(model.selectedAgent.id).toBe("evidence-checker");
    expect(model.selectedAgent.status).toBe("error");
    expect(model.selectedAgent.lastLine).toBe("Evidence ledger JSON parse failed");
  });

  it("preserves a valid user-selected agent", () => {
    const model = buildLaunchCrewActivityModel({
      selectedAgentId: "asset-studio",
      tasks: [
        task({
          id: "market",
          role: "market-voc-researcher",
        }),
        task({
          id: "asset",
          role: "asset-studio",
          status: "completed",
          result: "Listing pack 已回传",
        }),
      ],
      artifacts: ["listing-pack.md"],
      todos: [],
      isStreaming: false,
    });

    expect(model.selectedAgent.id).toBe("asset-studio");
    expect(model.selectedAgent.status).toBe("done");
    expect(model.selectedAgent.artifacts.map((artifact) => artifact.name)).toEqual([
      "listing-pack.md",
    ]);
  });

  it("maps real artifacts and evidence badges without fake ready states", () => {
    const model = buildLaunchCrewActivityModel({
      tasks: [],
      artifacts: [
        "competitor-table.csv",
        "evidence-ledger.json",
        "unknown-extra.md",
      ],
      todos: [],
      isStreaming: false,
    });

    expect(
      model.artifactStatuses
        .filter((artifact) => artifact.status === "ready")
        .map((artifact) => artifact.name),
    ).toEqual([
      "competitor-table.csv",
      "evidence-ledger.json",
      "unknown-extra.md",
    ]);
    expect(model.evidenceBadges.find((badge) => badge.id === "evidence-ledger")?.status).toBe(
      "ready",
    );
    expect(model.evidenceBadges.find((badge) => badge.id === "claims-audit")?.status).toBe(
      "ready",
    );
  });

  it("builds non-linear active missions from todos, tasks, and artifacts", () => {
    const model = buildLaunchCrewActivityModel({
      tasks: [
        task({
          id: "offer",
          role: "offer-architect",
          description: "设计首个 offer wedge",
        }),
      ],
      artifacts: ["content-scorecard.md"],
      todos: [
        { content: "校准短视频脚本", status: "in_progress" },
        { content: "整理证据账本", status: "pending" },
      ],
      isStreaming: true,
    });

    expect(model.activeMissions.map((mission) => mission.label)).toEqual([
      "校准短视频脚本",
      "设计首个 offer wedge",
      "内容评分卡",
    ]);
    expect(model.activeMissions.map((mission) => mission.status)).toEqual([
      "active",
      "active",
      "done",
    ]);
  });
});
