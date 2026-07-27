import { afterEach, describe, expect, test, vi } from "vitest";

import {
  loadCommerceRunTaskActivity,
  loadCommerceRunTaskActivityPage,
  loadCommerceSubagentTaskEvents,
  mergeCommerceRunTaskActivityPages,
  shouldContinueCommerceTaskPolling,
  type CommerceApiError,
  type CommerceSubagentTask,
  type CommerceSubagentTaskEventRecord,
} from "@/core/commerce";

const RUN_ID = "run_0123456789abcdef0123456789abcdef";
const TASK_ID = "task_0123456789abcdef0123456789abcdef";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Durable Subagent Task API", () => {
  test("loads one run's tasks and append-only events from the authenticated gateway", async () => {
    const requests: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        requests.push(url);
        if (url.endsWith(`/api/runs/${RUN_ID}/subagent-tasks`)) {
          return jsonResponse({ data: [taskResponse()] });
        }
        if (
          url.endsWith(
            `/api/subagent-tasks/${TASK_ID}/events?after_seq=0&limit=200`,
          )
        ) {
          return jsonResponse({
            data: [taskEventResponse()],
            next_after_seq: 1,
            has_more: false,
          });
        }
        return new Response("not found", { status: 404 });
      }),
    );

    const result = await loadCommerceRunTaskActivity({ runId: RUN_ID });

    expect(result).toHaveLength(1);
    expect(result[0]?.task.context_packet.available_tools).toEqual([
      "commerce_compare_windows",
      "commerce_evidence_query",
    ]);
    expect(result[0]?.events[0]?.event_type).toBe("task.created");
    expect(requests).toEqual([
      `/api/runs/${RUN_ID}/subagent-tasks`,
      `/api/subagent-tasks/${TASK_ID}/events?after_seq=0&limit=200`,
    ]);
  });

  test("supports an explicit event cursor without guessing missing pages", async () => {
    let requestedUrl = "";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        requestedUrl =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        return jsonResponse({
          data: [],
          next_after_seq: 7,
          has_more: true,
        });
      }),
    );

    const result = await loadCommerceSubagentTaskEvents({
      taskId: TASK_ID,
      afterSeq: 7,
      limit: 50,
    });

    expect(requestedUrl).toBe(
      `/api/subagent-tasks/${TASK_ID}/events?after_seq=7&limit=50`,
    );
    expect(result).toEqual({ data: [], next_after_seq: 7, has_more: true });
  });

  test("rejects malformed task responses instead of inventing visual state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ data: [{ task_id: TASK_ID }] })),
    );

    await expect(
      loadCommerceRunTaskActivity({ runId: RUN_ID }),
    ).rejects.toEqual(
      expect.objectContaining<Partial<CommerceApiError>>({
        code: "invalid_response",
      }),
    );
  });

  test("merges append-only event pages with monotonic cursors without replaying duplicates", () => {
    const task = taskResponse();
    const firstEvent = taskEventResponse();
    const previous = [
      {
        task,
        events: [firstEvent],
        nextAfterSeq: 1,
        hasMore: false,
      },
    ];
    const secondEvent = {
      ...firstEvent,
      seq: 2,
      event_type: "task.running",
      idempotency_key: "task.running",
      created_at: "2026-07-26T00:00:01+00:00",
    };

    const merged = mergeCommerceRunTaskActivityPages({
      previous,
      tasks: [{ ...task, status: "running", event_seq: 2 }],
      pages: new Map([
        [
          TASK_ID,
          {
            data: [firstEvent, secondEvent],
            next_after_seq: 2,
            has_more: true,
          },
        ],
      ]),
    });

    expect(merged).toEqual([
      expect.objectContaining({
        task: expect.objectContaining({ status: "running", event_seq: 2 }),
        events: [firstEvent, secondEvent],
        nextAfterSeq: 2,
        hasMore: true,
      }),
    ]);
  });

  test("requests the next page from each task's persisted cursor", async () => {
    const requests: string[] = [];
    const task = taskResponse();
    const previousEvent = taskEventResponse();
    const nextEvent = {
      ...previousEvent,
      seq: 2,
      event_type: "task.tool_result",
      payload: { tool_name: "commerce_compare_windows" },
      idempotency_key: "task.tool_result",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url =
          typeof input === "string"
            ? input
            : input instanceof URL
              ? input.toString()
              : input.url;
        requests.push(url);
        if (url.endsWith(`/api/runs/${RUN_ID}/subagent-tasks`)) {
          return jsonResponse({ data: [{ ...task, event_seq: 2 }] });
        }
        return jsonResponse({
          data: [nextEvent],
          next_after_seq: 2,
          has_more: false,
        });
      }),
    );

    const result = await loadCommerceRunTaskActivityPage({
      runId: RUN_ID,
      previous: [
        {
          task,
          events: [previousEvent],
          nextAfterSeq: 1,
          hasMore: true,
        },
      ],
    });

    expect(requests).toEqual([
      `/api/runs/${RUN_ID}/subagent-tasks`,
      `/api/subagent-tasks/${TASK_ID}/events?after_seq=1&limit=200`,
    ]);
    expect(result[0]?.events.map((event) => event.seq)).toEqual([1, 2]);
    expect(result[0]?.nextAfterSeq).toBe(2);
  });

  test("keeps polling between task waves while the parent Run is active", () => {
    expect(
      shouldContinueCommerceTaskPolling({
        runStatus: "running",
        activities: [terminalActivity()],
      }),
    ).toBe(true);
  });

  test("stops polling only after the Run and every task/event page are terminal", () => {
    expect(
      shouldContinueCommerceTaskPolling({
        runStatus: "success",
        activities: [terminalActivity()],
      }),
    ).toBe(false);
    expect(
      shouldContinueCommerceTaskPolling({
        runStatus: "error",
        activities: [],
      }),
    ).toBe(false);
  });

  test("drains non-terminal tasks and remaining event pages after the Run ends", () => {
    expect(
      shouldContinueCommerceTaskPolling({
        runStatus: "success",
        activities: [
          {
            ...terminalActivity(),
            task: { ...taskResponse(), status: "waiting" },
          },
        ],
      }),
    ).toBe(true);
    expect(
      shouldContinueCommerceTaskPolling({
        runStatus: "success",
        activities: [{ ...terminalActivity(), hasMore: true }],
      }),
    ).toBe(true);
    expect(
      shouldContinueCommerceTaskPolling({
        runStatus: null,
        activities: [terminalActivity()],
      }),
    ).toBe(true);
  });
});

function terminalActivity() {
  return {
    task: {
      ...taskResponse(),
      status: "completed" as const,
      completed_at: "2026-07-26T00:00:02+00:00",
    },
    events: [taskEventResponse()],
    nextAfterSeq: 1,
    hasMore: false,
  };
}

function taskResponse(): CommerceSubagentTask {
  return {
    task_id: TASK_ID,
    thread_id: "thread-1",
    run_id: RUN_ID,
    user_id: "user-1",
    parent_task_id: null,
    subagent_type: "analyst",
    description: "分析履约变化",
    context_packet: {
      schema_version: "deerflow.subagent-context@1.0.0",
      goal: "分析履约变化",
      source_refs: [],
      evidence_refs: [],
      constraints: {},
      available_skills: ["fulfillment-investigation"],
      available_tools: ["commerce_compare_windows", "commerce_evidence_query"],
      budget: { max_turns: 12, max_tool_rounds: 2 },
      expected_output_schema: {},
      metadata: {},
    },
    tool_policy: { allowed_tools: ["commerce_compare_windows"] },
    depends_on: [],
    metadata: {},
    status: "running",
    result: null,
    error: null,
    checkpoint: null,
    telemetry: {},
    wait_reason: null,
    version: 2,
    event_seq: 3,
    attempt: 1,
    max_attempts: 2,
    priority: 0,
    lease_owner: "worker-1",
    lease_token: 1,
    lease_expires_at: "2026-07-26T00:01:00+00:00",
    created_at: "2026-07-26T00:00:00+00:00",
    updated_at: "2026-07-26T00:00:01+00:00",
    started_at: "2026-07-26T00:00:01+00:00",
    completed_at: null,
  };
}

function taskEventResponse(): CommerceSubagentTaskEventRecord {
  return {
    task_id: TASK_ID,
    thread_id: "thread-1",
    run_id: RUN_ID,
    seq: 1,
    event_type: "task.created",
    payload: { status: "queued" },
    idempotency_key: "task.created",
    created_at: "2026-07-26T00:00:00+00:00",
  };
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
