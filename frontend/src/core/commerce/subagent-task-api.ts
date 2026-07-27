import type { Run } from "@langchain/langgraph-sdk";
import { z } from "zod";

import { fetch as fetchWithAuth } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import { CommerceApiError } from "./api";

const isoDateTimeSchema = z.string().datetime({ offset: true });
const jsonRecordSchema = z.record(z.string(), z.unknown());

export const commerceSubagentTaskStatusSchema = z.enum([
  "queued",
  "running",
  "waiting",
  "waiting_approval",
  "blocked",
  "completed",
  "failed",
  "cancelled",
  "timed_out",
]);

export const commerceSubagentContextPacketSchema = z
  .object({
    schema_version: z.string().min(1),
    goal: z.string().min(1),
    source_refs: z.array(z.string()),
    evidence_refs: z.array(z.string()),
    constraints: jsonRecordSchema,
    available_skills: z.array(z.string().min(1)),
    available_tools: z.array(z.string().min(1)),
    budget: jsonRecordSchema,
    expected_output_schema: jsonRecordSchema,
    metadata: jsonRecordSchema,
  })
  .strict();

export const commerceSubagentTaskSchema = z
  .object({
    task_id: z.string().min(1),
    thread_id: z.string().min(1),
    run_id: z.string().min(1),
    user_id: z.string().min(1).nullable(),
    parent_task_id: z.string().min(1).nullable(),
    subagent_type: z.string().min(1),
    description: z.string().min(1),
    context_packet: commerceSubagentContextPacketSchema,
    tool_policy: jsonRecordSchema,
    depends_on: z.array(z.string().min(1)),
    metadata: jsonRecordSchema,
    status: commerceSubagentTaskStatusSchema,
    result: jsonRecordSchema.nullable(),
    error: jsonRecordSchema.nullable(),
    checkpoint: jsonRecordSchema.nullable(),
    telemetry: jsonRecordSchema,
    wait_reason: z.string().nullable(),
    version: z.number().int().nonnegative(),
    event_seq: z.number().int().positive(),
    attempt: z.number().int().positive(),
    max_attempts: z.number().int().positive(),
    priority: z.number().int(),
    lease_owner: z.string().min(1).nullable(),
    lease_token: z.number().int().nonnegative(),
    lease_expires_at: isoDateTimeSchema.nullable(),
    created_at: isoDateTimeSchema,
    updated_at: isoDateTimeSchema,
    started_at: isoDateTimeSchema.nullable(),
    completed_at: isoDateTimeSchema.nullable(),
  })
  .strict();

export const commerceSubagentTaskEventSchema = z
  .object({
    task_id: z.string().min(1),
    thread_id: z.string().min(1),
    run_id: z.string().min(1),
    seq: z.number().int().positive(),
    event_type: z.string().min(1),
    payload: jsonRecordSchema,
    idempotency_key: z.string().min(1).nullable(),
    created_at: isoDateTimeSchema,
  })
  .strict();

const commerceRunSubagentTasksResponseSchema = z
  .object({ data: z.array(commerceSubagentTaskSchema) })
  .strict();

const commerceSubagentTaskEventsResponseSchema = z
  .object({
    data: z.array(commerceSubagentTaskEventSchema),
    next_after_seq: z.number().int().nonnegative(),
    has_more: z.boolean(),
  })
  .strict();

export type CommerceSubagentTask = z.infer<typeof commerceSubagentTaskSchema>;
export type CommerceSubagentTaskEventRecord = z.infer<
  typeof commerceSubagentTaskEventSchema
>;
export type CommerceSubagentTaskEventsResponse = z.infer<
  typeof commerceSubagentTaskEventsResponseSchema
>;

export interface CommerceRunTaskActivity {
  task: CommerceSubagentTask;
  events: CommerceSubagentTaskEventRecord[];
  nextAfterSeq: number;
  hasMore: boolean;
}

export type CommerceParentRunStatus = Run["status"];

const TERMINAL_PARENT_RUN_STATUSES = new Set<CommerceParentRunStatus>([
  "error",
  "success",
  "timeout",
  "interrupted",
]);

const TERMINAL_SUBAGENT_TASK_STATUSES = new Set<CommerceSubagentTask["status"]>(
  ["completed", "failed", "cancelled", "timed_out"],
);

export function shouldContinueCommerceTaskPolling({
  runStatus,
  activities,
}: {
  runStatus: CommerceParentRunStatus | null | undefined;
  activities: CommerceRunTaskActivity[];
}): boolean {
  if (!runStatus || !TERMINAL_PARENT_RUN_STATUSES.has(runStatus)) {
    return true;
  }
  return activities.some(
    (activity) =>
      activity.hasMore ||
      !TERMINAL_SUBAGENT_TASK_STATUSES.has(activity.task.status),
  );
}

/**
 * Merge one append-only API page into the previous Run activity snapshot.
 *
 * `seq` is the authoritative cursor. A repeated event never replaces the
 * first event already observed at that sequence, and cursors only move
 * forward. The same pure merge is consumed by Chat compact status and the
 * optional collaboration scene.
 */
export function mergeCommerceRunTaskActivityPages({
  previous,
  tasks,
  pages,
}: {
  previous: CommerceRunTaskActivity[];
  tasks: CommerceSubagentTask[];
  pages: Map<string, CommerceSubagentTaskEventsResponse>;
}): CommerceRunTaskActivity[] {
  const previousByTask = new Map(
    previous.map((activity) => [activity.task.task_id, activity]),
  );

  return tasks.map((task) => {
    const prior = previousByTask.get(task.task_id);
    const page = pages.get(task.task_id);
    const eventsBySequence = new Map(
      (prior?.events ?? []).map((event) => [event.seq, event]),
    );
    for (const event of page?.data ?? []) {
      if (!eventsBySequence.has(event.seq)) {
        eventsBySequence.set(event.seq, event);
      }
    }
    const events = [...eventsBySequence.values()].sort(
      (left, right) => left.seq - right.seq,
    );
    return {
      task,
      events,
      nextAfterSeq: Math.max(
        prior?.nextAfterSeq ?? 0,
        page?.next_after_seq ?? 0,
      ),
      hasMore: page?.has_more ?? prior?.hasMore ?? false,
    };
  });
}

export async function loadCommerceRunSubagentTasks({
  runId,
  signal,
}: {
  runId: string;
  signal?: AbortSignal;
}): Promise<CommerceSubagentTask[]> {
  const normalizedRunId = requiredId(runId, "Run ID");
  const payload = await fetchGatewayJson(
    `/api/runs/${encodeURIComponent(normalizedRunId)}/subagent-tasks`,
    commerceRunSubagentTasksResponseSchema,
    signal,
  );
  return payload.data;
}

export async function loadCommerceSubagentTaskEvents({
  taskId,
  afterSeq = 0,
  limit = 200,
  signal,
}: {
  taskId: string;
  afterSeq?: number;
  limit?: number;
  signal?: AbortSignal;
}): Promise<CommerceSubagentTaskEventsResponse> {
  const normalizedTaskId = requiredId(taskId, "Task ID");
  if (!Number.isInteger(afterSeq) || afterSeq < 0) {
    throw new CommerceApiError(
      "request_failed",
      "Task event cursor must be a non-negative integer",
    );
  }
  if (!Number.isInteger(limit) || limit < 1 || limit > 500) {
    throw new CommerceApiError(
      "request_failed",
      "Task event limit must be between 1 and 500",
    );
  }
  return fetchGatewayJson(
    `/api/subagent-tasks/${encodeURIComponent(normalizedTaskId)}/events?after_seq=${afterSeq}&limit=${limit}`,
    commerceSubagentTaskEventsResponseSchema,
    signal,
  );
}

export async function loadCommerceRunTaskActivity({
  runId,
  signal,
}: {
  runId: string;
  signal?: AbortSignal;
}): Promise<CommerceRunTaskActivity[]> {
  return loadCommerceRunTaskActivityPage({ runId, previous: [], signal });
}

export async function loadCommerceRunTaskActivityPage({
  runId,
  previous,
  eventLimit = 200,
  signal,
}: {
  runId: string;
  previous: CommerceRunTaskActivity[];
  eventLimit?: number;
  signal?: AbortSignal;
}): Promise<CommerceRunTaskActivity[]> {
  const tasks = await loadCommerceRunSubagentTasks({ runId, signal });
  const previousByTask = new Map(
    previous.map((activity) => [activity.task.task_id, activity]),
  );
  const pages = new Map(
    await Promise.all(
      tasks.map(async (task) => {
        const response = await loadCommerceSubagentTaskEvents({
          taskId: task.task_id,
          afterSeq: previousByTask.get(task.task_id)?.nextAfterSeq ?? 0,
          limit: eventLimit,
          signal,
        });
        return [task.task_id, response] as const;
      }),
    ),
  );
  return mergeCommerceRunTaskActivityPages({ previous, tasks, pages });
}

function requiredId(value: string, label: string): string {
  const normalized = value.trim();
  if (!normalized) {
    throw new CommerceApiError("request_failed", `${label} is required`);
  }
  return normalized;
}

async function fetchGatewayJson<T>(
  path: string,
  schema: {
    safeParse(value: unknown): { success: true; data: T } | { success: false };
  },
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetchWithAuth(`${getBackendBaseURL()}${path}`, {
      method: "GET",
      cache: "no-store",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new CommerceApiError(
      "request_failed",
      "Durable Task API request failed",
    );
  }

  if (!response.ok) {
    throw new CommerceApiError(
      "request_failed",
      `Durable Task API responded with HTTP ${response.status}`,
      response.status,
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new CommerceApiError(
      "invalid_response",
      "Durable Task API response was not valid JSON",
      response.status,
    );
  }
  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new CommerceApiError(
      "invalid_response",
      "Durable Task API response did not match the frontend contract",
      response.status,
    );
  }
  return parsed.data;
}
