import type { Message } from "@langchain/langgraph-sdk";
import { describe, expect, it } from "vitest";

import { deriveStreamingStatus } from "@/components/workspace/messages/streaming-status";

function ai(
  toolCalls: Array<Record<string, unknown>> = [],
  extra: Record<string, unknown> = {},
): Message {
  return {
    id: `ai-${Math.random()}`,
    type: "ai",
    content: "",
    tool_calls: toolCalls,
    additional_kwargs: extra,
  } as Message;
}

function tool(id: string, content: string, name?: string): Message {
  return {
    id: `tool-${id}`,
    type: "tool",
    name,
    tool_call_id: id,
    content,
  } as Message;
}

describe("deriveStreamingStatus", () => {
  it("shows a runtime preparation status before the first event", () => {
    expect(deriveStreamingStatus([])).toEqual({ key: "preparing" });
  });

  it("recognizes a Flash public search", () => {
    expect(
      deriveStreamingStatus([
        ai([{ id: "search-1", name: "web_search", args: { query: "mugs" } }]),
      ]),
    ).toMatchObject({ key: "searching", toolName: "web_search" });
  });

  it("recognizes each Launch specialist", () => {
    for (const [subagentType, key] of [
      ["market-voc-researcher", "researcher"],
      ["offer-architect", "offer"],
      ["asset-studio", "assets"],
    ] as const) {
      expect(
        deriveStreamingStatus([
          ai([
            {
              id: `task-${key}`,
              name: "task",
              args: { subagent_type: subagentType },
            },
          ]),
        ]),
      ).toMatchObject({ key, subagentType });
    }
  });

  it("shows preflight repair after an invalid presentation result", () => {
    expect(
      deriveStreamingStatus([
        ai([{ id: "present-1", name: "present_files", args: {} }]),
        tool("present-1", "Error: Launch Pack preflight blocked delivery"),
      ]),
    ).toMatchObject({ key: "repairing", toolName: "present_files" });
  });

  it("shows data joining and experiment analysis", () => {
    expect(
      deriveStreamingStatus([
        ai([{ id: "join-1", name: "join_files", args: {} }]),
      ]),
    ).toMatchObject({ key: "joining" });
    expect(
      deriveStreamingStatus([
        ai([{ id: "ab-1", name: "analyze_ab_test", args: {} }]),
      ]),
    ).toMatchObject({ key: "experiment" });
  });

  it("returns finalizing after successful file presentation", () => {
    expect(
      deriveStreamingStatus([
        ai([{ id: "present-2", name: "present_files", args: {} }]),
        tool("present-2", "Successfully presented files"),
      ]),
    ).toMatchObject({ key: "finalizing" });
  });

  it("surfaces a failed run instead of guessing the last phase", () => {
    expect(deriveStreamingStatus([], { hasError: true })).toEqual({
      key: "failed",
    });
  });
});
