import { describe, expect, test } from "vitest";

import {
  COMMERCE_AGENT_NAME,
  commerceAgentChatHref,
  commerceCollaborationHref,
  commerceWorkspaceBrand,
  isCommerceAgentName,
  selectCommerceRunId,
  shouldShowLegacyEcomLaunchNavigation,
} from "@/core/commerce/agent-ui";

describe("Commerce Agent DeerFlow route contract", () => {
  test("uses a Chinese product brand while retaining the DeerFlow shell", () => {
    expect(commerceWorkspaceBrand({ commerceCaseAgentEnabled: true })).toEqual({
      expanded: "经营诊断",
      collapsed: "诊",
    });
    expect(commerceWorkspaceBrand({ commerceCaseAgentEnabled: false })).toEqual(
      { expanded: "DeerFlow", collapsed: "DF" },
    );
  });

  test("hides the legacy Ecom Launch navigation when Commerce Agent is enabled", () => {
    expect(
      shouldShowLegacyEcomLaunchNavigation({
        commerceCaseAgentEnabled: true,
      }),
    ).toBe(false);
    expect(
      shouldShowLegacyEcomLaunchNavigation({
        commerceCaseAgentEnabled: false,
      }),
    ).toBe(true);
  });

  test("recognizes only the built-in Commerce Agent name", () => {
    expect(COMMERCE_AGENT_NAME).toBe("commerce-agent");
    expect(isCommerceAgentName("commerce-agent")).toBe(true);
    expect(isCommerceAgentName("commerce_agent")).toBe(false);
    expect(isCommerceAgentName("ecom-launch")).toBe(false);
    expect(isCommerceAgentName(null)).toBe(false);
  });

  test("keeps the default entry in DeerFlow Agent Chat", () => {
    expect(commerceAgentChatHref()).toBe(
      "/workspace/agents/commerce-agent/chats/new",
    );
    expect(commerceAgentChatHref("thread/with spaces")).toBe(
      "/workspace/agents/commerce-agent/chats/thread%2Fwith%20spaces",
    );
  });

  test("preserves thread, run and mock context for the optional collaboration space", () => {
    expect(
      commerceCollaborationHref({
        threadId: "thread-1",
        runId: "run-2",
        isMock: true,
      }),
    ).toBe(
      "/workspace/agents/commerce-agent/war-room?threadId=thread-1&runId=run-2&mock=true",
    );
    expect(commerceCollaborationHref({ threadId: "thread-1" })).toBe(
      "/workspace/agents/commerce-agent/war-room?threadId=thread-1",
    );
  });

  test("prefers the live stream run and otherwise restores the latest Commerce run", () => {
    const runs = [
      {
        run_id: "ordinary-newer",
        assistant_id: "lead_agent",
        created_at: "2026-07-26T12:00:00Z",
        updated_at: "2026-07-26T12:01:00Z",
      },
      {
        run_id: "commerce-older",
        assistant_id: "commerce-agent",
        created_at: "2026-07-26T10:00:00Z",
        updated_at: "2026-07-26T10:01:00Z",
      },
      {
        run_id: "commerce-latest",
        assistant_id: "commerce-agent",
        created_at: "2026-07-26T11:00:00Z",
        updated_at: "2026-07-26T11:02:00Z",
      },
    ];

    expect(selectCommerceRunId({ capturedRunId: "live-run", runs })).toBe(
      "live-run",
    );
    expect(selectCommerceRunId({ capturedRunId: null, runs })).toBe(
      "commerce-latest",
    );
    expect(
      selectCommerceRunId({
        capturedRunId: null,
        runs: runs.filter((run) => run.assistant_id !== "commerce-agent"),
      }),
    ).toBeNull();
  });
});
