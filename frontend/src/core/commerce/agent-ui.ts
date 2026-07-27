export const COMMERCE_AGENT_NAME = "commerce-agent";
export const COMMERCE_AGENT_DISPLAY_NAME = "电商经营诊断";
export const COMMERCE_COLLABORATION_LABEL = "协作空间";

export function commerceWorkspaceBrand({
  commerceCaseAgentEnabled,
}: {
  commerceCaseAgentEnabled: boolean;
}): { expanded: string; collapsed: string } {
  return commerceCaseAgentEnabled
    ? { expanded: "经营诊断", collapsed: "诊" }
    : { expanded: "DeerFlow", collapsed: "DF" };
}

export function shouldShowLegacyEcomLaunchNavigation({
  commerceCaseAgentEnabled,
}: {
  commerceCaseAgentEnabled: boolean;
}): boolean {
  return !commerceCaseAgentEnabled;
}

export function isCommerceAgentName(
  agentName: string | null | undefined,
): boolean {
  return agentName === COMMERCE_AGENT_NAME;
}

export function commerceAgentChatHref(threadId?: string | null): string {
  const normalizedThreadId = threadId?.trim();
  const target = normalizedThreadId
    ? encodeURIComponent(normalizedThreadId)
    : "new";
  return `/workspace/agents/${COMMERCE_AGENT_NAME}/chats/${target}`;
}

export function commerceCollaborationHref({
  threadId,
  runId,
  isMock = false,
}: {
  threadId?: string | null;
  runId?: string | null;
  isMock?: boolean;
}): string {
  const search = new URLSearchParams();
  const normalizedThreadId = threadId?.trim();
  const normalizedRunId = runId?.trim();
  if (normalizedThreadId) search.set("threadId", normalizedThreadId);
  if (normalizedRunId) search.set("runId", normalizedRunId);
  if (isMock) search.set("mock", "true");
  const query = search.toString();
  return `/workspace/agents/${COMMERCE_AGENT_NAME}/war-room${query ? `?${query}` : ""}`;
}

export function selectCommerceRunId({
  capturedRunId,
  runs,
}: {
  capturedRunId: string | null | undefined;
  runs: Array<{
    run_id: string;
    assistant_id: string;
    created_at: string;
    updated_at: string;
  }>;
}): string | null {
  const normalizedCapturedRunId = capturedRunId?.trim();
  if (normalizedCapturedRunId) return normalizedCapturedRunId;

  const latest = [...runs]
    .filter((run) => isCommerceAgentName(run.assistant_id))
    .sort((left, right) => {
      const updatedDelta =
        Date.parse(right.updated_at) - Date.parse(left.updated_at);
      if (Number.isFinite(updatedDelta) && updatedDelta !== 0) {
        return updatedDelta;
      }
      const createdDelta =
        Date.parse(right.created_at) - Date.parse(left.created_at);
      if (Number.isFinite(createdDelta) && createdDelta !== 0) {
        return createdDelta;
      }
      return right.run_id.localeCompare(left.run_id);
    })[0];
  return latest?.run_id ?? null;
}
