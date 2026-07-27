import { fetch as fetchWithAuth } from "@/core/api/fetcher";
import { env } from "@/env";

import {
  commerceActionDetailResponseSchema,
  commerceActionExecutionResponseSchema,
  commerceActionRecordListResponseSchema,
  commerceApprovalDecisionResponseSchema,
  commerceDatasetDetailResponseSchema,
  commerceDatasetIntakeResponseSchema,
  commerceDatasetListResponseSchema,
  commerceExplicitCaseResponseSchema,
  commerceMappingResumeResponseSchema,
  commerceCaseDetailResponseSchema,
  commerceCaseListResponseSchema,
  commerceDomainEventListResponseSchema,
  commerceRunListResponseSchema,
  commerceRunCheckpointListResponseSchema,
  commerceRunDetailResponseSchema,
  commerceSkillCandidateEvidenceResponseSchema,
  commerceSkillCandidateListResponseSchema,
  commerceSkillCandidateTransitionResponseSchema,
  type CommerceActionCenterSnapshot,
  type CommerceActionExecutionResponse,
  type CommerceAgentRunSnapshot,
  type CommerceApprovalDecisionResponse,
  type CommerceDataInboxSnapshot,
  type CommerceDatasetIntake,
  type CommerceExplicitCaseResponse,
  type CommerceMappingResumeResponse,
  type CommerceSkillCandidateTransition,
  type CommerceSkillsEvalsSnapshot,
  type CommerceWorkspaceSnapshot,
} from "./types";

export type CommerceApiErrorCode =
  | "workspace_missing"
  | "request_failed"
  | "invalid_response";

export class CommerceApiError extends Error {
  constructor(
    readonly code: CommerceApiErrorCode,
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "CommerceApiError";
  }
}

interface LoadCommerceWorkspaceOptions {
  workspaceId: string;
  selectedCaseId?: string;
  signal?: AbortSignal;
}

interface LoadCommerceDataInboxOptions {
  workspaceId: string;
  selectedDatasetId?: string;
  signal?: AbortSignal;
}

export async function loadCommerceWorkspaceSnapshot({
  workspaceId,
  selectedCaseId,
  signal,
}: LoadCommerceWorkspaceOptions): Promise<CommerceWorkspaceSnapshot> {
  const normalizedWorkspaceId = workspaceId.trim();
  if (!normalizedWorkspaceId) {
    throw new CommerceApiError(
      "workspace_missing",
      "Commerce Workspace ID is required",
    );
  }

  const list = await fetchCommerceJson(
    "/cases?limit=100&offset=0",
    normalizedWorkspaceId,
    commerceCaseListResponseSchema,
    signal,
  );
  const cases = [...list.items].sort(
    (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
  );
  const activeCaseId =
    selectedCaseId && cases.some((item) => item.id === selectedCaseId)
      ? selectedCaseId
      : cases[0]?.id;

  if (!activeCaseId) {
    return {
      workspaceId: normalizedWorkspaceId,
      cases,
      selectedCase: null,
      events: [],
      runs: [],
    };
  }

  const encodedCaseId = encodeURIComponent(activeCaseId);
  const [selectedCase, events, runs] = await Promise.all([
    fetchCommerceJson(
      `/cases/${encodedCaseId}`,
      normalizedWorkspaceId,
      commerceCaseDetailResponseSchema,
      signal,
    ),
    fetchCommerceJson(
      `/cases/${encodedCaseId}/events`,
      normalizedWorkspaceId,
      commerceDomainEventListResponseSchema,
      signal,
    ),
    fetchCommerceJson(
      `/cases/${encodedCaseId}/runs?limit=100&offset=0`,
      normalizedWorkspaceId,
      commerceRunListResponseSchema,
      signal,
    ),
  ]);

  return {
    workspaceId: normalizedWorkspaceId,
    cases,
    selectedCase,
    events: events.items,
    runs: runs.items,
  };
}

export async function loadCommerceDataInboxSnapshot({
  workspaceId,
  selectedDatasetId,
  signal,
}: LoadCommerceDataInboxOptions): Promise<CommerceDataInboxSnapshot> {
  const normalizedWorkspaceId = workspaceId.trim();
  if (!normalizedWorkspaceId) {
    throw new CommerceApiError(
      "workspace_missing",
      "Commerce Workspace ID is required",
    );
  }

  const list = await fetchCommerceJson(
    "/datasets?limit=100&offset=0",
    normalizedWorkspaceId,
    commerceDatasetListResponseSchema,
    signal,
  );
  const activeDatasetId =
    selectedDatasetId &&
    list.items.some((item) => item.dataset_id === selectedDatasetId)
      ? selectedDatasetId
      : list.items[0]?.dataset_id;

  if (!activeDatasetId) {
    return {
      workspaceId: normalizedWorkspaceId,
      datasets: list.items,
      selectedDataset: null,
    };
  }

  const selectedDataset = await fetchCommerceJson(
    `/datasets/${encodeURIComponent(activeDatasetId)}`,
    normalizedWorkspaceId,
    commerceDatasetDetailResponseSchema,
    signal,
  );
  return {
    workspaceId: normalizedWorkspaceId,
    datasets: list.items,
    selectedDataset,
  };
}

export async function uploadCommerceDataset({
  workspaceId,
  files,
  signal,
}: {
  workspaceId: string;
  files: File[];
  signal?: AbortSignal;
}): Promise<CommerceDatasetIntake> {
  const normalizedWorkspaceId = workspaceId.trim();
  if (!normalizedWorkspaceId) {
    throw new CommerceApiError(
      "workspace_missing",
      "Commerce Workspace ID is required",
    );
  }
  if (files.length === 0) {
    throw new CommerceApiError(
      "request_failed",
      "At least one file is required",
    );
  }
  const body = new FormData();
  for (const file of files) body.append("files", file);
  return fetchCommerceJson(
    "/datasets/intake",
    normalizedWorkspaceId,
    commerceDatasetIntakeResponseSchema,
    signal,
    {
      method: "POST",
      body,
    },
  );
}

export async function resumeCommerceDatasetMapping({
  workspaceId,
  datasetId,
  actorId,
  tableName,
  columnName,
  semanticField,
  idempotencyKey,
  signal,
}: {
  workspaceId: string;
  datasetId: string;
  actorId: string;
  tableName: string;
  columnName: string;
  semanticField: string;
  idempotencyKey: string;
  signal?: AbortSignal;
}): Promise<CommerceMappingResumeResponse> {
  return fetchCommerceJson(
    `/datasets/${encodeURIComponent(datasetId)}/mapping-resume`,
    workspaceId,
    commerceMappingResumeResponseSchema,
    signal,
    {
      method: "POST",
      body: JSON.stringify({
        confirmations: [
          {
            table_name: tableName,
            column_name: columnName,
            semantic_field: semanticField,
          },
        ],
        idempotency_key: idempotencyKey,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-Commerce-Actor-Id": actorId,
      },
    },
  );
}

export type CommerceExplicitCasePath =
  | "fulfillment"
  | "seller_peer"
  | "review_experience";

export interface CommerceMetricWindowInput {
  start: string;
  end: string;
}

export interface CommercePeerPolicyInput {
  productCategory: string;
  minOrdersPerSeller: number;
  matchSellerState: boolean;
}

export async function createCommerceExplicitCase({
  workspaceId,
  datasetId,
  sellerId,
  baselineWindow,
  currentWindow,
  requestedPaths,
  peerPolicy,
  signal,
}: {
  workspaceId: string;
  datasetId: string;
  sellerId: string;
  baselineWindow: CommerceMetricWindowInput;
  currentWindow: CommerceMetricWindowInput;
  requestedPaths: CommerceExplicitCasePath[];
  peerPolicy: CommercePeerPolicyInput | null;
  signal?: AbortSignal;
}): Promise<CommerceExplicitCaseResponse> {
  const normalizedWorkspaceId = workspaceId.trim();
  const normalizedDatasetId = datasetId.trim();
  const normalizedSellerId = sellerId.trim();
  if (!normalizedWorkspaceId) {
    throw new CommerceApiError(
      "workspace_missing",
      "Commerce Workspace ID is required",
    );
  }
  if (!normalizedDatasetId || !normalizedSellerId) {
    throw new CommerceApiError(
      "request_failed",
      "Dataset and seller are required",
    );
  }
  if (requestedPaths.length < 1 || requestedPaths.length > 3) {
    throw new CommerceApiError(
      "request_failed",
      "Explicit Case requires one to three paths",
    );
  }
  const uniquePaths = [...new Set(requestedPaths)];
  if (uniquePaths.length !== requestedPaths.length) {
    throw new CommerceApiError(
      "request_failed",
      "Explicit Case paths must be unique",
    );
  }
  return fetchCommerceJson(
    `/datasets/${encodeURIComponent(normalizedDatasetId)}/cases`,
    normalizedWorkspaceId,
    commerceExplicitCaseResponseSchema,
    signal,
    {
      method: "POST",
      body: JSON.stringify({
        seller_id: normalizedSellerId,
        baseline_window: baselineWindow,
        current_window: currentWindow,
        requested_paths: uniquePaths,
        peer_policy: peerPolicy
          ? {
              product_category: peerPolicy.productCategory.trim(),
              min_orders_per_seller: peerPolicy.minOrdersPerSeller,
              match_seller_state: peerPolicy.matchSellerState,
            }
          : null,
      }),
      headers: { "Content-Type": "application/json" },
    },
  );
}

export async function loadCommerceActionCenterSnapshot({
  workspaceId,
  caseIds,
  selectedActionId,
  signal,
}: {
  workspaceId: string;
  caseIds: string[];
  selectedActionId?: string;
  signal?: AbortSignal;
}): Promise<CommerceActionCenterSnapshot> {
  const normalizedWorkspaceId = workspaceId.trim();
  if (!normalizedWorkspaceId) {
    throw new CommerceApiError(
      "workspace_missing",
      "Commerce Workspace ID is required",
    );
  }
  const uniqueCaseIds = [...new Set(caseIds.map((item) => item.trim()))].filter(
    Boolean,
  );
  const lists = await Promise.all(
    uniqueCaseIds.map((caseId) =>
      fetchCommerceJson(
        `/cases/${encodeURIComponent(caseId)}/actions`,
        normalizedWorkspaceId,
        commerceActionRecordListResponseSchema,
        signal,
      ),
    ),
  );
  const records = lists
    .flatMap((item) => item.items)
    .sort(
      (left, right) =>
        Date.parse(right.updated_at) - Date.parse(left.updated_at),
    );
  const activeActionId =
    selectedActionId &&
    records.some((item) => item.action.id === selectedActionId)
      ? selectedActionId
      : records[0]?.action.id;
  const selectedDetail = activeActionId
    ? await fetchCommerceJson(
        `/actions/${encodeURIComponent(activeActionId)}`,
        normalizedWorkspaceId,
        commerceActionDetailResponseSchema,
        signal,
      )
    : null;
  return {
    workspaceId: normalizedWorkspaceId,
    records,
    selectedDetail,
  };
}

export async function loadCommerceAgentRunSnapshot({
  workspaceId,
  caseIds,
  selectedRunId,
  signal,
}: {
  workspaceId: string;
  caseIds: string[];
  selectedRunId?: string;
  signal?: AbortSignal;
}): Promise<CommerceAgentRunSnapshot> {
  const normalizedWorkspaceId = workspaceId.trim();
  if (!normalizedWorkspaceId) {
    throw new CommerceApiError(
      "workspace_missing",
      "Commerce Workspace ID is required",
    );
  }
  const uniqueCaseIds = [...new Set(caseIds.map((item) => item.trim()))].filter(
    Boolean,
  );
  const lists = await Promise.all(
    uniqueCaseIds.map((caseId) =>
      fetchCommerceJson(
        `/cases/${encodeURIComponent(caseId)}/runs?limit=100&offset=0`,
        normalizedWorkspaceId,
        commerceRunListResponseSchema,
        signal,
      ),
    ),
  );
  const runs = lists
    .flatMap((item) => item.items)
    .sort(
      (left, right) =>
        Date.parse(right.updated_at) - Date.parse(left.updated_at),
    );
  const activeRunId =
    selectedRunId && runs.some((item) => item.id === selectedRunId)
      ? selectedRunId
      : runs[0]?.id;
  if (!activeRunId) {
    return {
      workspaceId: normalizedWorkspaceId,
      runs,
      selectedDetail: null,
      events: [],
      checkpoints: [],
    };
  }
  const encodedRunId = encodeURIComponent(activeRunId);
  const [selectedDetail, events, checkpoints] = await Promise.all([
    fetchCommerceJson(
      `/runs/${encodedRunId}`,
      normalizedWorkspaceId,
      commerceRunDetailResponseSchema,
      signal,
    ),
    fetchCommerceJson(
      `/runs/${encodedRunId}/events`,
      normalizedWorkspaceId,
      commerceDomainEventListResponseSchema,
      signal,
    ),
    fetchCommerceJson(
      `/runs/${encodedRunId}/checkpoints`,
      normalizedWorkspaceId,
      commerceRunCheckpointListResponseSchema,
      signal,
    ),
  ]);
  return {
    workspaceId: normalizedWorkspaceId,
    runs,
    selectedDetail,
    events: events.items,
    checkpoints: checkpoints.items,
  };
}

export async function loadCommerceSkillsEvalsSnapshot({
  workspaceId,
  selectedCandidateId,
  signal,
}: {
  workspaceId: string;
  selectedCandidateId?: string;
  signal?: AbortSignal;
}): Promise<CommerceSkillsEvalsSnapshot> {
  const normalizedWorkspaceId = workspaceId.trim();
  if (!normalizedWorkspaceId) {
    throw new CommerceApiError(
      "workspace_missing",
      "Commerce Workspace ID is required",
    );
  }
  const list = await fetchCommerceJson(
    "/skill-candidates",
    normalizedWorkspaceId,
    commerceSkillCandidateListResponseSchema,
    signal,
  );
  const candidates = [...list.items].sort(
    (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
  );
  const activeCandidateId =
    selectedCandidateId &&
    candidates.some((item) => item.id === selectedCandidateId)
      ? selectedCandidateId
      : candidates[0]?.id;
  const selectedEvidence = activeCandidateId
    ? await fetchCommerceJson(
        `/skill-candidates/${encodeURIComponent(activeCandidateId)}/evidence`,
        normalizedWorkspaceId,
        commerceSkillCandidateEvidenceResponseSchema,
        signal,
      )
    : null;
  return {
    workspaceId: normalizedWorkspaceId,
    candidates,
    selectedEvidence,
  };
}

export async function promoteCommerceSkillCandidate({
  workspaceId,
  actorId,
  candidateId,
  idempotencyKey,
  signal,
}: {
  workspaceId: string;
  actorId: string;
  candidateId: string;
  idempotencyKey: string;
  signal?: AbortSignal;
}): Promise<CommerceSkillCandidateTransition> {
  return fetchCommerceJson(
    `/skill-candidates/${encodeURIComponent(candidateId)}/promote`,
    workspaceId,
    commerceSkillCandidateTransitionResponseSchema,
    signal,
    {
      method: "POST",
      body: JSON.stringify({ idempotency_key: idempotencyKey }),
      headers: {
        "Content-Type": "application/json",
        "X-Commerce-Actor-Id": actorId,
      },
    },
  );
}

export async function rollbackCommerceActiveSkill({
  workspaceId,
  actorId,
  skillName,
  reason,
  idempotencyKey,
  signal,
}: {
  workspaceId: string;
  actorId: string;
  skillName: string;
  reason: string;
  idempotencyKey: string;
  signal?: AbortSignal;
}): Promise<CommerceSkillCandidateTransition> {
  return fetchCommerceJson(
    `/skills/${encodeURIComponent(skillName)}/rollback`,
    workspaceId,
    commerceSkillCandidateTransitionResponseSchema,
    signal,
    {
      method: "POST",
      body: JSON.stringify({
        reason: reason.trim(),
        idempotency_key: idempotencyKey,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-Commerce-Actor-Id": actorId,
      },
    },
  );
}

export async function executeCommerceAction({
  workspaceId,
  actorId,
  actionId,
  operation,
  idempotencyKey,
  signal,
}: {
  workspaceId: string;
  actorId: string;
  actionId: string;
  operation: "execute" | "rollback";
  idempotencyKey: string;
  signal?: AbortSignal;
}): Promise<CommerceActionExecutionResponse> {
  const normalizedWorkspaceId = workspaceId.trim();
  const normalizedActorId = actorId.trim();
  const normalizedActionId = actionId.trim();
  const normalizedIdempotencyKey = idempotencyKey.trim();
  if (!normalizedWorkspaceId) {
    throw new CommerceApiError(
      "workspace_missing",
      "Commerce Workspace ID is required",
    );
  }
  if (
    !normalizedActorId ||
    !normalizedActionId ||
    normalizedIdempotencyKey.length < 8
  ) {
    throw new CommerceApiError(
      "request_failed",
      "Action execution requires actor, action and idempotency key",
    );
  }
  return fetchCommerceJson(
    `/actions/${encodeURIComponent(normalizedActionId)}/executions`,
    normalizedWorkspaceId,
    commerceActionExecutionResponseSchema,
    signal,
    {
      method: "POST",
      body: JSON.stringify({
        operation,
        idempotency_key: normalizedIdempotencyKey,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-Commerce-Actor-Id": normalizedActorId,
      },
    },
  );
}

export async function decideCommerceActionApproval({
  workspaceId,
  actorId,
  actionId,
  decision,
  idempotencyKey,
  reason,
  signal,
}: {
  workspaceId: string;
  actorId: string;
  actionId: string;
  decision: "approve" | "reject";
  idempotencyKey: string;
  reason?: string | null;
  signal?: AbortSignal;
}): Promise<CommerceApprovalDecisionResponse> {
  const normalizedWorkspaceId = workspaceId.trim();
  const normalizedActorId = actorId.trim();
  const normalizedActionId = actionId.trim();
  const normalizedIdempotencyKey = idempotencyKey.trim();
  let normalizedReason: string | null = null;
  if (reason?.trim()) normalizedReason = reason.trim();
  if (!normalizedWorkspaceId) {
    throw new CommerceApiError(
      "workspace_missing",
      "Commerce Workspace ID is required",
    );
  }
  if (
    !normalizedActorId ||
    !normalizedActionId ||
    normalizedIdempotencyKey.length < 8
  ) {
    throw new CommerceApiError(
      "request_failed",
      "Approval decision requires actor, action and idempotency key",
    );
  }
  return fetchCommerceJson(
    `/actions/${encodeURIComponent(normalizedActionId)}/approvals/${decision}`,
    normalizedWorkspaceId,
    commerceApprovalDecisionResponseSchema,
    signal,
    {
      method: "POST",
      body: JSON.stringify({
        idempotency_key: normalizedIdempotencyKey,
        reason: normalizedReason,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-Commerce-Actor-Id": normalizedActorId,
      },
    },
  );
}

function commerceBaseUrl(): string {
  const configured = env.NEXT_PUBLIC_BACKEND_BASE_URL?.trim();
  return configured ? configured.replace(/\/+$/, "") : "";
}

async function fetchCommerceJson<T>(
  path: string,
  workspaceId: string,
  schema: {
    safeParse(value: unknown): { success: true; data: T } | { success: false };
  },
  signal?: AbortSignal,
  options?: {
    method: "POST";
    body: BodyInit;
    headers?: HeadersInit;
  },
): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(options?.headers);
    headers.set("Accept", "application/json");
    headers.set("X-Commerce-Workspace-Id", workspaceId);
    response = await (options ? fetchWithAuth : globalThis.fetch)(
      `${commerceBaseUrl()}/api/commerce${path}`,
      {
        method: options?.method ?? "GET",
        body: options?.body,
        credentials: "include",
        cache: "no-store",
        headers,
        signal,
      },
    );
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new CommerceApiError("request_failed", "Commerce API request failed");
  }

  if (!response.ok) {
    throw new CommerceApiError(
      "request_failed",
      `Commerce API responded with HTTP ${response.status}`,
      response.status,
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new CommerceApiError(
      "invalid_response",
      "Commerce API response was not valid JSON",
      response.status,
    );
  }

  const parsed = schema.safeParse(payload);
  if (!parsed.success) {
    throw new CommerceApiError(
      "invalid_response",
      "Commerce API response did not match the frontend contract",
      response.status,
    );
  }
  return parsed.data;
}
