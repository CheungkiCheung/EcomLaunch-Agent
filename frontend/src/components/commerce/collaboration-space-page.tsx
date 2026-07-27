"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  commerceAgentChatHref,
  selectCommerceRunId,
} from "@/core/commerce/agent-ui";
import {
  buildCommerceCollaborationSceneViewModel,
  type CommerceCollaborationSceneViewModel,
} from "@/core/commerce/collaboration-scene-view-model";
import { useThreadRuns, useThreadState } from "@/core/threads/hooks";

import { CommerceCollaborationSpaceView } from "./collaboration-space-view";
import { useCommerceRunTaskActivity } from "./use-commerce-run-task-activity";

const EMPTY_SCENE: CommerceCollaborationSceneViewModel = {
  sceneStatus: "empty",
  statusText: "当前没有协作任务",
  actors: [],
  hasProjectionWarnings: false,
  projectionWarnings: [],
};

export function CommerceCollaborationSpacePage() {
  const searchParams = useSearchParams();
  const threadId = normalizedParam(searchParams.get("threadId"));
  const explicitRunId = normalizedParam(searchParams.get("runId"));
  const isMock = searchParams.get("mock") === "true";
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);

  const runs = useThreadRuns(threadId && !isMock ? threadId : undefined, {
    pollWhileActive: true,
  });
  const runId = useMemo(
    () =>
      selectCommerceRunId({
        capturedRunId: explicitRunId,
        runs: runs.data ?? [],
      }),
    [explicitRunId, runs.data],
  );
  const runStatus = useMemo(
    () => runs.data?.find((run) => run.run_id === runId)?.status ?? null,
    [runId, runs.data],
  );
  const activity = useCommerceRunTaskActivity({
    runId,
    runStatus,
    enabled: Boolean(runId) && !isMock,
  });
  const threadState = useThreadState(threadId, {
    enabled: Boolean(threadId) && !isMock,
    isMock,
  });
  const scene = useMemo(
    () =>
      runId
        ? buildCommerceCollaborationSceneViewModel(activity.viewModel)
        : EMPTY_SCENE,
    [activity.viewModel, runId],
  );

  useEffect(() => {
    if (
      selectedTaskId &&
      !scene.actors.some((actor) => actor.taskId === selectedTaskId)
    ) {
      setSelectedTaskId(null);
    }
  }, [scene.actors, selectedTaskId]);

  const queryError =
    activity.error ??
    (runs.error instanceof Error ? runs.error : null) ??
    (threadState.error instanceof Error ? threadState.error : null);

  return (
    <CommerceCollaborationSpaceView
      scene={scene}
      title={
        normalizedParam(threadState.data?.title ?? null) ?? "经营诊断协作空间"
      }
      threadId={threadId}
      runId={runId}
      backHref={commerceAgentChatHref(threadId)}
      selectedTaskId={selectedTaskId}
      isLoading={
        activity.isLoading ||
        (!explicitRunId && Boolean(threadId) && runs.isLoading)
      }
      error={queryError}
      onSelectTask={setSelectedTaskId}
    />
  );
}

function normalizedParam(value: string | null) {
  const normalized = value?.trim();
  return normalized?.length ? normalized : null;
}
